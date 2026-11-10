/** An item as the server sends it (GET /api/items). Everything comes from the CSV. */
export interface Item {
  id: string;
  set: string;
  name: string;
  category: string;
  kind: "type" | "place";
  rarity: "common" | "rare" | "legendary";
  fact: string;
  clue: string;
  location: string;
  access: string;
  lat: number | null; // place items only, for the map
  lng: number | null;
}

/** Where the player is, as the phone reports it. Sent to our server only, never to the model. */
export interface PlayerLocation {
  lat: number;
  lng: number;
  accuracy_m: number;
}

export type Outcome = "AWARD" | "RETRY" | "REJECT";

/** The verification result for one photo (POST /api/recognise). */
export interface RecognitionResult {
  outcome: Outcome;
  item_id: string | null;
  cypher_id: string | null;
  message: string;
  reason_code: string;
}

/** One discovery, kept on the device. */
export interface Discovery {
  item_id: string;
  first_found_at: string; // ISO date and time
  photo: Blob; // the stamp photo: a copy of the photo named by cover_id
  cover_id?: string; // missing only in a record not yet upgraded
}

/** One photo of a found item. Every photo is kept, the first one included. */
export interface ItemPhoto {
  id: string;
  item_id: string;
  taken_at: string; // ISO date and time
  photo: Blob;
}
