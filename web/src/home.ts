/** What the home screen shows (PRODUCT.md, "Screens", 0). Pure functions, so they are tested. */

import { groupCollection } from "./collection";
import { inkFor } from "./stamp";
import type { Discovery, Item } from "./types";

export interface HomeCategory {
  category: string;
  found: number;
  total: number;
  ink: string;
}

export interface HomeView {
  found: number;
  total: number;
  /** The latest stamps for the small stack, oldest of them first; empty for a new player. */
  latest: Discovery[];
  categories: HomeCategory[];
}

export const STACK_SIZE = 3;

export function homeView(items: Item[], discoveries: Discovery[]): HomeView {
  const sections = groupCollection(items, discoveries);
  const known = new Set(items.map((item) => item.id));
  const mine = discoveries.filter((d) => known.has(d.item_id));
  return {
    found: mine.length,
    total: items.length,
    latest: [...mine].sort((a, b) => b.first_found_at.localeCompare(a.first_found_at)).slice(0, STACK_SIZE).reverse(),
    categories: sections.map((s) => ({ category: s.category, found: s.found, total: s.total, ink: inkFor(s.category, items) })),
  };
}

const WELCOMED_KEY = "clocked.welcomed";

/** Whether this device has seen the first-open welcome. A browser that blocks storage sees it again. */
export function hasBeenWelcomed(storage: Pick<Storage, "getItem"> | undefined = safeStorage()): boolean {
  try {
    return storage?.getItem(WELCOMED_KEY) === "1";
  } catch {
    return false;
  }
}

export function markWelcomed(storage: Pick<Storage, "setItem"> | undefined = safeStorage()): void {
  try {
    storage?.setItem(WELCOMED_KEY, "1");
  } catch {
    // Storage blocked: the welcome shows again next time, which is harmless.
  }
}

function safeStorage(): Storage | undefined {
  try {
    return typeof localStorage === "undefined" ? undefined : localStorage;
  } catch {
    return undefined;
  }
}
