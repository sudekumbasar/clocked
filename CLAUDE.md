# Clocked

Clocked is a phone web app: photograph things you see in a city, the app recognises them, they join your collection. Version 1 is London only.

## Sources of truth

- `PRODUCT.md` is the product definition. Read it before planning or changing anything. If code and PRODUCT.md disagree, PRODUCT.md wins; if PRODUCT.md is unclear, ask.
- `data/london_collection_v4.csv` holds every collectible. Never hard-code a collectible, a fact, a coordinate, a radius or text to match in code.

## Rules that must not be broken

- **A wrong award is worse than a missed one.** When unsure, award nothing.
- **The vision model never awards.** It returns a structured candidate (or null). A separate deterministic step applies the item's verification rules and decides AWARD, RETRY or REJECT.
- **Facts are never generated.** They come from the CSV only.
- **The model API key stays on the server.** Never in client code, never committed.
- **The public build is camera-only and checks location.** Photo upload, "pretend I am here" and reset exist only in development builds and are removed when the public build is made. The server cannot tell a real location from a pretended one, so it has no override field and no development endpoints unless development mode is switched on in its own configuration.
- **Location is never sent to the model provider.** Only our own rules use it.
- **Scope.** Do not build anything listed under "Not in version 1" in PRODUCT.md, even if it would be easy. Suggest it instead.

## How to work

- Follow the build order in PRODUCT.md, one step at a time. Finish and demonstrate a step before starting the next.
- Propose a plan and wait for approval before creating the project structure or choosing a framework, a hosting option or a model provider.
- Keep the model provider behind one small interface so it can be swapped.
- Every recognition rule gets a test. The test script that scores a folder of photos is part of step 1, not an afterthought.
- **Model costs.** The budget is $10. The app uses Claude Sonnet 5.5 (chosen in step 1; see PRODUCT.md). Log the cost of every run that calls the real model and report the running total. Warn the project owner and wait before any run that would take the total past $8.
- **Field test.** Raise the prepaid credit and the budget stop together, and make sure no budget stop can cut the app off in the middle of a walk.
- **API key.** It lives only in `.env` locally and in Secret Manager in the cloud, and is never committed or pasted into a chat.
- **Language.** Code, comments, file contents, commit messages and all text shown in the app are in English.
- When something in PRODUCT.md turns out to be wrong or impractical, say so and propose a change to the document rather than quietly working around it.
