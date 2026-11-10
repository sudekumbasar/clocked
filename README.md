# Clocked

A London collecting game for your phone. Photograph something that says London (a red phone box, Borough Market, a historic pub, the London Eye) and the app recognises it and turns your own photo into a postage stamp in your collection, with a London postmark dated the day you found it and a short, sourced fact about the place. A map shows the places still to find, as clues.

**Live:** https://clocked-797428694878.europe-west1.run.app (open it on a phone; place stamps only award in London)

## How a photo is judged

The vision model never awards anything. It proposes; deterministic rules decide.

1. **The model proposes.** The photo goes to Claude Sonnet 5.5 with the list of 40 collectibles. It returns a structured answer: up to two candidates with a confidence, the text it can read on the object, and whether the photo shows the real thing or a picture of it (a screen, a poster, a postcard).
2. **A blind reading checks the text.** When a candidate needs its name read (a pub sign), a second request with no list of collectibles transcribes the text, so the model cannot "read" what it expects to see.
3. **Rules decide.** A separate verification step applies each item's rules from the CSV: confidence thresholds, text that must appear in both readings, words that rule an item out, and for places the player's distance against the item's radius and the phone's reported accuracy. The outcome is AWARD, RETRY ("take a closer photo") or REJECT. When unsure, it awards nothing: a wrong award is treated as worse than a missed one.

The player's location is used only by these rules and the map. It is never sent to the model.

| Verification | Used for | Example |
|---|---|---|
| vision | Things found all over the city | Red double-decker bus, black cab |
| vision + location | Unique places | Big Ben, Borough Market, Platform 9¾ |
| vision + text + location | Places that look like many others | A pub, by the name on its sign |

## Testing

- **A labelled test set** of 236 photos (106 positives, 130 negatives, many of them hard negatives: Westminster Abbey next to Big Ben, a different pub with the same name in another street, a station with no Paddington statue). `tools/score_photos.py` runs a folder of photos through the real endpoint and reports wrong awards, retries, rejects, per-item results and the model cost of the run. Saved answers can be re-scored with new thresholds without calling the model again.
- **Results:** on the latest full run (138 photos), no wrong awards, and 52 of 59 clear photos of new items awarded first time. The first walk around central London (13 photos) also gave no wrong awards, with phone location 3–38 m accurate.
- **Unit tests:** 209 for the server (every verification rule, text matching, catalogue validation, rate limits, the API) and 50 for the web app (collection, stamps, map rules, location handling, the on-device database and its upgrade).

## Stack

- **Web app:** Preact and TypeScript, built with Vite; a camera-only PWA. The collection lives on the device in IndexedDB; there are no accounts. Leaflet with OpenStreetMap for the map. Fonts (Fraunces, DM Sans, Courier Prime) are bundled under the SIL Open Font License.
- **Server:** Python, FastAPI, Pillow (photos are re-encoded and stripped of metadata before they are sent). The model provider sits behind one small interface; a fake provider runs the tests and demos without an API key.
- **Hosting:** Google Cloud Run (one instance at most, scaled to zero), with the API key in Secret Manager. Per-player rate limits and a prepaid model credit keep a public address from running up costs.
- **Content:** every collectible, fact, coordinate, radius and text to match lives in `data/london_collection_v4.csv`. Facts were written from cited sources, never generated.

## Repository

| Path | What it is |
|---|---|
| `PRODUCT.md` | The product definition: rules, screens, build order and open decisions |
| `data/` | The collectibles CSV and how the 40 items were chosen and sourced |
| `server/` | Recognition server, verification rules and tests |
| `web/` | The phone app and its tests |
| `tools/` | The photo scoring script and the model comparison |
| `testset/labels.csv` | Labels for the test photos; `SOURCES_*.md` list where each photo came from and its licence (the photos themselves are not in the repository) |
| `Dockerfile`, `scripts/` | Packaging, local start and Cloud Run deploy |

## Run it locally

```bash
# Server (Python 3.11)
cd server && python -m venv .venv && .venv/bin/pip install -r requirements.txt pytest httpx
.venv/bin/python -m pytest

# Web app (Node 20)
cd web && npm ci && npm test

# The whole app on http://127.0.0.1:8000 (needs ANTHROPIC_API_KEY in a .env file at the root)
sh scripts/start_server.sh        # public build
sh scripts/start_server.sh test   # with test mode: saved photos and "pretend I am here"
```

Without an API key, set `CLOCKED_PROVIDER=fake` to run the server with scripted answers.

## Credits

Built with [Claude Code](https://claude.com/claude-code). Map data © OpenStreetMap contributors. Test photos are from Wikimedia Commons under the licences listed in `testset/SOURCES_*.md`.

## Copyright

© 2026 Sude Kumbasar. All rights reserved. The code is shared to show the work; please ask before reusing it.
