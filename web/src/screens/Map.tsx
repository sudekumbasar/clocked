import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { mapMarkers, nearestToFind, type MapMarker } from "../map";
import type { Discovery, Item, PlayerLocation } from "../types";

interface Props {
  items: Item[];
  discoveries: Discovery[];
  /** Test mode only: a pretended location instead of the phone's. */
  pretend: PlayerLocation | null;
  onBack: () => void;
}

const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function markerIcon(marker: MapMarker): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<span class="map-pin ${marker.found ? "found" : ""}" style="--pin:${marker.ink}">${marker.found ? "✓" : "?"}</span>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  });
}

/** PRODUCT.md, "Screens", 5: undiscovered places as "?" markers; the name stays hidden until found. */
export default function MapScreen({ items, discoveries, pretend, onBack }: Props) {
  const element = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const markerLayer = useRef<L.LayerGroup | null>(null);
  const youLayer = useRef<L.LayerGroup | null>(null);
  const [phone, setPhone] = useState<PlayerLocation | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const here = pretend ?? phone;

  const markers = useMemo(
    () => mapMarkers(items, new Set(discoveries.map((d) => d.item_id)), here),
    [items, discoveries, here],
  );

  // The phone's location while the map is open (not when test mode pretends one).
  useEffect(() => {
    if (pretend || !navigator.geolocation) return;
    const watch = navigator.geolocation.watchPosition(
      (p) => setPhone({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy_m: p.coords.accuracy }),
      () => setPhone(null),
      { enableHighAccuracy: true, maximumAge: 30_000 },
    );
    return () => navigator.geolocation.clearWatch(watch);
  }, [pretend]);

  // Create the map once, framed on every place in the collection.
  useEffect(() => {
    const m = L.map(element.current!, { zoomControl: false, attributionControl: true });
    m.on("click", () => setSelectedId(null));
    L.tileLayer(TILES, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(m);
    L.control.zoom({ position: "bottomright" }).addTo(m);
    markerLayer.current = L.layerGroup().addTo(m);
    youLayer.current = L.layerGroup().addTo(m);
    const places = items.filter((i) => i.lat !== null && i.lng !== null).map((i) => [i.lat!, i.lng!] as [number, number]);
    if (places.length) m.fitBounds(L.latLngBounds(places), { padding: [30, 30] });
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
    };
  }, [items]);

  useEffect(() => {
    const layer = markerLayer.current;
    if (!layer) return;
    layer.clearLayers();
    for (const marker of markers) {
      L.marker([marker.lat, marker.lng], { icon: markerIcon(marker), title: marker.title, keyboard: true })
        .on("click", () => setSelectedId(marker.id))
        .addTo(layer);
    }
  }, [markers]);

  // The first time we know where the player is, open the map around them.
  const centred = useRef(false);
  useEffect(() => {
    if (here && map.current && !centred.current) {
      centred.current = true;
      map.current.setView([here.lat, here.lng], 15);
    }
  }, [here]);

  useEffect(() => {
    const layer = youLayer.current;
    if (!layer) return;
    layer.clearLayers();
    if (here) {
      L.circle([here.lat, here.lng], { radius: here.accuracy_m, className: "you-accuracy" }).addTo(layer);
      L.circleMarker([here.lat, here.lng], { radius: 7, className: "you-dot" }).addTo(layer);
    }
  }, [here]);

  function centreOnMe() {
    if (here && map.current) map.current.setView([here.lat, here.lng], 16);
  }

  const toFind = markers.filter((m) => !m.found).length;
  const selected = markers.find((m) => m.id === selectedId) ?? null;
  const nearest = nearestToFind(markers, here);
  const card = selected ?? nearest;

  return (
    <main class="map-screen">
      <div ref={element} class="map" />
      <header class="map-bar">
        <button class="pill" onClick={onBack}>
          ← Home
        </button>
        <span class="pill map-count">{toFind} to find</span>
      </header>
      <footer class="map-foot">
        {here && (
          <button class="pill map-me" onClick={centreOnMe}>
            Where am I
          </button>
        )}
        {card ? (
          <section class="map-card" aria-live="polite">
            <span class="map-card-head">
              <span class="mono-label">{selected ? `${card.category} · ${card.rarity}` : "Nearest to find"}</span>
              {card.distance && <span class="map-card-distance" style={{ color: card.ink }}>{card.distance}</span>}
            </span>
            <b>{card.title}</b>
            <span class="map-card-meta">{selected ? (card.found ? "In your stamps" : "Not found yet") : `${card.category} · ${card.rarity}`}</span>
            {card.ticket && <span class="map-card-ticket">{card.ticket}</span>}
          </section>
        ) : (
          <section class="map-card">
            <b>Tap a ? for its clue</b>
          </section>
        )}
      </footer>
    </main>
  );
}
