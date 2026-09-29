import dynamic from "next/dynamic";
import { useRouter } from "next/router";
import { useEffect, useMemo, useState } from "react";
import { DistrictPanel } from "@/components/atlas/DistrictPanel";
import { LayerPicker, type SelectedLayer } from "@/components/atlas/LayerPicker";
import { MapLegend } from "@/components/atlas/MapLegend";
import { ParcelPanel } from "@/components/atlas/ParcelPanel";
import { SpatialQueryCard } from "@/components/atlas/SpatialQueryCard";
import { PageContainer } from "@/components/layout/PageContainer";
import { DIVERGING_COLORS, SEQUENTIAL_COLORS, quantiles } from "@/components/map/colorScales";
import type { PointLayer } from "@/components/map/DistrictMap";
import { Button, Card, DataLabel, Spinner } from "@/components/ui";
import { INDIA_BOUNDS } from "@/config/geography";
import { useApi } from "@/hooks/useApi";
import { api } from "@/lib/api/client";

// MapLibre needs the browser, so the map is loaded on the client only.
const DistrictMap = dynamic(() => import("@/components/map/DistrictMap"), { ssr: false, loading: () => <Spinner text="Loading map" /> });

export default function AtlasPage() {
  const router = useRouter();
  const { data: layers } = useApi("/api/v1/geo/layers");
  const { data: states } = useApi("/api/v1/geo/states");
  const [layer, setLayer] = useState<SelectedLayer>({ kind: "metric", id: "climate_risk_index" });
  const [year, setYear] = useState<number | "">("");
  const [showConflicts, setShowConflicts] = useState(true);
  const [showLandslides, setShowLandslides] = useState(false);
  const [showParcels, setShowParcels] = useState(false);
  const [fitTo, setFitTo] = useState<number[] | null>(null);
  const [district, setDistrict] = useState<any>(null);
  const [parcel, setParcel] = useState<any>(null);

  // ?metric= opens the atlas on a given layer (linked from the overview page).
  useEffect(() => {
    if (router.isReady && typeof router.query.metric === "string") setLayer({ kind: "metric", id: router.query.metric });
  }, [router.isReady, router.query.metric]);

  const { data: geo, loading } = useApi("/api/v1/geo/districts",
    layer.kind === "metric" ? { metric: layer.id } : { indicator: layer.id, year: year || undefined });
  const { data: conflicts } = useApi(showConflicts ? "/api/v1/geo/points/conflicts" : null);
  const { data: landslides } = useApi(showLandslides ? "/api/v1/geo/points/landslides" : null);

  const layerMeta = layer.kind === "metric"
    ? layers?.district_metrics.find((m: any) => m.metric === layer.id)
    : layers?.time_series_indicators.find((m: any) => m.indicator === layer.id);
  const isDiverging = layer.kind === "metric" && /change|growth/.test(layer.id);

  const choropleth = useMemo(() => {
    if (!geo) return undefined;
    const values = geo.features.map((f: any) => f.properties.value).filter((v: any) => v !== null);
    if (isDiverging) {
      const breaks = [...quantiles(values.filter((v: number) => v < 0), 3), 0, ...quantiles(values.filter((v: number) => v > 0), 3)];
      return { data: geo, breaks, colors: DIVERGING_COLORS.slice(0, breaks.length + 1) };
    }
    const breaks = quantiles(values, 7);
    return { data: geo, breaks, colors: SEQUENTIAL_COLORS.slice(0, breaks.length + 1) };
  }, [geo, isDiverging]);

  const points = useMemo(() => {
    const layersOut: PointLayer[] = [];
    if (conflicts) layersOut.push({
      id: "conflicts", data: conflicts, color: "#b42318", radiusKey: "conflicts",
      label: (x: any) => `<b>${x.district}</b><br/>${x.conflicts} land conflicts<br/>${Number(x.people_affected || 0).toLocaleString("en-IN")} people affected<br/>Main sector: ${x.main_sector}`,
    });
    if (landslides) layersOut.push({
      id: "slides", data: landslides, color: "#7c3aed",
      label: (x: any) => `Landslide · ${x.district ?? ""}, ${x.state ?? ""}<br/>Trigger: ${x.trigger ?? "n/a"}`,
    });
    return layersOut;
  }, [conflicts, landslides]);

  const cadastralSource = layers?.cadastral;
  const cadastral = useMemo(
    () => cadastralSource ? { url: cadastralSource.url, layer: cadastralSource.layer, bounds: cadastralSource.bounds, show: showParcels } : null,
    [cadastralSource, showParcels],
  );

  async function openDistrict(props: any) {
    setParcel(null);
    setDistrict({ loading: true, name: props.name });
    setDistrict(await api.get(`/api/v1/geo/districts/${props.district_lgd}`));
  }

  async function openParcel(props: any) {
    setParcel({ loading: true });
    try {
      const summary = await api.get("/api/v1/geo/cadastral/village-summary", { village: props.vname });
      setParcel({ ...summary, gid: props.gid, area: props.area_ha, village: props.vname });
    } catch (e) {
      setParcel({ error: e, village: props.vname });
    }
  }

  return (
    <PageContainer title="GIS Atlas"
      subtitle="Land use, climate vulnerability, infrastructure and policy impact for every district. Click a district for its profile; zoom into Dhamtari (Chhattisgarh) to see cadastral parcels.">
      <div className="grid gap-4 xl:grid-cols-[300px_1fr_340px]">
        <div className="space-y-4">
          <LayerPicker layers={layers} selected={layer} onSelect={setLayer} year={year} onYearChange={setYear} />
          <Card title="Overlays">
            <div className="space-y-1 text-sm">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={showConflicts} onChange={(e) => setShowConflicts(e.target.checked)} /> Land conflict hotspots
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={showLandslides} onChange={(e) => setShowLandslides(e.target.checked)} /> Landslides (GSI)
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={showParcels}
                  onChange={(e) => { setShowParcels(e.target.checked); if (e.target.checked && cadastralSource) setFitTo(cadastralSource.bounds); }} />
                Cadastral parcels (Dhamtari)
              </label>
            </div>
          </Card>
        </div>

        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">{layerMeta?.name ?? "…"}</span>
            {layerMeta?.unit && <span className="text-muted">({layerMeta.unit})</span>}
            {geo && <DataLabel label={geo.features.find((f: any) => f.properties.label)?.properties.label} />}
            {loading && <span className="text-xs text-muted">updating…</span>}
            <Button variant="ghost" className="ml-auto text-xs" onClick={() => setFitTo([...INDIA_BOUNDS])}>Reset view</Button>
          </div>
          <DistrictMap states={states} choropleth={choropleth} points={points} cadastral={cadastral}
            onDistrictClick={openDistrict} onParcelClick={openParcel} fitTo={fitTo} />
          {choropleth && <MapLegend breaks={choropleth.breaks} colors={choropleth.colors} />}
          {layerMeta?.method && <p className="mt-1 text-xs text-muted">Method: {layerMeta.method}</p>}
          <SpatialQueryCard />
        </div>

        <div className="space-y-4">
          {parcel && <ParcelPanel parcel={parcel} />}
          <DistrictPanel district={district} />
        </div>
      </div>
    </PageContainer>
  );
}
