# Next Implementations Plan

## Planning Principle

The next work should strengthen the current core loop:

`world data -> AI context -> assistant output -> draft proposal -> review -> apply`

The best next items are the ones that improve this loop for manual testing in
`/app/` while keeping future React migration possible.

## Priority 1: Proposal Quality And Trust

Why now:

- the write-back loop is the heart of the product;
- local models still vary in structured output quality;
- better trust here makes every later module more useful.

Implementation slices:

1. Add clearer proposal-item provenance in the API and UI.
2. Show why a proposal item was created from the assistant response.
3. Improve extraction repair prompts for noisy local model outputs.
4. Add tests for more malformed relationship and rule variants.

Expected result:

- fewer failed saves;
- easier human review before applying world changes.

## Priority 2: Map Pins And Editable Maps

Why now:

- maps are already visible in the UI;
- this is the most natural next step for an existing module;
- it creates strong worldbuilding value without changing the core architecture.

Implementation slices:

1. Add persistent map pin schema and CRUD endpoints.
2. Render pins on uploaded map images in `/app/`.
3. Support pin title, note, linked entity, and coordinates.
4. Add basic edit/delete interactions.

Expected result:

- location-based world knowledge becomes much more usable;
- the maps module stops feeling like a placeholder.

## Priority 3: Random Tables

Why now:

- this is explicitly open in the roadmap;
- it fits worldbuilding workflows well;
- it can reuse the same proposal/review pattern for generated ideas later.

Implementation slices:

1. Add random table schema and storage.
2. Create CRUD API for tables and rows.
3. Add UI for rolling results in `/app/`.
4. Optionally allow AI to suggest entries as draft proposals.

Expected result:

- instant utility during sessions;
- more gameplay-facing value beyond static lore storage.

## Priority 4: Detective Board

Why later:

- high UX value, but broader surface area;
- better after map pins and proposal trust are stable.

Implementation slices:

1. Define board node and connection model.
2. Reuse existing entities as attachable references.
3. Add freeform notes plus evidence links.
4. Add board rendering and editing in the UI.

## Priority 5: React Migration By Feature Parity

Why carefully:

- `/app/` is already the stable manual-testing UI;
- a rewrite before feature stabilization would slow progress.

Implementation slices:

1. Mirror one mature module at a time from `/app/` into `frontend/`.
2. Start with read-heavy views such as context preview or timeline.
3. Move proposal review only after behavior is stable in the static UI.

## Recommended Immediate Order

1. Proposal quality and review clarity.
2. Map pins and editable maps.
3. Random tables.
4. Detective board.
5. React feature-by-feature migration.
