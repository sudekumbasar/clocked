import { describe, expect, it } from "vitest";
import { INKS, categoryOrder, inkFor, postmarkDate, stampView, tiltFor } from "./stamp";
import type { Item } from "./types";

function item(id: string, category: string, rarity: Item["rarity"] = "rare", name = `Name ${id}`): Item {
  return { id, set: "main", name, category, kind: "place", rarity, fact: "", clue: "", location: "", access: "public", lat: null, lng: null };
}

const ITEMS = [item("A1", "First"), item("A2", "First"), item("B1", "Second"), item("C1", "Third"),
               item("D1", "Fourth"), item("E1", "Fifth")];

describe("postage stamp", () => {
  it("gives each category its own postmark ink, in collection order", () => {
    expect(categoryOrder(ITEMS)).toEqual(["First", "Second", "Third", "Fourth", "Fifth"]);
    expect(["First", "Second", "Third", "Fourth"].map((c) => inkFor(c, ITEMS))).toEqual(INKS);
    expect(inkFor("Fifth", ITEMS)).toBe(INKS[0]);
  });

  it("tilts the same item the same way every time, within 6 degrees", () => {
    expect(tiltFor("L08")).toBe(tiltFor("L08"));
    for (const id of ["S01", "L06", "W10", "B07", "F01", "S10"]) {
      expect(Math.abs(tiltFor(id))).toBeLessThanOrEqual(6);
    }
  });

  it("dates the postmark the way a post office does", () => {
    expect(postmarkDate("2026-10-10T12:00:00Z")).toBe("10 OCT 26");
  });

  it("shows place, category, date and rarity", () => {
    const view = stampView(item("B1", "Second", "legendary", "Tower Bridge"), ITEMS, "2026-10-10T12:00:00Z");
    expect(view).toMatchObject({ name: "Tower Bridge", category: "Second", postmarkDate: "10 OCT 26",
                                 stars: 3, ink: INKS[1] });
  });
});
