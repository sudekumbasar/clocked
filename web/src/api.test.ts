import { describe, expect, it } from "vitest";
import { OFFLINE_MESSAGE, SERVER_MESSAGE, SLOW_MESSAGE, TOO_MANY_MESSAGE, recognise } from "./api";

const RESULT = { outcome: "AWARD", item_id: "S04", cypher_id: null, message: "CLOCKED IT!", reason_code: "passed" };
const photo = new Blob(["jpeg"], { type: "image/jpeg" });

function answering(status = 200) {
  const calls: FormData[] = [];
  const fetchFn = (async (_url: string, init: RequestInit) => {
    calls.push(init.body as FormData);
    return new Response(JSON.stringify({ result: RESULT }), { status });
  }) as typeof fetch;
  return { fetchFn, calls };
}

describe("recognise", () => {
  it("sends the photo with the location", async () => {
    const { fetchFn, calls } = answering();
    const result = await recognise(photo, { lat: 51.5, lng: -0.12, accuracy_m: 15 }, { fetchFn, online: () => true });
    expect(result).toEqual(RESULT);
    expect([calls[0].get("lat"), calls[0].get("lng"), calls[0].get("accuracy_m")]).toEqual(["51.5", "-0.12", "15"]);
  });

  it("sends no location fields when there is no location", async () => {
    const { fetchFn, calls } = answering();
    await recognise(photo, null, { fetchFn, online: () => true });
    expect(calls[0].has("lat") || calls[0].has("lng") || calls[0].has("accuracy_m")).toBe(false);
  });

  it("says so when offline, without calling the server", async () => {
    const { fetchFn, calls } = answering();
    await expect(recognise(photo, null, { fetchFn, online: () => false })).rejects.toMatchObject({
      message: OFFLINE_MESSAGE, offline: true });
    expect(calls).toHaveLength(0);
  });

  it("gives up after the time limit so the player can retry", async () => {
    const hanging = ((_url: string, init: RequestInit) =>
      new Promise((_resolve, reject) => init.signal!.addEventListener("abort", () => reject(new Error("aborted"))))) as typeof fetch;
    await expect(recognise(photo, null, { fetchFn: hanging, online: () => true, timeoutMs: 10 })).rejects.toMatchObject({
      message: SLOW_MESSAGE, offline: false });
  });

  it("reports a server failure", async () => {
    const { fetchFn } = answering(500);
    await expect(recognise(photo, null, { fetchFn, online: () => true })).rejects.toMatchObject({ message: SERVER_MESSAGE });
  });

  it("asks the player to wait when they have sent too many photos", async () => {
    const { fetchFn } = answering(429);
    await expect(recognise(photo, null, { fetchFn, online: () => true })).rejects.toMatchObject({ message: TOO_MANY_MESSAGE });
  });
});
