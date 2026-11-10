import { useMemo } from "preact/hooks";
import { groupCollection, lockedLabel } from "../collection";
import { inkFor, stampView } from "../stamp";
import type { Discovery, Item } from "../types";
import { PostageStamp } from "./PostageStamp";

interface Props {
  category: string;
  items: Item[];
  discoveries: Discovery[];
  onBack: () => void;
  onOpenItem: (itemId: string) => void;
}

/** One category's album page: a stamp for each find, an empty space with a number or clue for the rest. */
export function CategoryScreen({ category, items, discoveries, onBack, onOpenItem }: Props) {
  const section = useMemo(
    () => groupCollection(items, discoveries).find((s) => s.category === category),
    [category, items, discoveries],
  );
  if (!section) return null;
  const ink = inkFor(category, items);

  return (
    <main class="category-page paper" style={{ "--cat-ink": ink }}>
      <button class="back-link" onClick={onBack}>
        ← My stamps
      </button>
      <header class="page-head">
        <h1>{category}</h1>
        <span class="count">
          {section.found} / {section.total}
        </span>
      </header>
      <div class="bar">
        <div class="fill" style={{ width: `${(100 * section.found) / section.total}%` }} />
      </div>

      <ul class="album">
        {section.entries.map(({ item, discovery }, index) => (
          <li key={item.id}>
            {discovery ? (
              <button class="album-stamp" onClick={() => onOpenItem(item.id)} aria-label={item.name}>
                <PostageStamp photo={discovery.photo} stamp={stampView(item, items, discovery.first_found_at)} size="small" />
              </button>
            ) : (
              <div class="album-space" aria-label="Not found yet">
                <span class="space-kicker">{lockedLabel(item, index + 1).kicker}</span>
                <span class="space-title">{lockedLabel(item, index + 1).title}</span>
                <span class="space-detail">{lockedLabel(item, index + 1).detail}</span>
              </div>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}
