/**
 * Test mode (PRODUCT.md, "Testing without being there"). Exists only in development
 * builds: main.tsx imports this file only when VITE_TEST_MODE is set, so the public
 * build does not contain it.
 */

import { useRef } from "preact/hooks";
import { toJpeg } from "../camera";
import { resetCollection } from "../store";
import type { Item, PlayerLocation } from "../types";

interface Props {
  busy: boolean;
  items: Item[];
  pretendId: string | null;
  onPhoto: (photo: Blob) => void;
  onReset: () => void;
  /** "Pretend I am here": stand at a place item's coordinates, or null for the phone's location. */
  onPretend: (itemId: string | null, location: PlayerLocation | null) => void;
}

/** A pretended position is as precise as a good phone fix outdoors. */
const PRETEND_ACCURACY_M = 10;

export default function TestTools({ busy, items, pretendId, onPhoto, onReset, onPretend }: Props) {
  const input = useRef<HTMLInputElement>(null);

  async function pick(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    const bitmap = await createImageBitmap(file);
    onPhoto(await toJpeg(bitmap, bitmap.width, bitmap.height));
    input.current!.value = "";
  }

  async function reset() {
    if (!confirm("Test mode: empty the collection on this device?")) return;
    await resetCollection();
    onReset();
  }

  function pretend(event: Event) {
    const id = (event.target as HTMLSelectElement).value;
    const item = items.find((i) => i.id === id && i.lat !== null && i.lng !== null);
    onPretend(item ? item.id : null, item ? { lat: item.lat!, lng: item.lng!, accuracy_m: PRETEND_ACCURACY_M } : null);
  }

  const places = items.filter((i) => i.kind === "place" && i.lat !== null);

  return (
    <div class="test-tools">
      <label class="pill pretend">
        <span>Pretend I am here</span>
        <select value={pretendId ?? ""} onChange={pretend} aria-label="Pretend I am here">
          <option value="">Real location</option>
          {places.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <span class="test-label">Test mode</span>
      <label class="pill">
        Saved photo
        <input ref={input} type="file" accept="image/*" hidden disabled={busy} onChange={pick} />
      </label>
      <button class="pill" onClick={reset}>
        Reset
      </button>
    </div>
  );
}
