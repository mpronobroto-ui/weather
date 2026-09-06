from app import nlu


def test_parse_query_intents():
    p1 = nlu.parse_query("hi")
    assert p1.intent == "greeting"

    p2 = nlu.parse_query("what can you do?")
    assert p2.intent == "help"

    p3 = nlu.parse_query("will it rain tomorrow in Delhi?")
    assert p3.intent == "umbrella"
    assert p3.day_offset == 1
    assert p3.location_text == "Delhi"

    p4 = nlu.parse_query("any cyclone alert near Chennai?")
    assert p4.intent == "alert"
    assert p4.location_text == "Chennai"

    p5 = nlu.parse_query("crop farming advisory for Punjab")
    assert p5.intent == "agriculture"
    assert "Punjab" in (p5.location_text or "")

    p6 = nlu.parse_query("solar power output forecast for Jaipur")
    assert p6.intent == "energy"
    assert "Jaipur" in (p6.location_text or "")

    p8 = nlu.parse_query("weather of digha")
    assert p8.intent == "current"
    assert p8.location_text == "digha"

    p9 = nlu.parse_query("weather of kalighat")
    assert p9.intent == "current"
    assert p9.location_text == "kalighat"

    p10 = nlu.parse_query("weather of dakshineswar")
    assert p10.intent == "current"
    assert p10.location_text == "dakshineswar"

    p11 = nlu.parse_query("weather in Delhi")
    assert p11.intent == "current"
    assert p11.location_text == "Delhi"

    p12 = nlu.parse_query("weather at kathmandu")
    assert p12.intent == "current"
    assert p12.location_text == "kathmandu"

    p14 = nlu.parse_query("weather at rajarhat, kolkata")
    assert p14.intent == "current"
    assert "rajarhat, kolkata" in (p14.location_text or "").lower()

    p15 = nlu.parse_query("weather at chinar park, kolkata")
    assert p15.intent == "current"
    assert "chinar park, kolkata" in (p15.location_text or "").lower()

    p16 = nlu.parse_query("weather in bandra, mumbai")
    assert p16.intent == "current"
    assert "bandra, mumbai" in (p16.location_text or "").lower()


def test_parse_query_multilingual():
    p_hi = nlu.parse_query("क्या कल दिल्ली में बारिश होगी?")
    assert p_hi.intent == "umbrella"
    assert "दिल्ली" in (p_hi.location_text or "")

    p_bn = nlu.parse_query("কলকাতায় কাল আবহাওয়া কেমন?")
    assert p_bn.intent in ("forecast", "current")
    assert "কলকাতা" in (p_bn.location_text or "")

    # Bengali script: "আজকে মুম্বাই এর তাপমাত্রা কত" must extract Mumbai, not GPS default
    p_bn2 = nlu.parse_query("আজকে মুম্বাই এর তাপমাত্রা কত")
    assert p_bn2.intent == "current"
    assert p_bn2.location_text == "মুম্বাই"

    # Banglish: "Aaj ke Kolkata er weather ki?"
    p_bl = nlu.parse_query("Aaj ke Kolkata er weather ki?")
    assert p_bl.intent == "current"
    assert "Kolkata" in (p_bl.location_text or "")

    # Fused locative suffix
    p_bn3 = nlu.parse_query("কলকাতায় আবহাওয়া")
    assert p_bn3.location_text == "কলকাতা"

    p_bn4 = nlu.parse_query("মুম্বাই এর তাপমাত্রা")
    assert p_bn4.location_text == "মুম্বাই"

    # Fused Banglish "tapmatra" / "taapmatra" must not stick to the city name
    p_tap = nlu.parse_query("Kolkata tapmatra")
    assert p_tap.location_text == "Kolkata"
    p_tap2 = nlu.parse_query("what is kolkata tapmatra")
    assert p_tap2.location_text == "kolkata"
    p_tap3 = nlu.parse_query("Kolkata er taapmatra koto")
    assert p_tap3.location_text == "Kolkata"


def test_split_multi_location():
    assert nlu.split_multi_location("Chennai and Kolkata") == ["Chennai", "Kolkata"]
    assert nlu.split_multi_location("Mumbai / Pune") == ["Mumbai", "Pune"]
    assert nlu.split_multi_location("Rajarhat, Kolkata") == ["Rajarhat, Kolkata"]
    assert nlu.split_multi_location("Delhi") == ["Delhi"]
    assert nlu.split_multi_location("") == []


def test_multilingual_number_word_horizons():
    cases = [
        ("কলকাতার তাপমাত্রা পরবর্তী পাঁচ দিনে", 5),
        ("কলকাতার তাপমাত্রা পরবর্তী চার দিনে", 4),
        ("কলকাতার তাপমাত্রা পরবর্তী সাত দিনে", 7),
        ("दिल्ली का तापमान अगले पाँच दिनों में", 5),
        ("Chennai temperature next five days", 5),
        ("Kolkata weather for five days", 5),
    ]
    for text, expected in cases:
        parsed = nlu.parse_query(text)
        assert parsed.horizon_days == expected, (text, parsed)
        assert parsed.intent == "forecast", (text, parsed)


def test_number_words_all_bengali_forecast_horizons():
    cases = [
        ("কলকাতার তাপমাত্রা পরবর্তী এক দিনে", 1),
        ("কলকাতার তাপমাত্রা পরবর্তী দুই দিনে", 2),
        ("কলকাতার তাপমাত্রা পরবর্তী তিন দিনে", 3),
        ("কলকাতার তাপমাত্রা পরবর্তী চার দিনে", 4),
        ("কলকাতার তাপমাত্রা পরবর্তী পাঁচ দিনে", 5),
        ("কলকাতার তাপমাত্রা পরবর্তী ছয় দিনে", 6),
        ("কলকাতার তাপমাত্রা পরবর্তী সাত দিনে", 7),
        ("কলকাতার তাপমাত্রা পরবর্তী ৫ দিনে", 5),
        ("কলকাতার তাপমাত্রা পরবর্তী ৫ দিন", 5),
        ("কলকাতার তাপমাত্রা আগামী পাঁচ দিনের", 5),
    ]
    for text, expected in cases:
        parsed = nlu.parse_query(text)
        assert parsed.horizon_days == expected, (text, parsed)
        assert parsed.intent == "forecast", (text, parsed)
        assert parsed.location_text == "কলকাতা", (text, parsed)


def test_number_words_english_and_hindi_forecast_horizons():
    cases = [
        ("Kolkata weather next one day", 1),
        ("Kolkata weather next two days", 2),
        ("Kolkata weather next three days", 3),
        ("Kolkata weather next four days", 4),
        ("Kolkata weather next five days", 5),
        ("Kolkata weather next six days", 6),
        ("Kolkata weather next seven days", 7),
        ("दिल्ली का तापमान अगले चार दिनों में", 4),
        ("दिल्ली का तापमान अगले छह दिनों में", 6),
    ]
    for text, expected in cases:
        parsed = nlu.parse_query(text)
        assert parsed.horizon_days == expected, (text, parsed)
        assert parsed.intent == "forecast", (text, parsed)


def test_bengali_compound_day_number_words():
    cases = [
        ("ঢাকা শহরের পরবর্তী দুদিনের তাপমাত্রা", 2),
        ("ঢাকা শহরের পরবর্তী দুইদিনের তাপমাত্রা", 2),
        ("কলকাতার পরবর্তী তিনদিনের তাপমাত্রা", 3),
        ("কলকাতার পরবর্তী চারদিনের তাপমাত্রা", 4),
        ("কলকাতার পরবর্তী পাঁচদিনের তাপমাত্রা", 5),
        ("কলকাতার পরবর্তী ছয়দিনের তাপমাত্রা", 6),
        ("কলকাতার পরবর্তী সাতদিনের তাপমাত্রা", 7),
    ]
    for text, expected in cases:
        parsed = nlu.parse_query(text)
        assert parsed.horizon_days == expected, (text, parsed)
        assert parsed.intent == "forecast", (text, parsed)
