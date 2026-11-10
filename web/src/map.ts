/**
 * What the map shows (PRODUCT.md, "Screens", 5). Pure functions, so they are tested.
 * Undiscovered places are "?" markers: category, rarity, distance and a one-word clue,
 * never the name. Discovered places show normally. Type items are never on the map.
 */

import { distanceM, formatDistance } from "./location";
import { inkFor } from "./stamp";
import type { Item, PlayerLocation } from "./types";

export interface MapMarker {
  id: string;
  lat: number;
  lng: number;
  found: boolean;
  title: string; // the name once found, otherwise "Clue: Bells"
  category: string;
  rarity: Item["rarity"];
  distance: string | null; // only when we know where the player is
  ticket: string | null;
  ink: string;
}

/** PRODUCT.md: items inside a paid area are marked "ticket needed". */
export function ticketNote(access: string): string | null {
  if (access === "paid") return "Ticket needed";
  if (access === "mixed") return "Ticket needed for part of it";
  return null;
}

export function mapMarkers(items: Item[], discoveredIds: Set<string>, here: PlayerLocation | null): MapMarker[] {
  return items
    .filter((item) => item.kind === "place" && item.lat !== null && item.lng !== null)
    .map((item) => {
      const found = discoveredIds.has(item.id);
      const position = { lat: item.lat!, lng: item.lng! };
      return {
        id: item.id,
        ...position,
        found,
        title: found ? item.name : `Clue: ${item.clue || "?"}`,
        category: item.category,
        rarity: item.rarity,
        distance: here ? `${formatDistance(distanceM(here, position))} away` : null,
        ticket: ticketNote(item.access),
        ink: inkFor(item.category, items),
      };
    });
}

/** The nearest undiscovered place, for the home screen and the map's card. Null without a location. */
export function nearestToFind(markers: MapMarker[], here: PlayerLocation | null): MapMarker | null {
  if (!here) return null;
  let best: MapMarker | null = null;
  let bestDistance = Infinity;
  for (const marker of markers) {
    if (marker.found) continue;
    const d = distanceM(here, marker);
    if (d < bestDistance) {
      best = marker;
      bestDistance = d;
    }
  }
  return best;
}
