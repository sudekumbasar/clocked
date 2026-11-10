/**
 * The collection, kept on the device in IndexedDB. There are no accounts.
 *
 * Two stores:
 * - discoveries: one record per item found, with the date it was first found and its
 *   stamp photo (the cover). The cover is a copy of one of the item's photos, so every
 *   screen that shows a stamp reads one record.
 * - photos: every photo the player took of a found item, including the first.
 *
 * Losing the collection is the worst bug this app can have (PRODUCT.md), so the
 * upgrade from the first version, which kept only one photo per item, copies every
 * existing photo across before anything else uses the database.
 */

import { openDB, type IDBPDatabase } from "idb";
import type { Discovery, ItemPhoto } from "./types";

const DB_NAME = "clocked";
const DB_VERSION = 2;
const DISCOVERIES = "discoveries";
const PHOTOS = "photos";

let dbPromise: Promise<IDBPDatabase> | null = null;

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function db(): Promise<IDBPDatabase> {
  dbPromise ??= openDB(DB_NAME, DB_VERSION, {
    async upgrade(database, oldVersion, _newVersion, tx) {
      if (oldVersion < 1) database.createObjectStore(DISCOVERIES, { keyPath: "item_id" });
      if (oldVersion < 2) {
        const photos = database.createObjectStore(PHOTOS, { keyPath: "id" });
        photos.createIndex("by_item", "item_id");
        // Version 1 kept one photo per item: it becomes that item's first photo and stamp.
        const discoveries = tx.objectStore(DISCOVERIES);
        for (const old of (await discoveries.getAll()) as Discovery[]) {
          const id = `${old.item_id}-first`;
          await tx.objectStore(PHOTOS).put({ id, item_id: old.item_id, taken_at: old.first_found_at, photo: old.photo });
          await discoveries.put({ ...old, cover_id: id });
        }
      }
    },
    // Another tab (or a newer version of the app) needs the database: let it go and
    // reopen on next use, rather than leaving both waiting on each other.
    blocking(_current, _blocked, event) {
      (event.target as IDBDatabase).close();
      dbPromise = null;
    },
    terminated() {
      dbPromise = null;
    },
  });
  return dbPromise;
}

export async function getDiscovery(itemId: string): Promise<Discovery | undefined> {
  return (await db()).get(DISCOVERIES, itemId);
}

export async function listDiscoveries(): Promise<Discovery[]> {
  const all: Discovery[] = await (await db()).getAll(DISCOVERIES);
  return all.sort((a, b) => b.first_found_at.localeCompare(a.first_found_at));
}

/** Every photo of one item, oldest first. */
export async function listPhotos(itemId: string): Promise<ItemPhoto[]> {
  const all: ItemPhoto[] = await (await db()).getAllFromIndex(PHOTOS, "by_item", itemId);
  return all.sort((a, b) => a.taken_at.localeCompare(b.taken_at));
}

/**
 * Record a photo of an awarded item. The first photo of an item makes the discovery
 * and becomes its stamp; later photos are kept with it, and the first date stays.
 */
export async function addDiscovery(
  itemId: string,
  photo: Blob,
  now: Date = new Date(),
): Promise<{ isNew: boolean; discovery: Discovery; photo: ItemPhoto }> {
  const database = await db();
  const tx = database.transaction([DISCOVERIES, PHOTOS], "readwrite");
  const taken: ItemPhoto = { id: newId(), item_id: itemId, taken_at: now.toISOString(), photo };
  await tx.objectStore(PHOTOS).add(taken);
  const existing: Discovery | undefined = await tx.objectStore(DISCOVERIES).get(itemId);
  if (existing) {
    await tx.done;
    return { isNew: false, discovery: existing, photo: taken };
  }
  const discovery: Discovery = { item_id: itemId, first_found_at: taken.taken_at, photo, cover_id: taken.id };
  await tx.objectStore(DISCOVERIES).add(discovery);
  await tx.done;
  return { isNew: true, discovery, photo: taken };
}

/** Make one of the item's photos its stamp. The first-found date does not change. */
export async function setCover(itemId: string, photoId: string): Promise<Discovery> {
  const database = await db();
  const tx = database.transaction([DISCOVERIES, PHOTOS], "readwrite");
  const discovery: Discovery | undefined = await tx.objectStore(DISCOVERIES).get(itemId);
  const chosen: ItemPhoto | undefined = await tx.objectStore(PHOTOS).get(photoId);
  if (!discovery || !chosen || chosen.item_id !== itemId) {
    tx.abort();
    await tx.done.catch(() => undefined); // the abort is the answer here, not an error
    throw new Error("That photo is not one of this item's photos.");
  }
  const updated: Discovery = { ...discovery, photo: chosen.photo, cover_id: chosen.id };
  await tx.objectStore(DISCOVERIES).put(updated);
  await tx.done;
  return updated;
}

/**
 * Delete one photo. The stamp photo cannot be deleted, so an item can never be lost
 * from the collection by deleting photos.
 */
export async function deletePhoto(itemId: string, photoId: string): Promise<void> {
  const database = await db();
  const tx = database.transaction([DISCOVERIES, PHOTOS], "readwrite");
  const discovery: Discovery | undefined = await tx.objectStore(DISCOVERIES).get(itemId);
  const photo: ItemPhoto | undefined = await tx.objectStore(PHOTOS).get(photoId);
  if (!discovery || !photo || photo.item_id !== itemId || discovery.cover_id === photoId) {
    tx.abort();
    await tx.done.catch(() => undefined); // the abort is the answer here, not an error
    throw new Error("The stamp photo can't be deleted. Choose another photo as the stamp first.");
  }
  await tx.objectStore(PHOTOS).delete(photoId);
  await tx.done;
}

/** Test mode only: empty the collection so the discovery screen can be seen again. */
export async function resetCollection(): Promise<void> {
  const database = await db();
  await database.clear(DISCOVERIES);
  await database.clear(PHOTOS);
}
