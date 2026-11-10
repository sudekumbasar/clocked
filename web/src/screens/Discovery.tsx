import type { DiscoveryView } from "../discovery";
import { PostageStamp } from "./PostageStamp";

interface Props {
  view: DiscoveryView;
  photo: Blob;
  onContinue: () => void;
}

/** PRODUCT.md, "Screens", 2: the photo becomes a stamp, then CLOCKED IT!, name, rarity, progress and the fact. */
export function DiscoveryScreen({ view, photo, onContinue }: Props) {
  return (
    <main class={`discovery paper ${view.isNew ? "is-new" : "is-known"}`}>
      <PostageStamp photo={photo} stamp={view.stamp} size="large" animate={view.isNew} alt={`Your photo of ${view.name}`} />

      <section class="discovery-text">
        <p class="kicker" style={{ color: view.stamp.ink }}>
          {view.headline}
          {view.firstFound && <span> · First found {view.firstFound}</span>}
        </p>
        <h1 class="item-title">{view.name}</h1>
        <p class="tags">
          <span class="tag rarity" style={{ background: view.stamp.ink }}>{view.rarity}</span>
          <span class="tag">{view.progress}</span>
        </p>
        {!view.isNew && <p class="added-note">Added to your {view.name} photos.</p>}
        <p class="fact">{view.fact}</p>
      </section>

      <button class="primary" onClick={onContinue}>
        Keep exploring
      </button>
    </main>
  );
}
