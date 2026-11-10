import { describe, expect, it } from "vitest";
import { fanEntries, groupCollection, lockedLabel } from "./collection";
import type { Discovery, Item } from "./types";

function item(id: string, category: string, kind: Item["kind"] = "type", clue = ""): Item {
  return { id, set: "main", name: `Name ${id}`, category, kind, rarity: "rare", fact: "", clue,
           location: kind === "place" ? `Address ${id}` : "", access: "public", lat: null, lng: null };
}

const ITEMS = [item("S01", "London Icons"), item("S08", "London Icons", "place", "Album cover"),
               item("T01", "London Icons"), item("B01", "Pub Crawl", "place", "Flowers")];
const found = (id: string, day = 9): Discovery =>
  ({ item_id: id, first_found_at: `2026-10-0${day}T10:00:00Z`, photo: new Blob() });

describe("collection", () => {
  it("groups by category in CSV order, with progress", () => {
    const sections = groupCollection(ITEMS, [found("S08"), found("B01")]);
    expect(sections.map((s) => [s.category, s.found, s.total])).toEqual([
      ["London Icons", 1, 3], ["Pub Crawl", 1, 1],
    ]);
    expect(sections[0].entries.map((e) => [e.item.id, e.discovery !== null])).toEqual([
      ["S01", false], ["S08", true], ["T01", false],
    ]);
  });

  it("ignores discoveries of items not in this version", () => {
    const sections = groupCollection(ITEMS, [found("C04")]);
    expect(sections.reduce((n, s) => n + s.found, 0)).toBe(0);
  });

  it("fans the three most recent stamps of a category, oldest of them first", () => {
    const many = [item("A", "X"), item("B", "X"), item("C", "X"), item("D", "X")];
    const [section] = groupCollection(many, [found("A", 1), found("B", 4), found("C", 2), found("D", 3)]);
    expect(fanEntries(section).map((e) => e.item.id)).toEqual(["C", "D", "B"]);
  });

  it("shows an empty space for a type item by number and name", () => {
    expect(lockedLabel(ITEMS[0], 1)).toEqual({ kicker: "Nº 01", title: "Name S01", detail: "rare" });
  });

  it("never shows a place item's name in its empty space, only its clue", () => {
    const label = lockedLabel(ITEMS[3], 4);
    expect(label).toEqual({ kicker: "Clue", title: "Flowers", detail: "rare" });
    expect(JSON.stringify(label)).not.toContain("Name B01");
  });
});
