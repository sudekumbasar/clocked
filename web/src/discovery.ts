/** What the discovery screen shows (PRODUCT.md, "Screens", 2). Pure functions, so they are tested. */

import { stampView, type StampView } from "./stamp";
import type { Item } from "./types";

export const CLOCKED_IT = "CLOCKED IT!";
export const ALREADY_DISCOVERED = "Already discovered";

export interface DiscoveryView {
  headline: string;
  name: string;
  rarity: Item["rarity"];
  category: string;
  progress: string; // "London Icons 4 / 10"
  found: number;
  total: number;
  fact: string;
  firstFound: string | null; // only for an item the player already had
  isNew: boolean;
  stamp: StampView; // dated the first time the item was found
}

export function categoryProgress(items: Item[], discoveredIds: Set<string>, category: string) {
  const inCategory = items.filter((item) => item.category === category);
  const found = inCategory.filter((item) => discoveredIds.has(item.id)).length;
  return { found, total: inCategory.length };
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}

export function discoveryView(
  item: Item,
  items: Item[],
  discoveredIds: Set<string>,
  isNew: boolean,
  firstFoundAt: string,
): DiscoveryView {
  const { found, total } = categoryProgress(items, discoveredIds, item.category);
  return {
    headline: isNew ? CLOCKED_IT : ALREADY_DISCOVERED,
    name: item.name,
    rarity: item.rarity,
    category: item.category,
    progress: `${item.category} ${found} / ${total}`,
    found,
    total,
    fact: item.fact,
    firstFound: isNew ? null : formatDate(firstFoundAt),
    isNew,
    stamp: stampView(item, items, firstFoundAt),
  };
}
