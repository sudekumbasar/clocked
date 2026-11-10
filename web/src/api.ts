import type { Item, PlayerLocation, RecognitionResult } from "./types";

/** Text from PRODUCT.md, "When things go wrong". */
export const OFFLINE_MESSAGE =
  "Recognition needs an internet connection. Try again when you're online.";
export const SERVER_MESSAGE = "Something went wrong on our side. Your photo is kept: try again.";
export const SLOW_MESSAGE = "This is taking too long. Your photo is kept: try again.";
export const TOO_MANY_MESSAGE = "That's a lot of photos in a short time. Wait a minute and try again.";

/** After this long the player gets a Retry button instead of waiting on. */
export const RECOGNISE_TIMEOUT_MS = 20_000;

export class RecognitionError extends Error {
  constructor(
    message: string,
    readonly offline: boolean,
  ) {
    super(message);
  }
}

export async function fetchItems(): Promise<Item[]> {
  const response = await fetch("/api/items");
  if (!response.ok) throw new Error(`items: ${response.status}`);
  return response.json();
}

interface Options {
  fetchFn?: typeof fetch;
  online?: () => boolean;
  timeoutMs?: number;
}

/**
 * Send one photo, with the player's location when there is one. The location goes to
 * our server only; the server never passes it to the model.
 */
export async function recognise(
  photo: Blob,
  location: PlayerLocation | null,
  { fetchFn = fetch, online = () => navigator.onLine, timeoutMs = RECOGNISE_TIMEOUT_MS }: Options = {},
): Promise<RecognitionResult> {
  if (!online()) throw new RecognitionError(OFFLINE_MESSAGE, true);
  const form = new FormData();
  form.append("photo", photo, "photo.jpg");
  if (location) {
    form.append("lat", String(location.lat));
    form.append("lng", String(location.lng));
    form.append("accuracy_m", String(location.accuracy_m));
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetchFn("/api/recognise", { method: "POST", body: form, signal: controller.signal });
  } catch {
    if (controller.signal.aborted) throw new RecognitionError(SLOW_MESSAGE, false);
    throw new RecognitionError(online() ? SERVER_MESSAGE : OFFLINE_MESSAGE, !online());
  } finally {
    clearTimeout(timer);
  }
  if (response.status === 429) throw new RecognitionError(TOO_MANY_MESSAGE, false);
  if (!response.ok) throw new RecognitionError(SERVER_MESSAGE, false);
  const body = await response.json();
  return body.result as RecognitionResult;
}
