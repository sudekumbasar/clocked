import { describe, expect, it } from "vitest";
import { distanceM, formatDistance, getLocation, getLocationIfAllowed } from "./location";

function geolocation(behaviour: "ok" | "denied" | "silent"): Geolocation {
  return {
    getCurrentPosition(success, error) {
      if (behaviour === "ok") {
        success({ coords: { latitude: 51.5056, longitude: -0.0753, accuracy: 12 } } as GeolocationPosition);
      } else if (behaviour === "denied") {
        error?.({ code: 1, message: "denied" } as GeolocationPositionError);
      }
    },
  } as Geolocation;
}

describe("location", () => {
  it("reports the position with its accuracy", async () => {
    expect(await getLocation(geolocation("ok"))).toEqual({ lat: 51.5056, lng: -0.0753, accuracy_m: 12 });
  });

  it("gives null, not an error, when permission is denied", async () => {
    expect(await getLocation(geolocation("denied"))).toBeNull();
  });

  it("gives null when the phone never answers", async () => {
    expect(await getLocation(geolocation("silent"), 10)).toBeNull();
  });

  it("gives null when the browser has no geolocation", async () => {
    expect(await getLocation(undefined)).toBeNull();
  });

  it("measures distance on the Earth's surface", () => {
    // Tower Bridge to the Trafalgar Square lions: about 3.6 km.
    const d = distanceM({ lat: 51.5056, lng: -0.0753 }, { lat: 51.50772, lng: -0.12797 });
    expect(d).toBeGreaterThan(3600);
    expect(d).toBeLessThan(3700);
  });

  it("formats distances for a walker", () => {
    expect(formatDistance(83)).toBe("80 m");
    expect(formatDistance(1420)).toBe("1.4 km");
    expect(formatDistance(2_480_000)).toBe("2,480 km");
  });

  it("outside the camera, reads the position only when location is already allowed", async () => {
    const permissions = (state: PermissionState) => ({ query: async () => ({ state }) }) as unknown as Permissions;
    expect(await getLocationIfAllowed(permissions("granted"), geolocation("ok"))).toMatchObject({ lat: 51.5056 });
    let asked = false;
    const watching = { getCurrentPosition: () => { asked = true; } } as unknown as Geolocation;
    expect(await getLocationIfAllowed(permissions("prompt"), watching)).toBeNull();
    expect(asked).toBe(false);
    expect(await getLocationIfAllowed(undefined, geolocation("ok"))).toBeNull();
  });
});
