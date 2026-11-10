import { useEffect, useState } from "preact/hooks";
import { formatDate } from "../discovery";
import { stampView } from "../stamp";
import { deletePhoto, listPhotos, setCover } from "../store";
import type { Discovery, Item, ItemPhoto } from "../types";
import { PostageStamp, usePhotoUrl } from "./PostageStamp";

interface Props {
  item: Item;
  items: Item[];
  discovery: Discovery;
  onBack: () => void;
  /** The stamp changed: the collection should be read again. */
  onChanged: () => void;
}

function Thumb({ photo, isStamp, onOpen }: { photo: ItemPhoto; isStamp: boolean; onOpen: () => void }) {
  const url = usePhotoUrl(photo.photo);
  return (
    <button class={`thumb ${isStamp ? "is-stamp" : ""}`} onClick={onOpen} aria-label={`Photo from ${formatDate(photo.taken_at)}`}>
      <img src={url} alt="" />
      {isStamp && <span class="thumb-badge">Stamp</span>}
    </button>
  );
}

function Viewer({ photo, isStamp, onClose, onMakeStamp, onDelete }: {
  photo: ItemPhoto; isStamp: boolean; onClose: () => void; onMakeStamp: () => void; onDelete: () => void;
}) {
  const url = usePhotoUrl(photo.photo);
  const [confirming, setConfirming] = useState(false);
  return (
    <div class="viewer" role="dialog" aria-label="Photo">
      <img src={url} alt="" />
      <p class="viewer-date">Taken {formatDate(photo.taken_at)}</p>
      {isStamp ? (
        <p class="viewer-note">This photo is your stamp.</p>
      ) : confirming ? (
        <div class="viewer-actions">
          <button class="secondary danger" onClick={onDelete}>Delete this photo</button>
          <button class="secondary" onClick={() => setConfirming(false)}>Keep it</button>
        </div>
      ) : (
        <div class="viewer-actions">
          <button class="primary" onClick={onMakeStamp}>Make this my stamp</button>
          <button class="secondary" onClick={() => setConfirming(true)}>Delete</button>
        </div>
      )}
      <button class="back-link viewer-close" onClick={onClose}>Close</button>
    </div>
  );
}

/** PRODUCT.md, "Screens", 4: the stamp, every photo of the item, the fact, the date, and for places the address. */
export function ItemDetailScreen({ item, items, discovery, onBack, onChanged }: Props) {
  const [photos, setPhotos] = useState<ItemPhoto[]>([]);
  const [open, setOpen] = useState<ItemPhoto | null>(null);
  const [error, setError] = useState<string | null>(null);
  const stamp = stampView(item, items, discovery.first_found_at);

  async function reload() {
    setPhotos(await listPhotos(item.id));
  }
  useEffect(() => {
    reload();
  }, [item.id, discovery.cover_id]);

  async function act(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      setOpen(null);
      await reload();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <main class="detail paper">
      <button class="back-link" onClick={onBack}>
        ← {item.category}
      </button>

      <PostageStamp photo={discovery.photo} stamp={stamp} size="large" alt={`Your photo of ${item.name}`} />

      <section class="discovery-text">
        <p class="kicker" style={{ color: stamp.ink }}>
          Found {formatDate(discovery.first_found_at)}
        </p>
        <h1 class="item-title">{item.name}</h1>
        <p class="tags">
          <span class="tag rarity" style={{ background: stamp.ink }}>{item.rarity}</span>
          <span class="tag">{item.category}</span>
        </p>
        {item.kind === "place" && item.location && <p class="address">{item.location}</p>}
        <p class="fact">{item.fact}</p>

        {photos.length > 1 && (
          <section class="photo-roll">
            <h2 class="mono-label">Your photos · {photos.length}</h2>
            <div class="thumbs">
              {photos.map((p) => (
                <Thumb key={p.id} photo={p} isStamp={p.id === discovery.cover_id} onOpen={() => setOpen(p)} />
              ))}
            </div>
          </section>
        )}
        {error && <p class="home-message" role="alert">{error}</p>}
      </section>

      {open && (
        <Viewer
          photo={open}
          isStamp={open.id === discovery.cover_id}
          onClose={() => setOpen(null)}
          onMakeStamp={() => act(() => setCover(item.id, open.id))}
          onDelete={() => act(() => deletePhoto(item.id, open.id))}
        />
      )}
    </main>
  );
}
