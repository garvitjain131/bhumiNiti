#!/usr/bin/env python3
"""
Satellite -> district x year indicator panel for all of India, computed in Google Earth Engine.

Land conversion, built-up growth, night-light growth and rainfall for every district, as CSVs
you can join on the district code. Nothing heavy runs locally: the script queues Earth Engine
export tasks that land in Google Drive (typically 10-40 min per task, all run in parallel).

Setup (once):
  earthengine authenticate                     # free non-commercial Cloud project
  python pipelines/gee_district_indicators.py prep --districts data/boundaries/districts/SOI_Districts.parquet
      -> writes districts_upload.zip; upload it in code.earthengine.google.com > Assets > NEW > Shape files
         as  projects/<your-project>/assets/india_districts
  python pipelines/gee_district_indicators.py run --project <your-project> \
      --asset projects/<your-project>/assets/india_districts

Without an uploaded asset, --asset gaul uses FAO GAUL 2015 level-2 (outdated; its boundary
depiction does not follow the Survey of India) - development only, never for a demo.
"""
from __future__ import annotations

import argparse
import sys

DW_CLASSES = ["water", "trees", "grass", "flooded_vegetation", "crops", "shrub_and_scrub", "built", "bare", "snow_and_ice"]


def prep(args):
    import glob
    import zipfile
    import geopandas as gpd
    gdf = gpd.read_parquet(args.districts).to_crs(4326)
    gdf["geometry"] = gdf.geometry.simplify(0.001, preserve_topology=True)  # ~100 m; keeps upload small
    print("columns:", [c for c in gdf.columns if c != "geometry"])
    gdf.columns = [c[:10] for c in gdf.columns]  # shapefile field limit
    gdf.to_file("districts_upload.shp")
    with zipfile.ZipFile("districts_upload.zip", "w") as z:
        for f in glob.glob("districts_upload.*"):
            if not f.endswith(".zip"):
                z.write(f)
    print(f"wrote districts_upload.zip ({len(gdf)} districts); upload it as an Earth Engine table asset")


def run(args):
    import ee
    ee.Initialize(project=args.project)

    if args.asset == "gaul":
        dist = ee.FeatureCollection("FAO/GAUL/2015/level2").filter(ee.Filter.eq("ADM0_NAME", "India"))
        print("WARNING: GAUL boundaries - development only", file=sys.stderr)
    else:
        dist = ee.FeatureCollection(args.asset)
    india = ee.Geometry.Rectangle([68, 6, 98, 38])

    def panel(years, image_for_year, reducer, scale, tile_scale=4):
        """reduceRegions per year -> one flat table with a 'year' column, geometry dropped."""
        def tag(y):
            return lambda f: f.set("year", y).setGeometry(None)
        fcs = []
        for y in years:
            fc = image_for_year(y).reduceRegions(collection=dist, reducer=reducer, scale=scale, tileScale=tile_scale)
            fcs.append(fc.map(tag(y)))
        return ee.FeatureCollection(fcs).flatten()

    # Dynamic World (10 m, 2016+): annual modal class -> share of district area per class
    def dynamic_world(y):
        s = ee.Date.fromYMD(y, 1, 1)
        mode = (ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1").filterDate(s, s.advance(1, "year"))
                .filterBounds(india).select("label").reduce(ee.Reducer.mode()))
        return ee.Image.cat([mode.eq(i).rename(c) for i, c in enumerate(DW_CLASSES)])

    # MODIS MCD12Q1 (500 m, 2001-2023): long consistent series for land-conversion trends
    def modis_lc(y):
        lc = (ee.ImageCollection("MODIS/061/MCD12Q1").filter(ee.Filter.calendarRange(y, y, "year"))
              .first().select("LC_Type1"))
        return ee.Image.cat([lc.lte(5).rename("forest"), lc.eq(12).rename("cropland"), lc.eq(13).rename("urban"),
                             lc.eq(14).rename("crop_natural_mosaic"), lc.eq(10).rename("grassland"),
                             lc.eq(16).rename("barren"), lc.eq(17).rename("water")])

    # GHSL built-up surface (100 m, 1975-2030 in 5-yr epochs; 2025/2030 are model projections)
    def ghsl(y):
        return ee.Image(f"JRC/GHSL/P2023A/GHS_BUILT_S/{y}").select("built_surface").divide(1e6).rename("built_km2")

    # VIIRS monthly night lights (500 m, 2014+) -> annual mean radiance
    def viirs(y):
        s = ee.Date.fromYMD(y, 1, 1)
        return (ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG").filterDate(s, s.advance(1, "year"))
                .select("avg_rad").mean().rename("ntl_avg_rad"))

    # CHIRPS rainfall (5 km, 1981+) -> annual total mm
    def chirps(y):
        s = ee.Date.fromYMD(y, 1, 1)
        return (ee.ImageCollection("UCSB-CHG/CHIRPS/PENTAD").filterDate(s, s.advance(1, "year"))
                .select("precipitation").sum().rename("rain_mm"))

    rng = lambda a, b, step=1: list(range(a, b + 1, step))
    tasks = {
        "dw_landcover_share": (panel(args.dw_years, dynamic_world, ee.Reducer.mean(), 100, 16),
                               "Share of district area in each Dynamic World class (annual mode)"),
        "modis_landcover_share": (panel(rng(2001, 2023), modis_lc, ee.Reducer.mean(), 500),
                                  "Share of district area per MODIS IGBP class group"),
        "ghsl_builtup_km2": (panel(rng(1975, 2030, 5), ghsl, ee.Reducer.sum(), 100, 8),
                             "Built-up surface km2 (2025/2030 = GHSL projections, label as PREDICTED)"),
        "viirs_nightlights": (panel(rng(2014, args.last_year), viirs,
                                    ee.Reducer.mean().combine(ee.Reducer.sum(), "", True), 500),
                              "Mean and sum of annual mean VIIRS radiance"),
        "chirps_rainfall": (panel(rng(2001, args.last_year), chirps, ee.Reducer.mean(), 5566),
                            "District-mean annual rainfall mm"),
    }
    for name, (fc, desc) in tasks.items():
        if args.only and name not in args.only.split(","):
            continue
        t = ee.batch.Export.table.toDrive(collection=fc, description=f"lpip_{name}", folder=args.folder,
                                          fileNamePrefix=name, fileFormat="CSV")
        t.start()
        print(f"queued {name:<24} task={t.id}  {desc}")
    print(f"\nTrack at https://code.earthengine.google.com/tasks ; CSVs land in Drive/{args.folder}/ "
          f"-> copy to data/temporal/. Every row = district x year; label satellite-derived values "
          f"OBSERVED/ESTIMATED, projections PREDICTED.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep", help="simplify + zip a district parquet for GEE upload")
    p.add_argument("--districts", required=True)
    r = sub.add_parser("run", help="queue export tasks")
    r.add_argument("--project", required=True, help="Google Cloud project registered for Earth Engine")
    r.add_argument("--asset", default="gaul", help="district FeatureCollection asset id, or 'gaul'")
    r.add_argument("--folder", default="lpip_gee")
    r.add_argument("--dw-years", type=lambda s: [int(x) for x in s.split(",")], default=[2017, 2019, 2021, 2023, 2025])
    r.add_argument("--last-year", type=int, default=2025)
    r.add_argument("--only", help="comma-separated task names")
    args = ap.parse_args()
    prep(args) if args.cmd == "prep" else run(args)


if __name__ == "__main__":
    main()
