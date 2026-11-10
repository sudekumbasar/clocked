/**
 * The postage stamp a discovery becomes (PRODUCT.md, "Stamp look"): the player's
 * photo with a perforated edge, the place and its category printed below it, and a
 * London postmark dated the day it was first found. Pure functions, so they are
 * tested. Nothing here names a category: its ink comes from the category's position
 * in the collection.
 */

import type { Item } from "./types";

/** Postmark inks, one per category in collection order; a fifth category reuses the first. */
export const INKS = ["#c9452f", "#2f6a59", "#74497f", "#2e4c86"];

export interface StampView {
  name: string;
  category: string;
  postmarkDate: string; // "10 OCT 26"
  stars: number; // common 1, rare 2, legendary 3
  ink: string;
  tilt: number; // degrees, the same every time for the same item
}

const STARS: Record<Item["rarity"], number> = { common: 1, rare: 2, legendary: 3 };

/** Categories in the order the collection shows them (the CSV's order). */
export function categoryOrder(items: Item[]): string[] {
  return [...new Set(items.map((item) => item.category))];
}

export function inkFor(category: string, items: Item[]): string {
  const index = categoryOrder(items).indexOf(category);
  return INKS[Math.max(index, 0) % INKS.length];
}

/** A small tilt between -6 and 6 degrees that depends only on the item's id. */
export function tiltFor(itemId: string): number {
  let hash = 0;
  for (const char of itemId) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return (hash % 13) - 6;
}

/** The postmark's date: "10 OCT 26". */
export function postmarkDate(iso: string): string {
  return new Date(iso)
    .toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "2-digit" })
    .toUpperCase();
}

export function stampView(item: Item, items: Item[], foundAt: string): StampView {
  return {
    name: item.name,
    category: item.category,
    postmarkDate: postmarkDate(foundAt),
    stars: STARS[item.rarity],
    ink: inkFor(item.category, items),
    tilt: tiltFor(item.id),
  };
}
