import { useEffect, useRef, useState } from "react";
import { Map, NavigationControl, Popup, ScaleControl, addProtocol, setWorkerUrl } from "maplibre-gl";
import { Protocol } from "pmtiles";
import { INDIA_BOUNDS } from "@/config/geography";

// Self-hosted worker (MapLibre 6 resolves it relative to its own URL, which bundlers rewrite).
setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
let protocolAdded = false;

const escapeHtml = (v: unknown) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

export type ChoroplethLayer = { data: any; valueKey?: string; breaks: number[]; colors: string[] };
export type PointLayer = { id: string; data: any; color: string; radiusKey?: string; label?: (p: any) => string };
export type CadastralLayer = { url: string; layer: string; bounds: number[]; show: boolean };

export type DistrictMapProps = {
  states?: any; choropleth?: ChoroplethLayer; points?: PointLayer[]; cadastral?: CadastralLayer | null;
  onDistrictClick?: (props: any) => void; onParcelClick?: (props: any) => void;
  fitTo?: number[] | null; height?: number;
};

// No third-party basemap: only Survey of India boundaries are drawn, so borders follow the official map.
const STYLE: any = {
  version: 8,
  sources: {},
  layers: [{ id: "bg", type: "background", paint: { "background-color": "#e9eef0" } }],
};

/** India district map: choropleth, point overlays and cadastral parcels over Survey of India boundaries. */
export default function DistrictMap({ states, choropleth, points = [], cadastral, onDistrictClick, onParcelClick, fitTo, height = 560 }: DistrictMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<Map | null>(null);
  const [ready, setReady] = useState(false);
  const handlers = useRef({ onDistrictClick, onParcelClick });
  const pointLabels = useRef<Record<string, (props: any) => string>>({});
  useEffect(() => { handlers.current = { onDistrictClick, onParcelClick }; }, [onDistrictClick, onParcelClick]);

  useEffect(() => {
    if (!container.current) return;
    if (!protocolAdded) {
      addProtocol("pmtiles", new Protocol().tile);
      protocolAdded = true;
    }
    const m = new Map({ container: container.current, style: STYLE, center: [82.8, 22.5], zoom: 3.6, minZoom: 3, maxZoom: 18,
      attributionControl: { compact: true, customAttribution: "Boundaries: Survey of India / LGD" } });
    m.addControl(new NavigationControl({ showCompass: false }), "top-right");
    m.addControl(new ScaleControl({}), "bottom-left");
    m.on("load", () => { m.fitBounds(INDIA_BOUNDS, { padding: 12, duration: 0 }); setReady(true); });
    // One hover popup for the whole map: the topmost feature under the cursor wins (a point is drawn above its
    // district), so a point's details never open on top of the district's.
    const hover = new Popup({ closeButton: false, closeOnClick: false, maxWidth: "260px", offset: 10 });
    const districtHtml = (p: any) => {
      const v = p.value === null || p.value === undefined || p.value === "null" ? "no data" : Number(p.value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
      return `<b>${escapeHtml(p.name)}</b><br/>${escapeHtml(p.state_name)}<br/>${v}${p.is_disputed === true || p.is_disputed === "true" ? "<br/><i>disputed area</i>" : ""}`;
    };
    m.on("mousemove", (e) => {
      const layers = [...Object.keys(pointLabels.current), "districts-fill"].filter((id) => m.getLayer(id));
      const f = layers.length ? m.queryRenderedFeatures(e.point, { layers })[0] : undefined;
      const html = !f ? null : f.layer.id === "districts-fill" ? districtHtml(f.properties) : pointLabels.current[f.layer.id]?.(f.properties);
      m.getCanvas().style.cursor = f ? "pointer" : "";
      if (html) hover.setLngLat(e.lngLat).setHTML(html).addTo(m);
      else hover.remove();
    });
    m.on("mouseout", () => { m.getCanvas().style.cursor = ""; hover.remove(); });
    m.on("click", "districts-fill", (e) => {
      if (m.getZoom() >= 11 && m.getLayer("parcels-fill")) return;
      const p = e.features?.[0]?.properties;
      if (p) handlers.current.onDistrictClick?.(p);
    });
    m.on("click", "parcels-fill", (e) => {
      const p = e.features?.[0]?.properties;
      if (p) handlers.current.onParcelClick?.(p);
    });
    map.current = m;
    return () => { m.remove(); map.current = null; };
  }, []);

  // district choropleth
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !choropleth) return;
    const src = m.getSource("districts") as any;
    if (src) src.setData(choropleth.data);
    else {
      m.addSource("districts", { type: "geojson", data: choropleth.data });
      m.addLayer({ id: "districts-fill", type: "fill", source: "districts", paint: { "fill-opacity": 0.85 } }, m.getLayer("states-line") ? "states-line" : undefined);
      m.addLayer({ id: "districts-line", type: "line", source: "districts", paint: { "line-color": "#ffffff", "line-width": 0.4 } }, m.getLayer("states-line") ? "states-line" : undefined);
    }
    const key = choropleth.valueKey ?? "value";
    const steps: any[] = ["step", ["to-number", ["get", key]], choropleth.colors[0]];
    choropleth.breaks.forEach((b, i) => steps.push(b, choropleth.colors[i + 1]));
    m.setPaintProperty("districts-fill", "fill-color", ["case", ["==", ["get", key], null], "#d6d3cc", steps] as any);
  }, [choropleth, ready]);

  // state outlines on top
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !states || m.getSource("states")) return;
    m.addSource("states", { type: "geojson", data: states });
    m.addLayer({ id: "states-line", type: "line", source: "states", paint: { "line-color": "#334155", "line-width": 0.9 } });
  }, [states, ready]);

  // point layers
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const want = new Set(points.map((p) => p.id));
    for (const l of m.getStyle().layers ?? []) {
      if (l.id.startsWith("pts-") && !want.has(l.id.slice(4))) { m.removeLayer(l.id); m.removeSource(l.id); delete pointLabels.current[l.id]; }
    }
    for (const p of points) {
      const id = "pts-" + p.id;
      if (p.label) pointLabels.current[id] = p.label;
      if (m.getSource(id)) { (m.getSource(id) as any).setData(p.data); continue; }
      m.addSource(id, { type: "geojson", data: p.data });
      m.addLayer({ id, type: "circle", source: id, paint: {
        "circle-color": p.color, "circle-opacity": 0.75, "circle-stroke-color": "#fff", "circle-stroke-width": 0.6,
        "circle-radius": p.radiusKey ? ["interpolate", ["linear"], ["sqrt", ["to-number", ["get", p.radiusKey]]], 1, 2.5, 5, 11] : 2.5 } });
    }
  }, [points, ready]);

  // cadastral parcels (PMTiles)
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !cadastral) return;
    const has = !!m.getSource("parcels");
    if (cadastral.show && !has) {
      m.addSource("parcels", { type: "vector", url: `pmtiles://${window.location.origin}${cadastral.url}` });
      m.addLayer({ id: "parcels-fill", type: "fill", source: "parcels", "source-layer": cadastral.layer, minzoom: 11,
        paint: { "fill-color": "#f5d08a", "fill-opacity": 0.35 } });
      m.addLayer({ id: "parcels-line", type: "line", source: "parcels", "source-layer": cadastral.layer, minzoom: 11,
        paint: { "line-color": "#7c4a03", "line-width": 0.6 } });
    }
    if (!cadastral.show && has) {
      m.removeLayer("parcels-line"); m.removeLayer("parcels-fill"); m.removeSource("parcels");
    }
  }, [cadastral, ready]);

  useEffect(() => {
    if (map.current && ready && fitTo) map.current.fitBounds(fitTo as any, { padding: 30, duration: 800 });
  }, [fitTo, ready]);

  return <div ref={container} style={{ height, width: "100%" }} className="overflow-hidden rounded-md border border-line" />;
}

