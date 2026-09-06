# Fix: cyclone answers mixed unrelated regions, weren't shown as points, and the info box was blank

## Issue 1 — "Pacific" mixed Western + Eastern/Central Pacific storms together
`_REGION_HINTS["pacific"]` intentionally covers three basins (wp/ep/cp)
because "Pacific" genuinely spans all of them — Western Pacific (Philippines/
Japan) and Eastern/Central Pacific (Mexico/Hawaii) are thousands of miles
apart but both correctly match "Pacific". The bug was presentation, not
filtering: all matching storms were flattened into one undifferentiated
list, making it look like unrelated storms had leaked into the answer.

**Fix:** `composer.py::_cyclone_section` now tags each storm with a
human-readable `basin_label` (e.g. "Western Pacific (Philippine Sea / South
China Sea)" vs "Central Pacific (Hawaii)") and groups the reply text AND the
card by basin, with a sub-heading per group whenever more than one basin is
present. A specific region (e.g. "Kolkata", "Philippines") still filters
down to just its own basin, so nothing changes there.

## Issue 2 — reply wasn't shown "in points"
The bulletin lines were already joined with `\n` and "•" bullets in
`composer.py`, but the chat bubble had no `white-space` CSS rule, so the
browser's default (`white-space:normal`) collapsed every newline into a
single space — squashing the whole multi-point reply into one run-on
paragraph.

**Fix:** added `white-space:pre-wrap` to `.bubble` in `FRONTEND/index.html`
so the existing newlines/bullets actually render as separate lines.

## Issue 3 — the info box below the reply was blank ("—" everywhere, always green)
Cyclone answers were rendered through the generic weather stat-grid, which
expects `day`/`current`/`alert` fields that a cyclone answer never
populates — hence Temp/Range/Rain/Wind all showed "—" and the pill was
hardcoded green regardless of an active major hurricane.

**Fix:**
- `composer.py` now computes a real alert level from the most severe active
  storm's category (tropical depression → green, storm → yellow,
  hurricane/typhoon/severe → orange, major/super/extremely-severe → red)
  via `_cyclone_alert()`, and returns it as `alert` + `alert_label`.
- `FRONTEND/index.html` adds `buildCycloneCard()` / `buildCycloneSection()`,
  a dedicated card for cyclone answers: colored alert pill reflecting real
  severity, storms grouped by basin, each storm shown with name/category/
  wind/position, seasonal context, and a wide-area map — instead of reusing
  the irrelevant Temp/Rain/Wind grid.

## Note on "TWENTYTHRE"
That truncated name (missing the final "E" of "TWENTY-THREE") comes directly
from the live RAMMB/CIRA source page, not from our code — unnamed storms are
often labelled with a short numeric/word designator by the source itself
before they're assigned a name. Nothing in our pipeline truncates it.
