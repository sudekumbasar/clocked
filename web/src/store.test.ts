import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it } from "vitest";
import {
  addDiscovery,
  deletePhoto,
  getDiscovery,
  listDiscoveries,
  listPhotos,
  resetCollection,
  setCover,
} from "./store";

const photo = (text: string) => new Blob([text], { type: "image/jpeg" });

describe("collection on the device", () => {
  beforeEach(resetCollection);

  it("stores a first discovery with its date and photo", async () => {
    const result = await addDiscovery("S01", photo("a"), new Date("2026-10-07T10:00:00Z"));
    expect(result.isNew).toBe(true);
    const saved = await getDiscovery("S01");
    expect(saved?.first_found_at).toBe("2026-10-07T10:00:00.000Z");
    expect(await saved!.photo.text()).toBe("a");
    expect(saved!.cover_id).toBe(result.photo.id);
  });

  it("keeps every photo of an item, and the first date and stamp", async () => {
    await addDiscovery("L07", photo("first"), new Date("2026-10-01T10:00:00Z"));
    const again = await addDiscovery("L07", photo("second"), new Date("2026-10-07T10:00:00Z"));
    expect(again.isNew).toBe(false);
    expect(again.discovery.first_found_at).toBe("2026-10-01T10:00:00.000Z");
    expect(await (await getDiscovery("L07"))!.photo.text()).toBe("first");
    const photos = await listPhotos("L07");
    expect(await Promise.all(photos.map((p) => p.photo.text()))).toEqual(["first", "second"]);
  });

  it("lets the player make another photo the stamp, keeping the first date", async () => {
    await addDiscovery("L07", photo("first"), new Date("2026-10-01T10:00:00Z"));
    const later = await addDiscovery("L07", photo("better"), new Date("2026-10-07T10:00:00Z"));
    const updated = await setCover("L07", later.photo.id);
    expect(await updated.photo.text()).toBe("better");
    expect(updated.first_found_at).toBe("2026-10-01T10:00:00.000Z");
    expect(await (await getDiscovery("L07"))!.photo.text()).toBe("better");
  });

  it("never makes another item's photo the stamp", async () => {
    await addDiscovery("L07", photo("eye"));
    const bus = await addDiscovery("S04", photo("bus"));
    await expect(setCover("L07", bus.photo.id)).rejects.toThrow();
    expect(await (await getDiscovery("L07"))!.photo.text()).toBe("eye");
  });

  it("deletes a photo the player doesn't want", async () => {
    await addDiscovery("L07", photo("keep"), new Date("2026-10-01T10:00:00Z"));
    const blurry = await addDiscovery("L07", photo("blurry"), new Date("2026-10-02T10:00:00Z"));
    await deletePhoto("L07", blurry.photo.id);
    expect(await Promise.all((await listPhotos("L07")).map((p) => p.photo.text()))).toEqual(["keep"]);
  });

  it("never deletes the stamp photo, so an item can't be lost", async () => {
    const first = await addDiscovery("L07", photo("stamp"));
    await expect(deletePhoto("L07", first.photo.id)).rejects.toThrow(/stamp photo/);
    expect(await listPhotos("L07")).toHaveLength(1);
    expect(await getDiscovery("L07")).toBeDefined();
  });

  it("can delete the old stamp photo once another is the stamp", async () => {
    const first = await addDiscovery("L07", photo("old"), new Date("2026-10-01T10:00:00Z"));
    const second = await addDiscovery("L07", photo("new"), new Date("2026-10-02T10:00:00Z"));
    await setCover("L07", second.photo.id);
    await deletePhoto("L07", first.photo.id);
    expect(await (await getDiscovery("L07"))!.photo.text()).toBe("new");
    expect((await getDiscovery("L07"))!.first_found_at).toBe("2026-10-01T10:00:00.000Z");
  });

  it("lists newest discoveries first, and reset empties both stores", async () => {
    await addDiscovery("S01", photo("a"), new Date("2026-10-01T10:00:00Z"));
    await addDiscovery("T01", photo("b"), new Date("2026-10-02T10:00:00Z"));
    expect((await listDiscoveries()).map((d) => d.item_id)).toEqual(["T01", "S01"]);
    await resetCollection();
    expect(await listDiscoveries()).toEqual([]);
    expect(await listPhotos("S01")).toEqual([]);
  });
});
