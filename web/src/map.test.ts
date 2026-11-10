import { describe, expect, it } from "vitest";
import { mapMarkers, nearestToFind, ticketNote } from "./map";
import type { Item } from "./types";

function item(id: string, kind: Item["kind"], extra: Partial<Item> = {}): Item {
  return { id, set: "main", name: `Name ${id}`, category: "London Icons", kind, rarity: "rare", fact: "",
           clue: kind === "place" ? "Lifts" : "", location: "", access: "public",
           lat: kind === "place" ? 51.5056 : null, lng: kind === "place" ? -0.0753 : null, ...extra };
}

const ITEMS = [item("S04", "type"), item("L08", "place"), item("F07", "place", { access: "paid", clue: "Whale" })];

describe("map", () => {
  it("shows places only, never type items", () => {
    expect(mapMarkers(ITEMS, new Set(), null).map((m) => m.id)).toEqual(["L08", "F07"]);
  });

  it("keeps an undiscovered place's name hidden, showing its clue", () => {
    const [marker] = mapMarkers(ITEMS, new Set(), null);
    expect(marker.title).toBe("Clue: Lifts");
    expect(JSON.stringify(marker)).not.toContain("Name L08");
  });

  it("shows a discovered place by name", () => {
    const [marker] = mapMarkers(ITEMS, new Set(["L08"]), null);
    expect([marker.found, marker.title]).toEqual([true, "Name L08"]);
  });

  it("gives the distance only when the player's location is known", () => {
    expect(mapMarkers(ITEMS, new Set(), null)[0].distance).toBeNull();
    const here = { lat: 51.5056, lng: -0.0753 + 0.0012, accuracy_m: 10 };
    expect(mapMarkers(ITEMS, new Set(), here)[0].distance).toBe("80 m away");
  });

  it("marks places in a paid area", () => {
    expect(mapMarkers(ITEMS, new Set(), null)[1].ticket).toBe("Ticket needed");
    expect([ticketNote("public"), ticketNote("mixed")]).toEqual([null, "Ticket needed for part of it"]);
  });

  it("finds the nearest place still to find", () => {
    const items = [item("A", "place", { lat: 51.50, lng: -0.10 }), item("B", "place", { lat: 51.51, lng: -0.12 }),
                   item("C", "place", { lat: 51.505, lng: -0.11 })];
    const here = { lat: 51.505, lng: -0.111, accuracy_m: 10 };
    expect(nearestToFind(mapMarkers(items, new Set(), here), here)?.id).toBe("C");
    expect(nearestToFind(mapMarkers(items, new Set(["C"]), here), here)?.id).toBe("B"); // about 840 m, against 940 m for A
  });

  it("has no nearest place without a location, or when everything is found", () => {
    const here = { lat: 51.5, lng: -0.1, accuracy_m: 10 };
    expect(nearestToFind(mapMarkers(ITEMS, new Set(), null), null)).toBeNull();
    expect(nearestToFind(mapMarkers(ITEMS, new Set(["L08", "F07"]), here), here)).toBeNull();
  });
});
