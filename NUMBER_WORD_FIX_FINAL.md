# Forecast Number-Word Fix (Final)

Fixed Bengali compound day-count phrases that were previously missed.

Examples now parsed correctly:
- ঢাকা শহরের পরবর্তী দুদিনের তাপমাত্রা -> 2 days
- ঢাকা শহরের পরবর্তী দুইদিনের তাপমাত্রা -> 2 days
- কলকাতার পরবর্তী তিনদিনের তাপমাত্রা -> 3 days
- কলকাতার পরবর্তী পাঁচদিনের তাপমাত্রা -> 5 days
- কলকাতার পরবর্তী ছয়দিনের তাপমাত্রা -> 6 days
- Bengali digits and separated forms remain supported.

The parser resolves explicit horizons before generic day-offset words and strips the entire
horizon from the location query. This prevents "দুদিনের" / "পাঁচদিনের" from being sent to
geocoding and prevents fallback to the default 7-day forecast.

Validation:
- tests/test_nlu.py: 7 passed
- Direct parser checks: 2-day, 2-day separated, and 5-day compound Bengali phrases passed.
