/**
 * The player's location (PRODUCT.md, "Location check"). Asked for when a photo is
 * taken, so the phone's permission prompt appears at the first photo, not on opening
 * the app. Pure functions and an injectable Geolocation, so they are tested.
 */

import type { PlayerLocation } from "./types";

/** How long to wait for a position before sending the photo without one. */
export const LOCATION_TIMEOUT_MS = 8000;

/**
 * The current position, or null when it is denied, unavailable or slow. Never throws:
 * type items do not need location, and the server answers "need your location" for
 * place items itself.
 */
export function getLocation(
  geolocation: Geolocation | undefined = typeof navigator === "undefined" ? undefined : navigator.geolocation,
  timeoutMs = LOCATION_TIMEOUT_MS,
): Promise<PlayerLocation | null> {
  if (!geolocation) return Promise.resolve(null);
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(null), timeoutMs + 500);
    geolocation.getCurrentPosition(
      (position) => {
        clearTimeout(timer);
        resolve({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracy_m: position.coords.accuracy,
        });
      },
      () => {
        clearTimeout(timer);
        resolve(null);
      },
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 30_000 },
    );
  });
}

const EARTH_RADIUS_M = 6_371_000;

/** Great-circle distance in metres. */
export function distanceM(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h));
}

/** "80 m", "1.4 km", "2,480 km". */
export function formatDistance(metres: number): string {
  if (metres < 1000) return `${Math.round(metres / 10) * 10} m`;
  if (metres < 10_000) return `${(metres / 1000).toFixed(1)} km`;
  return `${Math.round(metres / 1000).toLocaleString("en-GB")} km`;
}

/**
 * The position only if the player has already allowed location, so screens other than
 * the camera (home, for "nearest to find") never cause the permission prompt.
 */
export async function getLocationIfAllowed(
  permissions: Permissions | undefined = typeof navigator === "undefined" ? undefined : navigator.permissions,
  geolocation: Geolocation | undefined = typeof navigator === "undefined" ? undefined : navigator.geolocation,
): Promise<PlayerLocation | null> {
  try {
    const status = await permissions?.query({ name: "geolocation" });
    if (status?.state !== "granted") return null;
  } catch {
    return null;
  }
  return getLocation(geolocation);
}
