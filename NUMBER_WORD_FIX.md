# Multilingual forecast number-word fix

The NLU now resolves an explicit forecast horizon **before** single-day keywords such as `tomorrow`, `আগামীকাল`, or `कल`.

Supported examples include:

- Bengali: `এক`, `দুই`, `তিন`, `চার`, `পাঁচ`, `ছয়/ছয়`, `সাত`
- Bengali forms: `পাঁচ দিন`, `পাঁচ দিনে`, `পাঁচ দিনের`, `পাঁচটি দিন`
- Bengali digits: `৫ দিনে`
- Hindi: `एक`, `दो`, `तीन`, `चार`, `पाँच/पांच`, `छह/छः`, `सात`
- English: `one` through `seven`
- Latin/Banglish forms already present in `NUMBER_WORDS`

Examples:

`কলকাতার তাপমাত্রা পরবর্তী পাঁচ দিনে` -> `horizon_days=5`, `intent=forecast`, `location=কলকাতা`

`Kolkata weather next five days` -> `horizon_days=5`, `intent=forecast`, `location=Kolkata`

`दिल्ली का तापमान अगले पाँच दिनों में` -> `horizon_days=5`, `intent=forecast`, `location=दिल्ली`

Explicit horizons are capped at 7 days. The location extractor also removes the multilingual number-word horizon before geocoding so words such as `পাঁচ` cannot leak into the location.

Tests: `BACKEND/tests/test_nlu.py` contains coverage for all Bengali 1–7 number words plus English and Hindi examples.
