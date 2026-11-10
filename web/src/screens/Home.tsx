import { useMemo } from "preact/hooks";
import { homeView } from "../home";
import { formatDistance, distanceM } from "../location";
import type { MapMarker } from "../map";
import { stampView } from "../stamp";
import type { Discovery, Item, PlayerLocation } from "../types";
import { PostageStamp } from "./PostageStamp";

interface Props {
  items: Item[];
  discoveries: Discovery[];
  nearest: MapMarker | null;
  here: PlayerLocation | null;
  message: string | null;
  onTakePhoto: () => void;
  onOpenCollection: () => void;
  onOpenMap: () => void;
}

function CameraIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
      <circle cx="12" cy="13" r="3.5" />
    </svg>
  );
}

/** PRODUCT.md, "Screens", 0: the screen the app opens on. */
export function HomeScreen({ items, discoveries, nearest, here, message, onTakePhoto, onOpenCollection, onOpenMap }: Props) {
  const view = useMemo(() => homeView(items, discoveries), [items, discoveries]);
  const byId = useMemo(() => new Map(items.map((item) => [item.id, item])), [items]);

  return (
    <main class="home paper">
      <header class="home-head">
        <span class="mono-label">London</span>
        <h1 class="home-title">Clocked</h1>
        <p class="home-sub">Your London, in stamps</p>
      </header>

      <section class="home-hero">
        <div class="stack" onClick={view.latest.length ? onOpenCollection : undefined}>
          {view.latest.length === 0 ? (
            <div class="first-space">Your first stamp goes here</div>
          ) : (
            view.latest.map((discovery, index) => {
              const item = byId.get(discovery.item_id)!;
              return (
                <span class="stack-card" key={discovery.item_id} style={{ "--i": index }}>
                  <PostageStamp photo={discovery.photo} stamp={stampView(item, items, discovery.first_found_at)} size="small" />
                </span>
              );
            })
          )}
        </div>
        <p class="home-count">
          <b>{view.found}</b>
          <span>of {view.total} stamps</span>
        </p>
      </section>

      <ul class="home-cats">
        {view.categories.map((c) => (
          <li key={c.category}>
            <span class="home-cat-name">{c.category}</span>
            <span class="count">
              {c.found}/{c.total}
            </span>
            <span class="home-bar">
              <i style={{ width: `${(100 * c.found) / c.total}%`, background: c.ink }} />
            </span>
          </li>
        ))}
      </ul>

      {nearest && here && (
        <button class="nearest" onClick={onOpenMap}>
          <span>
            <span class="mono-label">Nearest to find</span>
            <b>{nearest.title}</b>
          </span>
          <em style={{ color: nearest.ink }}>{formatDistance(distanceM(here, nearest))} →</em>
        </button>
      )}

      {message && (
        <p class="home-message" role="status">
          {message}
        </p>
      )}

      <div class="home-actions">
        <button class="primary shoot" onClick={onTakePhoto}>
          <CameraIcon /> Take a photo
        </button>
        <div class="home-links">
          <button class="secondary" onClick={onOpenCollection}>
            My stamps
          </button>
          <button class="secondary" onClick={onOpenMap}>
            Map
          </button>
        </div>
      </div>
    </main>
  );
}
