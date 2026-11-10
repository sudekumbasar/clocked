import { describe, expect, it } from "vitest";
import { hasBeenWelcomed, homeView, markWelcomed } from "./home";
import type { Discovery, Item } from "./types";

function item(id: string, category: string): Item {
  return { id, set: "main", name: `Name ${id}`, category, kind: "type", rarity: "rare", fact: "", clue: "",
           location: "", access: "public", lat: null, lng: null };
}
const ITEMS = [item("A", "One"), item("B", "One"), item("C", "Two"), item("D", "Two"), item("E", "Two")];
const found = (id: string, day: number): Discovery =>
  ({ item_id: id, first_found_at: `2026-10-0${day}T10:00:00Z`, photo: new Blob() });

describe("home", () => {
  it("counts stamps and shows progress per category", () => {
    const view = homeView(ITEMS, [found("A", 1), found("C", 2), found("D", 3)]);
    expect([view.found, view.total]).toEqual([3, 5]);
    expect(view.categories.map((c) => [c.category, c.found, c.total])).toEqual([["One", 1, 2], ["Two", 2, 3]]);
  });

  it("stacks the three latest stamps, oldest of them first", () => {
    const view = homeView(ITEMS, [found("A", 1), found("B", 4), found("C", 2), found("D", 3)]);
    expect(view.latest.map((d) => d.item_id)).toEqual(["C", "D", "B"]);
  });

  it("ignores stamps of items not in this version", () => {
    expect(homeView(ITEMS, [found("Z", 1)]).found).toBe(0);
  });

  it("shows a new player an empty stack", () => {
    expect(homeView(ITEMS, []).latest).toEqual([]);
  });

  it("remembers the welcome on this device, and survives blocked storage", () => {
    const store = new Map<string, string>();
    const storage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) };
    expect(hasBeenWelcomed(storage)).toBe(false);
    markWelcomed(storage);
    expect(hasBeenWelcomed(storage)).toBe(true);
    const blocked = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
    expect(hasBeenWelcomed(blocked)).toBe(false);
    expect(() => markWelcomed(blocked)).not.toThrow();
  });
});
