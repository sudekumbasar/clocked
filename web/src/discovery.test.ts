import { describe, expect, it } from "vitest";
import { ALREADY_DISCOVERED, CLOCKED_IT, categoryProgress, discoveryView, formatDate } from "./discovery";
import type { Item } from "./types";

function item(id: string, category: string, rarity: Item["rarity"] = "common"): Item {
  return { id, set: "main", name: `Item ${id}`, category, kind: "type", rarity, fact: `Fact ${id}`,
           clue: "", location: "", access: "public", lat: null, lng: null };
}

const ITEMS = [item("S01", "Street Icons"), item("S02", "Street Icons"), item("S03", "Street Icons", "rare"),
               item("T01", "Transport")];

describe("discovery screen", () => {
  it("counts progress within the item's category only", () => {
    expect(categoryProgress(ITEMS, new Set(["S01", "S03", "T01"]), "Street Icons")).toEqual({ found: 2, total: 3 });
  });

  it("shows CLOCKED IT, name, rarity, progress and fact for a new item", () => {
    const view = discoveryView(ITEMS[2], ITEMS, new Set(["S01", "S03"]), true, "2026-10-07T10:00:00Z");
    expect(view).toMatchObject({ headline: CLOCKED_IT, name: "Item S03", rarity: "rare",
                                 progress: "Street Icons 2 / 3", fact: "Fact S03", firstFound: null });
  });

  it("progress has no city prefix", () => {
    const view = discoveryView(ITEMS[0], ITEMS, new Set(["S01"]), true, "2026-10-07T10:00:00Z");
    expect(view.progress).toBe("Street Icons 1 / 3");
  });

  it("shows Already discovered and the first date for a known item", () => {
    const view = discoveryView(ITEMS[0], ITEMS, new Set(["S01"]), false, "2026-10-01T09:30:00Z");
    expect(view.headline).toBe(ALREADY_DISCOVERED);
    expect(view.firstFound).toBe("1 October 2026");
  });

  it("formats dates the British way", () => {
    expect(formatDate("2026-12-25T12:00:00Z")).toBe("25 December 2026");
  });
});
