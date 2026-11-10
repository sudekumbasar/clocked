/** What the collection and category pages show (PRODUCT.md, "Screens", 3). Pure functions, so they are tested. */

import type { Discovery, Item } from "./types";

export interface CollectionEntry {
  item: Item;
  discovery: Discovery | null;
}

export interface CollectionSection {
  category: string;
  found: number;
  total: number;
  entries: CollectionEntry[];
}

/** Sections in CSV order of categories; items in CSV order within each. */
export function groupCollection(items: Item[], discoveries: Discovery[]): CollectionSection[] {
  const byId = new Map(discoveries.map((d) => [d.item_id, d]));
  const sections = new Map<string, CollectionSection>();
  for (const item of items) {
    let section = sections.get(item.category);
    if (!section) {
      section = { category: item.category, found: 0, total: 0, entries: [] };
      sections.set(item.category, section);
    }
    const discovery = byId.get(item.id) ?? null;
    section.entries.push({ item, discovery });
    section.total += 1;
    if (discovery) section.found += 1;
  }
  return [...sections.values()];
}

/** How many stamps a category's fan shows on the collection page. */
export const FAN_SIZE = 3;

/** The stamps on top of a category's fan: the most recently found, oldest of them first. */
export function fanEntries(section: CollectionSection): CollectionEntry[] {
  return section.entries
    .filter((entry) => entry.discovery)
    .sort((a, b) => b.discovery!.first_found_at.localeCompare(a.discovery!.first_found_at))
    .slice(0, FAN_SIZE)
    .reverse();
}

export interface LockedLabel {
  kicker: string;
  title: string;
  detail: string;
}

/**
 * An empty space in a category's album. Type items ("spot it") show their number
 * and name; place items ("find it") show only their clue and rarity, so the place
 * stays a secret.
 */
export function lockedLabel(item: Item, position: number): LockedLabel {
  if (item.kind === "type") {
    return { kicker: `Nº ${String(position).padStart(2, "0")}`, title: item.name, detail: item.rarity };
  }
  return { kicker: "Clue", title: item.clue || "Hidden place", detail: item.rarity };
}
