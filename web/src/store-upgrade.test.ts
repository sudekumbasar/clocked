// The upgrade from the first version of the collection, which kept one photo per item.
// Losing the collection is the worst bug this app can have (PRODUCT.md).
import "fake-indexeddb/auto";
import { IDBFactory } from "fake-indexeddb";
import { openDB } from "idb";
import { describe, expect, it, vi } from "vitest";

describe("upgrading a collection from version 1", () => {
  it("keeps every stamp and turns it into the item's first photo", async () => {
    globalThis.indexedDB = new IDBFactory();
    const old = await openDB("clocked", 1, {
      upgrade(database) {
        database.createObjectStore("discoveries", { keyPath: "item_id" });
      },
    });
    await old.put("discoveries", { item_id: "L07", first_found_at: "2026-10-30T15:25:31.000Z", photo: new Blob(["eye"]) });
    await old.put("discoveries", { item_id: "S02", first_found_at: "2026-10-30T14:34:51.000Z", photo: new Blob(["box"]) });
    old.close();

    vi.resetModules();
    const store = await import("./store");
    const discoveries = await store.listDiscoveries();
    expect(discoveries.map((d) => d.item_id)).toEqual(["L07", "S02"]);
    expect(await discoveries[0].photo.text()).toBe("eye");
    expect(discoveries[0].first_found_at).toBe("2026-10-30T15:25:31.000Z");

    const photos = await store.listPhotos("L07");
    expect(photos.map((p) => [p.id, p.taken_at])).toEqual([["L07-first", "2026-10-30T15:25:31.000Z"]]);
    expect(await photos[0].photo.text()).toBe("eye");
    expect(discoveries[0].cover_id).toBe("L07-first");

    // The old stamp is protected like any stamp, and new photos join it.
    await expect(store.deletePhoto("L07", "L07-first")).rejects.toThrow();
    const again = await store.addDiscovery("L07", new Blob(["eye again"]));
    expect(again.isNew).toBe(false);
    expect(await store.listPhotos("L07")).toHaveLength(2);
  });
});
