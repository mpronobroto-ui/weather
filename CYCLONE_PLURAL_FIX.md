# Fix: "cyclones" (plural) not detected as an alert-intent query

## Bug
`BACKEND/app/nlu.py` classified queries like **"cyclones in kolkata"** as the
generic `current` weather intent instead of the `alert` intent, so they never
reached the dedicated cyclone-report branch in `composer.py` (IMD/NHC/RAMMB
active-storm lookup). Singular "cyclone" worked; plural "cyclones" did not.

## Root cause
`_match_keyword()` in `nlu.py` matches keywords with strict word boundaries:

    (?<!\w)cyclone(?!\w)

This deliberately prevents partial-word collisions (e.g. "hi" inside "Delhi").
But it also blocks legitimate plural matches: in "cyclones", the letter "s"
immediately follows "cyclone", so the `(?!\w)` boundary fails and the keyword
never matches.

`INTENT_KEYWORDS["alert"]` only listed the singular forms ("cyclone", "flood",
"storm", "warning", "alert"), so any plural phrasing silently fell through to
the default "current" intent.

## Fix
Added the plural forms alongside each singular keyword in
`INTENT_KEYWORDS["alert"]`:

    alert, alerts, warning, warnings, cyclone, cyclones,
    flood, floods, storm, storms, danger, warn

## Verification
    "cyclones in kolkata"          -> intent=alert,   location=kolkata   (was: current)
    "cyclone in kolkata"           -> intent=alert,   location=kolkata   (unchanged)
    "is there a cyclone near chennai" -> intent=alert, location=chennai  (unchanged)
    "storms in mumbai"             -> intent=alert,   location=mumbai   (was: current)
    "floods in bihar"              -> intent=alert,   location=bihar    (was: current)
    "weather in kolkata"           -> intent=current, location=kolkata  (unaffected)
    "will it rain in kolkata"      -> intent=umbrella,location=kolkata  (unaffected)

Existing test `tests/test_nlu.py::"any cyclone alert near Chennai?"` still
passes (singular form was already correct before this fix).
