# Clocked: product definition

Version 1 scope, 10 October 2026, revision 5. Companion data file: `london_collection_v4.csv`.

## What it is

Clocked is a phone app that turns time in a city into a collection of memories. You take the photo you would take anyway, of the places and things that say London, the app recognises it, and it joins your collection with your own photo, a story about the place and the date. Version 1 covers London only.

The name is British slang: to clock something is to notice it. It does not mention London, so other cities can be added later.

The one question version 1 has to answer: **is it fun to open this while walking around London?** Everything that does not help answer it is left out.

## Core loop

Home → Camera → Recognition → Discovery → Collection → Map

1. The player sees something, or goes somewhere, and takes a photo in the app: the photo they would take anyway, not a close-up of a sign.
2. The app decides whether the photo shows a collectible, and which one.
3. If it does, the player gets a discovery screen and the item joins the collection.
4. The map shows undiscovered places nearby, which gives a reason to keep walking.

## Collectibles

There are two kinds, and the difference is a design principle.

- **Type: spot it.** Found all over the city and recognised from the photo alone (a red telephone box, a red double-decker bus). Never shown on the map.
- **Place: find it.** Exists at one address and is checked against location where possible (Big Ben, Borough Market, Platform 9¾). Shown on the map. For a place, the photo is a memory photo: the view, the frontage, the statue, the crowd, as people normally photograph it. Location is the main check; the photo only has to show the place.

Rarity describes effort, not real-world scarcity.

- **Common:** you will see it on an ordinary walk.
- **Rare:** you have to look for it.
- **Legendary:** you have to go there on purpose.

Version 1 content:

- **Main collection, 40 items in four categories of 10:**
  - **London Icons:** the things that say London at a glance. A mix of street icons seen on any walk (red bus, black cab, red telephone box, red post box, Underground roundel) and the big landmarks (such as Big Ben, the London Eye, Tower Bridge).
  - **Londoner's London:** where Londoners go at the weekend: markets, parks and views, and a stadium or two.
  - **Pub Crawl:** historic pubs worth seeing. Collected from the street; the app never asks anyone to go in or to drink.
  - **Film & Free Museums:** places from films and books (such as Platform 9¾, the Paddington statue, Abbey Road) and famous objects in London's free museums.
- **Retired in revision 5:** the Street Icons, Transport and Blue Plaques items that do not move to the new categories. Their rows stay in the CSV with the set `retired`, switched off the same way as the Royal Cyphers, so nothing is deleted.
- **Royal Cyphers, 7 items: moved to the next version** (see "Next version: Royal Cyphers"). The rules below still describe how the set works; in version 1 it is switched off and no cypher is ever awarded. A nested set. Photographing a post box awards "Red post box" once; reading the cypher on it awards that cypher separately, so a post box the player already has can still give something new. A cypher is awarded only alongside a post box that passes its own checks in the same photo, whether or not the player already has the post box. Pillar, wall and lamp boxes all count as post boxes. A cypher on anything that is not a post box (a building, a bollard, a police box) does not count.

The counts of type and place items and of each rarity describe the data once the 40 items are chosen; they are not rules: swapping an item must not break anything.

All item data lives in the CSV: `id, set, name, category, kind, rarity, verification, access, location, lat, lng, verification_radius_m, clue, fact, source_url, notes, match_text, model_hint, conflict_text, parent_id`. The app reads items from this file; nothing about a collectible is hard-coded. `lat`, `lng`, `verification_radius_m` and `clue` are empty for type items.

- `match_text`: the text that must be read, for items whose verification includes text.
- `model_hint`: a short visual description sent to the vision model. `notes` are for us and are never sent to the model.
- `conflict_text`: text that, if read, means the photo probably shows something else (see Further rules).
- `parent_id`: for an item in a nested set, the item it can only be awarded alongside (each royal cypher has the post box as its parent).

## Recognition

**The rule: a wrong award is worse than a missed one.** If the app is not sure, it gives nothing.

### How a photo is judged

photo → vision model (candidates) + blind reading (text only) → verification rules → AWARD, RETRY or REJECT

1. **The model picks from a list.** It is sent the photo and the list of collectibles, and must return a structured answer:
   - `candidates`: at most two, most certain first. Each has a `candidate_id`, a `confidence` and `object_text`, the text read on that object itself. A second candidate is given only when a different collectible is also clearly in the photo.
   - `cypher_id` and `cypher_confidence`: a royal cypher read on a post box, or null. Always null in version 1, because the Royal Cyphers set is switched off.
   - `other_text`: any other text read in the photo.
   - `reason`: a short explanation, for testing only.

   It is never asked an open question such as "what is this?".
2. **"None of these" is a valid answer.** The candidates list can be empty, and the prompt says so plainly.
3. **Text is read twice.** When an award could depend on text (an item with a text check, or a royal cypher), the photo is also sent in a second, separate request with no list of collectibles: the model only transcribes the text it can see, and says when it cannot read any. This blind reading cannot be steered by what the model expects to find.
4. **Our rules decide, not the model.** A separate, deterministic step checks the answer against the item's `verification` column and returns the outcome. The model never adds anything to the collection.
5. **The model's confidence is a rough signal only.** Text and location are the hard checks: a place is awarded because the player is there (and, where the place cannot be told apart otherwise, the name was read), not because the model said 0.95. The two are not equally strong. The text is read by the same model that proposes the candidate, so it is not an independent check: in testing, the model wrote text it expected rather than text it could see (a royal cypher it could not read, a plaque name too small to read). Location is the only check that does not depend on the model. The blind reading narrows the gap: in the same tests it did not invent those texts. Items whose verification is vision alone have no hard check, so for them the high confidence threshold is the whole decision. This is accepted for version 1; the test set carries extra hard negatives for these items instead.

### Signals per collectible

| Signal | Used for | Example |
| --- | --- | --- |
| vision | The object is recognisable by shape | Telephone box, black cab, red bus |
| vision + text | The object carries words that confirm it | A royal cypher (next version) |
| vision + location | The place is unique; the photo shows it as people photograph it | Big Ben, Borough Market, Abbey Road crossing |
| vision + text + location | The place looks like many others, so its name must be read too | A pub frontage with the pub's name on the sign |

Text checks are used only where an item cannot be told apart otherwise. They should not push players towards close-ups of signs instead of the photo they would take anyway.

A text check passes only when `match_text` is found both in the text on the candidate object itself (`object_text`) and in the blind reading. `conflict_text` is checked against `object_text` only, never against other text in the frame: at an interchange station one photo can show several modes' names. Text matching ignores case, punctuation and spacing but only matches whole words, so GR does not match GRADE. In `match_text` and `conflict_text`, `|` separates alternatives and `+` joins words that must all be read.

### Outcomes

- **High confidence, all checks pass:** "CLOCKED IT!" and the discovery screen.
- **Medium confidence on an item checked by text and location (a pub), when its name is read in both readings and the player is within the radius:** also "CLOCKED IT!". The name and the place together are stronger evidence than the model's own certainty; in testing, the model read THE GEORGE in both readings at the George Inn but gave only 0.72 and 0.80. Items without both checks still need high confidence: a shop next to Platform 9¾ reached 0.80.
- **Medium, or a required check could not be completed:** "I think this might be: [name]. Take a closer photo to confirm." No award.
- **Low or no candidate:** "Couldn't identify this one. Try getting closer or capturing any text or signs." No award.

### Further rules

- **One photo, one discovery.** Each candidate is checked on its own, then one is chosen:
  1. a place item that passes all its checks;
  2. otherwise, any candidate that passes all its checks, the most certain first;
  3. otherwise, the outcome for the most certain candidate.

  This handles items that overlap, such as a landmark with a red bus in front of it, or a market whose entrance has a telephone box. The only exception to one discovery is a post box, which can award the box and its cypher together (next version). A cypher only counts when the post box is the item awarded, and the text on the post box and the blind reading both name that same cypher and nothing in its `conflict_text` (G R inside G R VI is not George V). A cypher has no confidence threshold of its own.
- **The `verification` column is the only source** for which checks an item needs. Items below ground never include location, because there is no GPS below ground.
- **Location check:** the player must be within the item's `verification_radius_m`. There is no default in code: the data uses 75 m for most places, 200 m for items with approximate coordinates, and a wide radius (up to about 1.5 km) for landmarks that are photographed from a distance, such as Big Ben from across the river. A wide radius is only given to items that look like nothing else. The radius is deliberately generous because phone location in dense streets is often tens of metres off. The app refuses to start if an item's verification includes location but it has no radius, or it has a radius but its verification does not include location. Place items below ground keep coordinates for the map only.
- **Location accuracy:** the phone reports how far off its location may be. If that is more than the item's radius, the outcome is RETRY.
- **Outside the radius:** if a place item is recognised and its text check passes in both readings, but the player is outside the radius, nothing is awarded and the player is told they don't seem to be near it. A place item with no text check that is outside the radius gets the ordinary "couldn't identify" message, so a hidden place's name is not given away by photographing any zebra crossing.
- **Conflicting text:** if the text on the candidate object includes anything in its `conflict_text` (for example OVERGROUND on an Underground roundel candidate), the outcome is RETRY.
- **A picture of an item is not the item.** The model says whether the item is shown as a picture (on a screen, a poster, a billboard, a print, a postcard, in a book) or as a model, toy or souvenir, rather than being the real thing; if so, the outcome is RETRY: "This looks like a picture of [name], not the real thing. Take a photo of the real one." The name is given only for type items; for a place the message says "it", so a postcard does not give away a hidden place. Decided on 29 October 2026, after the first public test awarded a red bus photographed on a laptop screen. A real object carrying an advert, such as a bus with a poster on its side, is still the real thing. In testing, 20 photos of real statues, signs, skeletons and other items (Paddington, Sherlock Holmes, the Trafalgar lions, Platform 9¾, Hope) were all still awarded.
- **Thresholds** for high and medium are set by testing on real photos, starting strict. Royal cyphers do not use a threshold; they rely on the two readings agreeing. A stricter cypher threshold was tried first, and in testing it stopped wrong cyphers only by luck: the model gave 0.90 where the threshold was 0.95.

## Screens

0. **Home.** The screen the app opens on. The app's name, how many stamps the player has ("7 of 40 stamps") with the latest ones as a small stack, progress per category, the nearest undiscovered place as its clue and distance ("Nearest to find: Clue: Skate · 870 m", only when the player's location is known; tapping it opens the map), and a large "Take a photo" button, with "My stamps" and "Map" below it. A player with no stamps yet sees an empty stamp space: "Your first stamp goes here".
   - **First open:** once, before the home screen, a short welcome in three steps (take the photo you'd take anyway; we recognise it, and for places check you're there; it becomes a stamp) and why the app will ask for the camera and location.
1. **Camera.** Opened from "Take a photo". A live camera view and one button, with a stamp-shaped frame over the view. Version 1 is camera-only: no gallery uploads. The product is "I spotted this in the city", and it also keeps the flow to open, shoot, discover. The app uses the live camera inside the page, not the phone's file picker, because a file picker cannot be limited to the camera reliably.
2. **Discovery.** The most important screen in the app. The player's photo becomes a postage stamp (see "Stamp look" below), then it shows, in order: "CLOCKED IT!", the item's name, rarity, its category with progress ("London Icons 4 / 10"; the city is not part of the category name, and will get its own column when a second city is added), and one fact. Includes a short animation and, on Android, a vibration (iPhone browsers do not support vibration). For an item the player already has: "Already discovered", the date it was first found, and the photo just taken, which is kept with the item's other photos ("Added to your [name] photos").
3. **Collection.** One fan of stamps per category, showing the most recent finds, with progress and how many are still to find. Tapping a category opens its album page: one space per item in CSV order, filled with the stamp once found. An empty space shows, for a type item, its number and name; for a place item, only its clue and rarity.
4. **Item detail.** The player's own photo as a large stamp, the fact, date found, and for place items the address. Every photo the player has taken of the item is kept, shown below as a small roll. Any of them can be made the stamp (the postmark keeps the date the item was first found), and any photo except the stamp can be deleted, so an item can never be lost from the collection by deleting photos.
5. **Map.** Undiscovered place items only, as "?" markers. Tapping one shows category, rarity, distance and a one-word clue ("Clue: Music") in a card at the bottom of the screen; the name stays hidden until found. Before anything is tapped, the card shows the nearest undiscovered place. Items inside a paid area are marked "ticket needed". Discovered places show normally. The map is drawn in muted, old-map colours so the markers stand out.

## When things go wrong

| Situation | What the player sees |
| --- | --- |
| No internet | "Recognition needs an internet connection. Try again when you're online." The photo is kept so it can be retried. |
| Server slow or failing | A Retry button, after 20 seconds at most. The photo is not lost. |
| Too many photos in a short time (more than 10 a minute or 150 a day from one player) | "That's a lot of photos in a short time. Wait a minute and try again." The photo is kept. This stops a public address being used to spend the model budget. |
| Camera permission denied | "Camera access is needed to discover items." |
| Location denied, type item | Nothing. Type items do not need location. |
| Location denied or unavailable, place item | "We recognised this, but need your location to verify the discovery." No award. |
| Location too imprecise for the item's radius | "Your location isn't precise enough to verify this yet. Wait a moment and try again." No award. |
| Place item recognised and its text matches, but the player is outside the radius | "This looks like [name], but you don't seem to be near it." No award. |
| Object recognised but text could not be read | The medium outcome: ask for a closer photo. |
| Item already in the collection | "Already discovered" with the date. |

## Content rules

- Every fact is written once, checked against its source, and stored in the CSV. Facts are never generated live.
- Free-to-reach items are preferred: everything should be collectable from the street or from a free museum. Items inside a paid area are marked "ticket needed".
- Pub Crawl items are collected from outside. Nothing in the app asks anyone to go in or to drink.
- Museum objects are indoors, where phone location is weak, and museum shops sell copies of famous objects. How each museum object is checked is decided item by item when the list is chosen.

## Technical shape (proposed defaults)

- **Mobile web app** that runs in the phone browser and can be added to the home screen. No app store.
- **No accounts.** The collection is stored on the device.
- **Keeping the collection safe.** Losing the collection is the worst bug this app can have. Safari may delete a website's stored data after about 7 days without a visit, unless the site has been added to the home screen. So the app asks the browser for persistent storage and prompts the player to add it to the home screen.
- **Recognition** starts with a hosted vision model, called through a small server endpoint so the API key is never in the app. The model is Claude Sonnet 5.5 through Anthropic's API, for both the main answer and the blind reading, and the blind reading runs only when needed, after the main answer. Chosen at the end of step 1 by comparing setups on 77 labelled photos: Haiku 4.5 made 3 wrong awards on items checked by vision alone (green post boxes, a City of London crest taken for a dragon) and could not read royal cyphers; Sonnet 5.5 made none. Running the blind reading on every photo, in parallel, saved 0.3 s on average and cost 34% more. Anthropic deletes API inputs and outputs within 30 days (longer only if they are flagged for a policy violation) and does not train on them.
- **Privacy:** the photo is sent to the recognition service for that one request and our server does not keep it. After a successful discovery the photo is stored on the player's device only, for the collection. Before choosing the model provider, check its own data retention terms: our server not keeping a photo does not mean the provider does not. Location is used only to verify place items and to draw the map, and is never sent to the recognition service.
- **Location** is asked for when the player takes a photo, so the phone's permission prompt appears at the first photo, not on opening the app. If none arrives within 8 seconds the photo is sent without it.
- **Map:** Leaflet with OpenStreetMap tiles, muted with a colour filter in the app, with the required "© OpenStreetMap contributors" credit on the map. It loads only when the player opens it.
- **Later:** train our own classifier for one or two categories.

## Testing without being there

The public app is camera-only and checks location. Development needs a way around both, kept out of the public version.

- **Test script.** Runs a folder of saved photos through the recognition endpoint and reports awards, retries and rejects, and logs the model cost of every run. This is how the test set is scored. It does not use the app at all.
- **Test mode in the app.** A switch that exists only in development builds. It adds two things: choosing a saved photo instead of using the camera, and "pretend I am here", which sets the player's location to any item's coordinates. With both, every item including place items can be walked through from a desk.
- **Reset collection**, also in test mode only, so the discovery screen can be seen again.
- The public build has none of these: test mode is removed when the public build is made, not hidden behind a switch. The server cannot tell a real location from a pretended one, because both arrive as coordinates. So the rule is enforced in two places: the public app has no way to set a location by hand, and the server has no override field and no development endpoints unless development mode is switched on in the server's own configuration, which the public server never has.

## Not in version 1

The Royal Cyphers set, points and levels, accounts, friends and profile comparison, leaderboards, streaks, daily challenges, secret discoveries, gallery uploads, cheat prevention beyond camera-only, the day-trip planner, any city other than London.

## Ideas for a later version (29 October 2026)

Not built in version 1, which keeps everything on the phone and has no accounts. Plan these once version 1 has worked on the street.

- **Accounts:** sign up and log in, so a collection survives a lost phone and can be shared. Needs a privacy review (email, passwords or a sign-in provider, deleting an account) and a database.
- **Friends:** add friends and see each other's stamps.
- **Shared games between friends:** a small group of friends picks its own list of things to find. Open questions before this can be built: how a home-made task is checked without wrong awards (a bowl of noodles can be anywhere, so it cannot use location the way places do), where its fact comes from (facts are never generated), and keeping to the rule that the app never asks anyone to drink.

## Next version: Royal Cyphers

The set was built and tested in step 1 and switched off for version 1. Its rows stay in the CSV and its rules stay in the code; one server setting (`disabled_sets`) leaves it out.

Why: the rule for keeping it was no wrong cypher on the test set and at least half of the clear close-up cypher photos awarded. With the chosen model (Sonnet 5.5) there were no wrong cyphers, but only 3 of 12 clear close-ups were awarded, and none of the 6 Edward VIII photos, the legendary item. A cheaper model (Haiku 4.5) awarded a "G R" cypher to a bollard it took for a post box.

Before bringing it back:
- Find a way to read cyphers reliably, for example a second, zoomed-in look at the cypher only.
- Add the forms the data does not cover yet: Elizabeth II lamp and wall boxes often show "E R" with a crown between the letters and no "II".
- Re-run the same rule on the cypher photos in the test set.

## How we will know it works (proposed targets)

**Recognition, on a test set of real photos**

- At least 150 photos, of which at least 50 are hard negatives: things that look like a collectible but are not. Examples: a red object that is not a telephone box, a minicab, a non-red double-decker, a round logo that is not a roundel, another Ferris wheel or clock tower, a pub or market that is not in the collection, another blue door, Paddington merchandise, a museum-shop copy of a famous object, a picture of a landmark on a screen or a poster. Items checked by vision alone get extra hard negatives, because confidence is their only check.
- **Zero wrong awards on the test set.** This is a release gate, not proof that errors never happen: zero errors in n awards only shows the true error rate is below roughly 3/n. Claiming under 1% needs about 300 clean awards, so the test set keeps growing.
- **At least 7 in 10** clear photos of common items are awarded first time. This stops the system passing the first test by recognising nothing.

**Fun, from five people on a real walk**

- First discovery within 10 minutes outdoors in central London.
- Recorded per walk: discoveries, retakes per successful discovery, and time between discoveries.
- One question afterwards, yes or no: "If you were walking around London next weekend, would you open this without me asking you to?"

## Build order

1. One photo in, one structured recognition result out, and the test script. All items are read from the CSV from this step on.
2. Discovery screen and a collection saved on the device, with persistent storage requested and an "Add to Home Screen" prompt.
3. Test coverage and screens for all items. Done for the revision 4 items.
3a. Revision 5 content: choose the 40 items, write each fact from a source, set verification and radius, and rebuild the test set for them.
4. Location checks, the map and the failure states.
5. Field test in London and threshold tuning.

## Open decisions

- The name. "Clocked" is the working name, but time-tracking apps also use it, and the revision 5 direction (going places and keeping memories) fits it less well. The preferred candidate is **Stamped**: every place is a stamp, like in a passport. Before any public release, check the app stores, a domain and trade marks for the chosen name.
- Stamp look (chosen 10 October 2026, from six options): each discovery turns the player's own photo into a perforated postage stamp, with the place and its category printed below it and a London postmark dated the day it was first found, in the category's ink. The postmark sits on a corner; the photo stays clearly visible. The collection is a fan of stamps per category, and each category opens to an album page. Warm paper, a serif for names (Fraunces), a typewriter face for postal labels (Courier Prime) and DM Sans for text; the fonts are bundled with the app (SIL Open Font License).
- Items checked by vision alone that cause wrong awards at step 5 are dropped or replaced.
- Two things to re-check before launch: the Earl's Court police box may be moved to Hogarth Road, and the Edward VIII post box location rests on one 2015 source.
