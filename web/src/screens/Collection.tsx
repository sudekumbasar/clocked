import { useMemo } from "preact/hooks";
import { fanEntries, groupCollection } from "../collection";
import { inkFor, stampView } from "../stamp";
import type { Discovery, Item } from "../types";
import { PostageStamp } from "./PostageStamp";

interface Props {
  items: Item[];
  discoveries: Discovery[];
  onBack: () => void;
  onOpenCategory: (category: string) => void;
}

/** PRODUCT.md, "Screens", 3: one fan of stamps per category; tap it for the category's album page. */
export function CollectionScreen({ items, discoveries, onBack, onOpenCategory }: Props) {
  const sections = useMemo(() => groupCollection(items, discoveries), [items, discoveries]);
  const found = sections.reduce((n, s) => n + s.found, 0);

  return (
    <main class="collection paper">
      <button class="back-link" onClick={onBack}>
        ← Home
      </button>
      <header class="page-head">
        <h1>My stamps</h1>
        <span class="count">
          {found} of {items.length}
        </span>
      </header>

      {sections.map((section) => {
        const ink = inkFor(section.category, items);
        const fan = fanEntries(section);
        const toFind = section.total - section.found;
        return (
          <button
            class="shelf"
            key={section.category}
            style={{ "--cat-ink": ink }}
            onClick={() => onOpenCategory(section.category)}
            aria-label={`${section.category}: ${section.found} of ${section.total} found`}
          >
            <span class="shelf-head">
              <span class="shelf-title">{section.category}</span>
              <span class="count">
                {section.found} / {section.total}
              </span>
            </span>
            <span class="fan">
              {fan.map(({ item, discovery }, index) => (
                <span class="fan-card" key={item.id} style={{ "--i": index }}>
                  <PostageStamp photo={discovery!.photo} stamp={stampView(item, items, discovery!.first_found_at)} size="small" />
                </span>
              ))}
              <span class="to-find">
                {toFind > 0 ? (
                  <>
                    <b>{toFind}</b> to find
                  </>
                ) : (
                  <b>Complete</b>
                )}
              </span>
            </span>
          </button>
        );
      })}
    </main>
  );
}
