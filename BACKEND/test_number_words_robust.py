from app.nlu import parse_query

def test_bengali_number_words():
    cases = {
        "কলকাতার তাপমাত্রা পরবর্তী এক দিনে": 1,
        "কলকাতার তাপমাত্রা পরবর্তী দুই দিনে": 2,
        "কলকাতার তাপমাত্রা পরবর্তী তিন দিনে": 3,
        "কলকাতার তাপমাত্রা পরবর্তী চার দিনে": 4,
        "কলকাতার তাপমাত্রা পরবর্তী পাঁচ দিনে": 5,
        "কলকাতার তাপমাত্রা পরবর্তী ছয় দিনে": 6,
        "কলকাতার তাপমাত্রা পরবর্তী সাত দিনে": 7,
        "কলকাতার তাপমাত্রা পরবর্তী ৫ দিনে": 5,
        "কলকাতার তাপমাত্রা পরবর্তী ৫ দিনে": 5,
        "কলকাতার তাপমাত্রা পরবর্তী পাঁচটি দিনে": 5,
        "কলকাতার তাপমাত্রা পরবর্তী পাঁচটা দিনে": 5,
        "কলকাতার তাপমাত্রা পরবর্তী পাঁচদিনে": 5,
        "কলকাতার তাপমাত্রা পরবর্তী পাঁচ\u200c দিনে": 5,
    }
    for text, expected in cases.items():
        q = parse_query(text)
        assert q.intent == "forecast", (text, q)
        assert q.horizon_days == expected, (text, q)
        assert q.location_text == "কলকাতা", (text, q)

def test_english_and_hindi_words():
    assert parse_query("Kolkata weather next five days").horizon_days == 5
    assert parse_query("Delhi weather next six days").horizon_days == 6
    assert parse_query("दिल्ली का तापमान अगले पाँच दिनों में").horizon_days == 5

def test_digit_forms():
    assert parse_query("Kolkata next 5 days").horizon_days == 5
    assert parse_query("কলকাতা পরবর্তী ৫ দিনে").horizon_days == 5
