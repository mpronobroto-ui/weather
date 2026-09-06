"""
Query-understanding engine.

Design choice for the hackathon: ship a deterministic, dependency-free rule
engine as the DEFAULT path so the demo works instantly with no API key, then
let `llm.py` optionally take over parsing (and final phrasing) when an LLM
key (OpenAI / Gemini / a local Llama via Ollama) is configured in the
environment. Judges can therefore see both a zero-cost baseline and the
"real" LLM-in-the-loop mode by just setting an env var.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

INTENT_KEYWORDS = {
    "aqi": [
        "aqi", "air quality", "pm2.5", "pm2_5", "pm10", "pollution",
        "vaayu gunvatta", "vayu gunvatta", "pradushan", "pradooshan",
        "वायु गुणवत्ता", "प्रदूषण", "air pollution",
    ],
    "alert": [
        "alert", "alerts", "warning", "warnings", "cyclone", "cyclones", "flood", "floods",
        "storm", "storms", "danger", "warn",
        "chetavani", "chetavni", "baadh", "badh", "toofan", "tufan", "chakravaat", "chakrawat",
        "चेतावनी", "अलर्ट", "बाढ़", "तूफान", "चक्रवात",
        "সতর্কতা", "বন্যা", "ঘূর্ণিঝড়",
        "எச்சரிக்கை", "புயல்", "வெள்ளம்",
        "హెచ్చరిక", "తుఫాను", "వరద",
        "इशारा", "पूर", "चक्रीवादळ",
    ],
    "umbrella": [
        "umbrella", "rain", "raining", "rainfall", "precip", "wet", "shower",
        "take umbrella", "need umbrella", "carry umbrella", "will it rain",
        "baarish", "barish", "baarish hogi", "barsaat", "barsat", "varsha", "chatri", "chhatri",
        "छतरी", "बारिश", "वर्षा", "बरसात",
        "ছাতা", "বৃষ্টি",
        "குடை", "மழை",
        "గొడుగు", "వర్షం",
        "छत्री", "पाऊस",
    ],
    "forecast": [
        "forecast", "week", "tomorrow", "next", "coming days", "7 day", "5 day",
        "अगले", "अगला", "अगली", "agle", "agla", "agli", "agale", "aglaa", "hafta", "saptah",
        "पूर्वानुमान", "कल", "अगले", "सप्ताह",
        "পূর্বাভাস", "আগামীকাল", "সপ্তাহ",
        "முன்னறிவிப்பு", "நாளை", "வாரம்",
        "సూచన", "రేపు", "వారం",
        "अंदाज", "उद्या", "आठवडा",
    ],
    "historical": [
        "past weather", "past weather report", "historical weather", "historical report",
        "weather history", "weather report history", "previous weather", "previous days",
        "last few days", "last days", "yesterday", "day before yesterday",
        "yesterday's weather", "past day", "past days", "on this date",
        "গতকালের আবহাওয়া", "গতকাল", "আগের দিনের আবহাওয়া", "পূর্বের আবহাওয়া",
        "पिछले दिनों का मौसम", "कल का मौसम", "कल का मौसम कैसा था", "पिछला मौसम",
        "bar yesterday", "kal ka weather", "kal ka mausam", "pichle din", "pichle dino ka weather",
    ],
    "climate": [
        "climate", "trend", "history", "historical", "average", "past years", "over the years",
        "जलवायु", "इतिहास", "औसत", "पिछले वर्ष",
        "জলবায়ু", "ইতিহাস", "গড়",
        "காலநிலை", "வரலாறு", "சராசரி",
        "వాతావరణ ధోరణి", "చరిత్ర", "సగటు",
    ],
    "agriculture": [
        "crop", "farm", "farmer", "sowing", "irrigation", "agri",
        "फसल", "किसान", "खेत", "सिंचाई", "बुवाई",
        "ফসল", "কৃষক", "চাষ",
        "பயிர்", "விவசாயி", "பாசனம்",
        "పంట", "రైతు", "సాగు",
    ],
    "aviation": [
        "flight", "aviation", "airport", "pilot", "runway", "taf", "metar",
        "उड़ान", "विमान", "हवाई अड्डा",
        "ফ্লাইট", "বিমান",
        "விமானம்", "விமான நிலையம்",
    ],
    "marine": [
        "sea", "marine", "fisherman", "fishing", "coast", "boat", "ocean",
        "समुद्र", "मछुआरे", "तट",
        "সমুদ্র", "জেলে", "উপকূল",
        "கடல்", "மீனவர்", "கடற்கரை",
        "సముద్రం", "మత్స్యకారుడు",
    ],
    "urban": [
        "city", "urban", "municipal", "drainage", "waterlogging", "smart city",
        "shehar", "sheher", "nagar",
        "शहर", "नगर", "जलभराव",
        "শহর", "পৌর", "জলাবদ্ধতা",
        "நகரம்", "வடிகால்",
    ],
    "energy": [
        "solar", "renewable", "wind turbine", "turbine", "energy", "irradiance",
        "grid operator", "power output", "energy grid", "energy forecast",
        "सौर", "पवन ऊर्जा", "ऊर्जा",
    ],
    "retail": [
        "retail", "inventory", "stock up", "restock", "shop", "store", "shopkeeper",
        "sales forecast", "consumer demand", "दुकान", "स्टॉक",
    ],
    "construction": [
        "construction", "crane", "site manager", "contractor", "build schedule",
        "work stoppage", "scaffolding", "जोखिम निर्माण", "निर्माण स्थल",
    ],
    "greeting": [
        "hi", "hello", "hey", "namaste", "नमस्ते", "हाय", "হ্যালো", "வணக்கம்", "నమస్తే",
    ],
    "help": [
        "what can you do", "what can you help", "what can i ask", "what do you do",
        "how do you work", "how does this work", "help", "commands", "capabilities",
        "features", "what are you", "who are you", "what is this", "instructions",
        "how to use", "user guide", "options", "menu",
        "तुम क्या कर सकते हो", "मदद", "सहायता",
        "তুমি কী করতে পারো", "সাহায্য",
        "நீ என்ன செய்ய முடியும்", "உதவி",
        "నువ్వు ఏమి చేయగలవు", "సహాయం",
    ],
    "current": [
        "now", "current", "today", "right now", "abhi", "aaj",
        "अभी", "आज", "वर्तमान",
        "এখন", "আজ",
        "இப்போது", "இன்று",
        "ఇప్పుడు", "ఈరోజు",
    ],
}

# Words to strip out before what's left is treated as a location candidate.
STOPWORDS = set(
    """
    the a an is are was were will would can could may might in at on of for to my your our weather forecast
    tell me what is show give please today tomorrow tommorow tomorow now current next week
    help commands capabilities features instructions guide options menu
    happen happens happening let know going get
    climate trend history alert warning crop farm farmer flight aviation
    marine sea fishing city urban
    how about umbrella rain raining rainfall
    take need carry should i do you think there any near around about
    with without along having including plus via using against onto into
    cyclone cyclones storm storms flood floods danger warn
    suggestions suggestion risk impact under due heavy
    alerts alert
    solar renewable wind turbine energy irradiance grid operator power output outlook
    generation generate generating and or forecast location locations device gps here me
    retail inventory stock up restock shop store shopkeeper sales consumer demand
    construction crane site manager contractor build schedule work stoppage scaffolding
    aqi air quality pollution pm2.5 pm10 kya hai ka ki ke mein batao dikhao mera mere area aaj kal kaisa kaisi
    temperature degree degrees percent humidity wind speed pressure level condition conditions

    और का की के में है हैं क्या मौसम पर को से तक
    बताओ बताइए बताना दिखाओ जानिए जानकारी कृपया प्लीज
    कैसा कैसी कैसे कल आज अभी परसों की के लिए पास कोई चाहिए ले जानी
    कितना कितनी कितने तापमान ताप डिग्री मात्रा गर्मी ठंड नमी आर्द्रता हवा गति दबाव स्तर प्रतिशत
    होगा होगी होंगे रहेगा रहेगी रहेंगे था थी थे हो रहा रही रहे हुआ हुई हुए
    मुझे मुझको मेरा मेरी मेरे अपने अपनी अपना
    दिन दिनों दिवस दिवसों दोनों रोज हफ्ता हफ्ते हफ्तों सप्ताह महीना महीने माह अगले अगला अगली

    পরিস্থিতি কেমন আজ আজকে আজকের আবহাওয়া আবহাওয়ার কেমন কাল কালকের এখন কত
    তাপমাত্রা তাপমাত্রার ডিগ্রি ডিগ্রী বল দেখাও অনুগ্রহ করে বলো জানাও
    বৃষ্টি বাতাস আর্দ্রতা চাপ গতি কি কিসের কী কীসের এর এ তে তেই কে থেকে
    দিয়ে দিয়ে সহ বনাম হবে হচ্ছে ছিল আছে আমি আপনি তুমি আমাদের
    প্রথম দ্বিতীয় তৃতীয় পরবর্তী আগামী আসন্ন দিন দিনে দিনের সপ্তাহ সপ্তাহে
    সপ্তাহের মাস মাসে বছর পরের পরেরটা পরেরটি
    weather ki koto kotoota temp temperature aajke aajker aaj er e te
    first next coming days day week month prothom prothomta dine diner
    bangla banglish

    வானிலை எப்படி இருக்கும் இன்று என்ன நாளை இப்போது எவ்வளவு வெப்பநிலை சொல்லு காட்டு
    ఏమిటి ఎలా ఉంది ఈరోజు రేపు ఇప్పుడు ఎంత ఉష్ణోగ్రత చెప్పు చూపించు

    agle agla agli agale aglaa peechla pichla parso parson abhi
    tapman tapmaan taapman taapmaan taap tap matra maatra degree
    # Fused Banglish spellings people type without spaces
    tapmatra taapmatra tapmatr taapmatr tampmatra tampmatr
    temperature temprature temparature tempature
    kitna kitni kitne kitnaa kitnee kitnay koto kotoota
    garmi garmee thand thandi nami aardrata hawa havaa gati raftaar dabaav pratishat
    hoga hogi honge hoyega hoyegi rahega rahegi rahenge tha thi the
    raha rahi rahe hua hui hue
    mujhe mujhko mera meri mere apne apni apna
    din dinon dino divas divason dono dohno roz hafte hafton saptah mahina mahine mah
    last past previous historical history report reports yesterday yesterdays
    days day week weeks month months on date dated
    january february march april may june july august september october november december
    jan feb mar apr jun jul aug sep sept oct nov dec
    par se tak chahiye lena jaani paas koi aur bata bataye bataiye dikha dikhaye
    """.split()
)



DAY_WORDS = {
    "today": 0, "आज": 0, "আজ": 0, "আজকে": 0, "আজকের": 0, "இன்று": 0, "ఈరోజు": 0,
    "aaj": 0, "aajke": 0, "aajker": 0,
    "tomorrow": 1, "tommorow": 1, "tomorow": 1, "tomorro": 1,
    "कल": 1, "আগামীকাল": 1, "কাল": 1, "কালকের": 1, "நாளை": 1, "రేపు": 1, "kal": 1,
    "day after tomorrow": 2, "परसों": 2, "parso": 2, "parson": 2,
}


# Number words used for forecast horizons.  This is deliberately kept in the
# rule-based NLU instead of relying on an LLM, so "পাঁচ দিনে" and equivalent
# phrases always produce the same 5-day result as the digit "5".
NUMBER_WORDS = {
    "one": 1, "a": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "ek": 1, "dui": 2, "tin": 3, "teen": 3, "char": 4, "chaar": 4, "panch": 5, "paanch": 5, "che": 6, "chhe": 6, "saat": 7,
    "এক": 1, "দুই": 2, "দু": 2, "দুইটি": 2, "দুটো": 2, "তিন": 3, "চার": 4, "চারটি": 4, "চারটা": 4, "পাঁচ": 5, "পাচ": 5, "পাঁচটি": 5, "পাঁচটা": 5, "পাঁচটা": 5, "পাচটা": 5, "ছয়": 6, "ছয়": 6, "ছয়টা": 6, "ছয়টা": 6, "সাত": 7, "সাতটা": 7,
    "একটি": 1, "দুইটি": 2, "তিনটি": 3, "চারটি": 4, "পাঁচটি": 5, "ছয়টি": 6, "ছয়টি": 6, "সাতটি": 7,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5, "पांच": 5, "छह": 6, "छः": 6, "सात": 7,
    "ஒன்று": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4, "ஐந்து": 5, "ஆறு": 6, "ஏழு": 7,
    "ఒకటి": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5, "ఆరు": 6, "ఏడు": 7,
    "दोन": 2, "पाच": 5, "सहा": 6,
    "એક": 1, "બે": 2, "ત્રણ": 3, "ચાર": 4, "પાંચ": 5, "છ": 6, "સાત": 7,
    "ਇੱਕ": 1, "ਦੋ": 2, "ਤਿੰਨ": 3, "ਚਾਰ": 4, "ਪੰਜ": 5, "ਛੇ": 6, "ਸੱਤ": 7,
    "ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5, "ಆರು": 6, "ಏಳು": 7,
    "ഒന്ന്": 1, "രണ്ട്": 2, "മൂന്ന്": 3, "നാല്": 4, "അഞ്ച്": 5, "ആറ്": 6, "ഏഴ്": 7,
    "ଏକ": 1, "ଦୁଇ": 2, "ତିନି": 3, "ଚାରି": 4, "ପାଞ୍ଚ": 5, "ଛଅ": 6, "ସାତ": 7,
    "ایک": 1, "دو": 2, "تین": 3, "چار": 4, "پانچ": 5, "چھ": 6, "سات": 7,
}

# Number words are query operators, not place-name tokens.  Adding them to
# STOPWORDS also prevents "পাঁচ", "চার", etc. from leaking into geocoding.
STOPWORDS.update(NUMBER_WORDS.keys())


WORD_CHAR_PATTERN = r"[\w\u0900-\u097F\u0980-\u09FF\u0B80-\u0BFF\u0C00-\u0C7F]"


def _match_keyword(pattern_text: str, text: str) -> bool:
    """Match a keyword or multi-word phrase against text respecting word boundaries.
    Avoids accidental partial-word collisions like 'hi' matching inside 'Dakshineswar' or 'Delhi'."""
    pat = rf"(?<!{WORD_CHAR_PATTERN}){re.escape(pattern_text.lower())}(?!{WORD_CHAR_PATTERN})"
    return bool(re.search(pat, text, re.IGNORECASE))


def _strip_keyword(pattern_text: str, text: str) -> str:
    """Remove a keyword or multi-word phrase from text respecting word boundaries."""
    pat = rf"(?<!{WORD_CHAR_PATTERN}){re.escape(pattern_text)}(?!{WORD_CHAR_PATTERN})"
    return re.sub(pat, " ", text, flags=re.IGNORECASE)


@dataclass
class ParsedQuery:
    intent: str = "current"
    location_text: str | None = None
    day_offset: int = 0
    horizon_days: int = 7
    historical_start_date: str | None = None
    historical_end_date: str | None = None
    raw_text: str = ""
    matched_keywords: list[str] = field(default_factory=list)


def _detect_intent(text_lower: str) -> tuple[str, list[str]]:
    scores: dict[str, list[str]] = {}
    for intent, words in INTENT_KEYWORDS.items():
        hits = [w for w in words if _match_keyword(w, text_lower)]
        if hits:
            scores[intent] = hits

    if "aqi" in scores:
        return "aqi", scores["aqi"]

    # Same idea for the newer sector intents: a specific word like "solar"
    # or "crane" should win even if a generic word like "forecast" also
    # matched (e.g. "solar energy forecast for Jaipur").
    ENERGY_STRONG = ("solar", "renewable", "wind turbine", "turbine", "irradiance", "energy grid", "power output")
    if "energy" in scores and any(_match_keyword(s, text_lower) for s in ENERGY_STRONG):
        return "energy", scores["energy"]

    RETAIL_STRONG = ("retail", "inventory", "stock up", "restock", "shopkeeper", "sales forecast", "consumer demand")
    if "retail" in scores and any(_match_keyword(s, text_lower) for s in RETAIL_STRONG):
        return "retail", scores["retail"]

    CONSTRUCTION_STRONG = ("crane", "construction site", "work stoppage", "build schedule", "scaffolding", "site manager")
    if "construction" in scores and any(_match_keyword(s, text_lower) for s in CONSTRUCTION_STRONG):
        return "construction", scores["construction"]

    # priority order: historical > alert > umbrella > climate > forecast > sectors > current
    for intent in [
        "aqi", "historical", "alert", "umbrella", "climate", "forecast", "agriculture", "aviation",
        "marine", "urban", "energy", "retail", "construction", "greeting", "help", "current",
    ]:
        if intent in scores:
            return intent, scores[intent]
    return "current", []


# Bengali digits → ASCII for horizon parsing ("৭" → "7")
_BN_DIGIT_MAP = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
# Hindi/Devanagari digits
_HI_DIGIT_MAP = str.maketrans("०१२३४५६७८९", "0123456789")


def _normalize_indic_digits(text: str) -> str:
    return text.translate(_BN_DIGIT_MAP).translate(_HI_DIGIT_MAP)


# Normalize invisible Unicode formatting marks that Bengali/Indic keyboards can
# insert between a number word and "দিন" (e.g. পাঁচ\u200c দিনে).  This keeps
# word-number detection stable across browsers, keyboards and copy/paste.
def _normalize_query_text(text: str) -> str:
    text = _normalize_indic_digits(text)
    return re.sub(r"[​‌‍﻿]", "", text)


def _detect_day_offset(text_lower: str) -> tuple[int, int]:
    """Return (start-day offset, forecast horizon).

    This parser deliberately resolves an explicit *horizon* before resolving
    single-day words such as "tomorrow", "আগামীকাল", or "कल".  That ordering
    is important for natural-language queries such as:

        "কলকাতার তাপমাত্রা পরবর্তী পাঁচ দিনে" -> 5
        "दिल्ली का तापमान अगले पाँच दिनों में" -> 5
        "Kolkata weather next five days" -> 5

    Supports Arabic/Latin digits, Bengali/Devanagari digits, and number words
    in the languages represented by NUMBER_WORDS. Forecasts are capped at
    seven days because the weather API/UI supports a maximum seven-day view.
    """
    text_norm = _normalize_query_text(text_lower)

    # Build a boundary-safe number token.  Do NOT use \b around Indic words:
    # Python's \w/\b handling can split Indic text around combining marks.
    word_pattern = "|".join(
        re.escape(w) for w in sorted(NUMBER_WORDS, key=len, reverse=True)
    )
    number_token = rf"(?:[1-9]|1[0-6]|{word_pattern})"

    day_unit = (
        r"(?:days?|day|din(?:on)?|divas(?:on)?|hafte?|hafton?|saptah|"
        r"दिन(?:ों|ो)?|दिवस(?:ों|ो)?|हफ़्त[ेों]?|हफ्त[ेों]?|सप्ताह(?:ों)?|"
        r"দিন(?:ে|ের|গুলি|গুলিতে|গুলোর|টা|টি)?|সপ্তাহ(?:ে|ের|গুলি)?|"
        r"நாட்கள்?|நாள்|రోజులు?|రోజు)"
    )

    def _number_value(raw: str) -> int | None:
        raw = raw.strip().lower()
        if raw.isdigit():
            return int(raw)
        return NUMBER_WORDS.get(raw)

    # 1) Explicit N + day-unit.  This is checked FIRST so "পরবর্তী পাঁচ দিনে"
    # cannot be intercepted by the generic "পরবর্তী" day-offset keyword.
    horizon_re = re.compile(
        rf"(?<!{WORD_CHAR_PATTERN})({number_token})\s*(?:-\s*)?{day_unit}"
        rf"(?!{WORD_CHAR_PATTERN})",
        re.IGNORECASE,
    )
    m = horizon_re.search(text_norm)
    if m:
        requested = _number_value(m.group(1))
        if requested is not None:
            return 0, max(1, min(requested, 7))

    # 2) Prefix forms where a language inserts words between "next/first" and
    # the number, e.g. "পরবর্তী পাঁচ দিনে", "next five days", "अगले पाँच दिनों".
    prefix = (
        r"(?:প্রথম|পরবর্তী|আগামী|আসন্ন|পরের|first|next|coming|"
        r"আগামী|পরবর্তী|अगले|अगला|अगली|पिछले|"
        r"agle|agla|agli|agale|pehle|pichle|"
        r"पहले|अगले)"
    )
    prefixed_re = re.compile(
        rf"{prefix}\s*(?:का|की|के|এর|র)?\s*"
        rf"({number_token})\s*(?:-\s*)?{day_unit}",
        re.IGNORECASE,
    )
    m = prefixed_re.search(text_norm)
    if m:
        requested = _number_value(m.group(1))
        if requested is not None:
            return 0, max(1, min(requested, 7))

    # 3) Week requests.
    if re.search(
        r"(?<!\w)(?:one\s+)?week(?:s)?(?!\w)|"
        r"সপ্তাহ|সপ্তাহে|সপ্তাহের|सप्ताह|हफ्ता|हफ्ते|हफ़्ता|हफ़्ते",
        text_norm,
        re.IGNORECASE,
    ):
        return 0, 7

    # 4) Only after an explicit horizon has been ruled out, handle single-day
    # offset words such as tomorrow/আগামীকাল/कल.
    for phrase, offset in sorted(DAY_WORDS.items(), key=lambda x: len(x[0]), reverse=True):
        if _match_keyword(phrase, text_lower) or _match_keyword(phrase, text_norm):
            return offset, 1

    return 0, 7


_DEVICE_LOCATION_RE = re.compile(
    r"\b(my|current|this|our)\s+location\b|\bnear\s+me\b|\baround\s+me\b|\bmy\s+area\b|"
    r"\bwhere\s+i\s+am\b|\bhere\b",
    re.IGNORECASE,
)

# Hindi (and other Indic) grammar is postpositional: the place name comes
# BEFORE words like "में"/"का"/"पर" ("Kolkata *mein*"), the mirror image of
# English "in Kolkata". The English connector regex below can never match
# these, so a query like "कोलकाता का तापमान कितना है" fell through to pure
# stopword-stripping, and any word the stopword list hadn't anticipated
# (तापमान, कितना, ...) stayed glued to the place name and broke geocoding.
#
# A query can also contain MORE THAN ONE postposition, e.g. "अगले 7 दिनों
# का कोलकाता का तापमान" ("next 7 days' Kolkata temperature") has one "का"
# after the day-count and another after the actual city. Splitting on every
# postposition and cleaning each resulting segment (rather than matching
# only the first one) means whichever segment survives stopword-stripping —
# here "कोलकाता" — is the one used, instead of accidentally grabbing the
# leftover of a time phrase like "दिनों" and feeding that to the geocoder.
_HINDI_POSTPOSITIONS = ("में", "का", "की", "के", "पर", "को", "से", "तक")
# NOTE: plain \b is unsafe here — Python's \w does not treat Devanagari
# vowel signs (matras) as word characters, so \b finds a "boundary" in the
# middle of ordinary words that merely happen to contain a postposition as
# a substring (e.g. "को" inside "कोलकाता" = क + ो + ल...). Using the same
# WORD_CHAR_PATTERN class as _match_keyword/_strip_keyword above avoids
# that false split.
_HINDI_POSTPOSITION_SPLIT_RE = re.compile(
    rf"\s+(?:{'|'.join(_HINDI_POSTPOSITIONS)})(?!{WORD_CHAR_PATTERN})"
)
_HAS_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

# Same idea for transliterated ("Hinglish") queries typed in Latin script —
# "Kolkata mein", "Mumbai ka". Plain \b IS safe here since this is plain
# ASCII with no combining-mark quirk.
_HINGLISH_POSTPOSITIONS = ("mein", "ka", "ki", "ke", "par", "ko", "se", "tak")
_HINGLISH_POSTPOSITION_SPLIT_RE = re.compile(
    r"\s+(?:" + "|".join(_HINGLISH_POSTPOSITIONS) + r")\b", re.IGNORECASE
)

# Bengali (and Banglish) is also postpositional. Common patterns:
#   "মুম্বাই এর তাপমাত্রা"  /  "কলকাতার আবহাওয়া"  /  "Kolkata er weather"
#   "কলকাতায়" (locative -য় / -তে suffix glued to the place name)
# Split on the free-standing postpositions and also strip the common
# locative/genitive suffixes from the surviving candidate so geocoding
# receives a clean place name.
_BENGALI_POSTPOSITIONS = (
    "এর", "এ", "তে", "কে", "থেকে", "দিয়ে", "দিয়ে", "সহ", "বনাম", "জন্য", "প্রতি",
)
_HAS_BENGALI_RE = re.compile(r"[\u0980-\u09FF]")
_BENGALI_POSTPOSITION_SPLIT_RE = re.compile(
    rf"\s+(?:{'|'.join(_BENGALI_POSTPOSITIONS)})(?!{WORD_CHAR_PATTERN})"
)
# Banglish (Roman-script Bengali): "Mumbai er", "Kolkata e", "Delhi te"
_BANGLISH_POSTPOSITIONS = ("er", "e", "te", "ey", "theke", "jonno", "proti")
_BANGLISH_POSTPOSITION_SPLIT_RE = re.compile(
    r"\s+(?:" + "|".join(_BANGLISH_POSTPOSITIONS) + r")\b", re.IGNORECASE
)
# Locative/genitive suffixes often fused to the place name in Bengali script
# e.g. কলকাতায়, মুম্বাইতে, দিল্লীর. Strip only when the remaining stem is
# still long enough to be a real place name.
_BENGALI_SUFFIX_RE = re.compile(
    r"(?:য়|য়ে|তে|র|এর|এ)$"
)


def _strip_bengali_suffix(tok: str) -> str:
    """Remove common Bengali locative/genitive suffixes glued to a place name."""
    if not _HAS_BENGALI_RE.search(tok):
        return tok
    stripped = _BENGALI_SUFFIX_RE.sub("", tok)
    # Keep original if stripping would leave a too-short or empty stem.
    if len(stripped) >= 2:
        return stripped
    return tok


def _clean_segment_tokens(seg: str) -> str:
    """Tokenize a text segment and drop stopwords/day-words/single chars/bare numbers."""
    # Some Hinglish typing mashes words together with only a capital-letter
    # boundary ("TaapMatra" for "Taap Matra") — split those back apart so
    # each half can be checked against the stopword list individually.
    seg = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", seg)
    tokens = re.findall(r"[\w\u0900-\u097F\u0980-\u09FF\u0B80-\u0BFF\u0C00-\u0C7F]+", seg)
    rem = []
    for tok in tokens:
        if tok.lower() in STOPWORDS or tok.lower() in DAY_WORDS:
            continue
        if len(tok) <= 1 or tok.isdigit():
            continue
        # Strip fused Bengali suffixes (কলকাতায় → কলকাতা) before accepting.
        tok = _strip_bengali_suffix(tok)
        if tok.lower() in STOPWORDS or len(tok) <= 1:
            continue
        rem.append(tok)
    return " ".join(rem)


def _extract_location(raw_text: str, intent: str, matched_keywords: list[str]) -> str | None:
    # Phrases like "for my location", "near me" mean "use my GPS position", not a
    # place named "location"/"me". Strip them before any other parsing so they can
    # never be geocoded as a literal place name (previously "for my location" could
    # leak the word "location" into the geocoder and match an unrelated business).
    text = _DEVICE_LOCATION_RE.sub(" ", raw_text)
    # remove matched intent keywords first (longest first to avoid partial overlap issues)
    for kw in sorted(matched_keywords, key=len, reverse=True):
        text = _strip_keyword(kw, text)

    # strip day-offset words so "for Kolkata tomorrow" → Kolkata
    for phrase in sorted(DAY_WORDS.keys(), key=len, reverse=True):
        text = _strip_keyword(phrase, text)

    # Also strip explicit numeric/worded horizons so forms such as
    # "5-day forecast Chennai", "প্রথম ৭ দিনে", and "forecast for one day Jaipur"
    # leave only the actual place name for geocoding. Covers Hindi + Bengali
    # day-count words ("7 दिनों", "3 दिन", "৭ দিনে") and "প্রথম/first" prefixes.
    text_for_horizon = _normalize_indic_digits(text)
    horizon_number_words = r"(?:%s)" % "|".join(re.escape(w) for w in sorted(NUMBER_WORDS, key=len, reverse=True))
    day_unit = (
        r"(?:days?|din(?:on)?|divas(?:on)?|hafte?|hafton?|saptah|"
        r"दिन(?:ों)?|दिवस(?:ों)?|हफ़्त[ेों]?|हफ्त[ेों]?|सप्ताह(?:ों)?|"
        r"দিন(?:ে|ের)?|সপ্তাহ(?:ে|ের)?)"
    )
    text_for_horizon = re.sub(
        rf"(?:প্রথম|first|next|coming|আগামী|পরবর্তী|agle|agla|agli)?\s*"
        rf"(?<!\w){horizon_number_words}\s*(?:-\s*)?{day_unit}(?!\w)",
        " ",
        text_for_horizon,
        flags=re.IGNORECASE,
    )
    # Also strip bare "প্রথম"/"first" + day unit leftovers and standalone day words
    # that survived the numeric strip.
    text_for_horizon = re.sub(
        rf"(?:প্রথম|first|next|coming|আগামী|পরবর্তী)\s*{day_unit}",
        " ",
        text_for_horizon,
        flags=re.IGNORECASE,
    )
    text = text_for_horizon


    # common connector patterns: "weather in X", "for X", "near X", "around X"
    # \b boundaries matter here: without them "in" was matching inside "Mein"
    # (Hinglish for "में") — e.g. "...Mein Kolkata" was mis-parsed as
    # "...M" + "in Kolkata", accidentally "working" by luck rather than
    # design. Bounding the alternation prevents that false substring match.
    m = re.search(
        r"\b(?:in|at|for|near|around|over|of)\b\s+([A-Za-z\u0900-\u097F\u0980-\u09FF\u0B80-\u0BFF\u0C00-\u0C7F .,]+?)(?:\?|$)",
        text,
        re.IGNORECASE,
    )
    if m:
        candidate = m.group(1).strip(" ?.!,")
        segments = [s.strip() for s in candidate.split(",")]
        clean_segments = [_clean_segment_tokens(seg) for seg in segments]
        clean_segments = [s for s in clean_segments if s]
        if clean_segments:
            return ", ".join(clean_segments).strip()

    # Postpositional languages (Hindi etc.): the place name precedes the
    # connector word, e.g. "कोलकाता में" / "मुंबई का". A query can contain
    # more than one postposition (a leading time phrase plus the place), so
    # split on ALL of them and use the first segment that survives cleaning
    # rather than assuming the very first postposition marks the place.
    if _HAS_DEVANAGARI_RE.search(text):
        for seg in _HINDI_POSTPOSITION_SPLIT_RE.split(text):
            candidate = _clean_segment_tokens(seg)
            if candidate:
                return candidate

    # Same idea, transliterated ("Hinglish"): "Kolkata ka", "Mumbai mein".
    # Plain \b is safe here since this is ASCII, unlike the Devanagari case.
    # Gated on an actual match so ordinary English queries (with no "ka"/
    # "mein"/etc. token) fall through unchanged to the comma-aware fallback
    # below, e.g. "weather at rajarhat, kolkata" keeps its comma intact.
    if _HINGLISH_POSTPOSITION_SPLIT_RE.search(text):
        for seg in _HINGLISH_POSTPOSITION_SPLIT_RE.split(text):
            candidate = _clean_segment_tokens(seg)
            if candidate:
                return candidate

    # Bengali script postpositions: "মুম্বাই এর তাপমাত্রা", "কলকাতা তে".
    # Same multi-postposition strategy as Hindi — split on every match and
    # take the first segment that survives stopword cleaning.
    if _HAS_BENGALI_RE.search(text):
        for seg in _BENGALI_POSTPOSITION_SPLIT_RE.split(text):
            candidate = _clean_segment_tokens(seg)
            if candidate:
                return candidate

    # Banglish (Roman-script Bengali): "Mumbai er temperature", "Kolkata e weather".
    if _BANGLISH_POSTPOSITION_SPLIT_RE.search(text):
        for seg in _BANGLISH_POSTPOSITION_SPLIT_RE.split(text):
            candidate = _clean_segment_tokens(seg)
            if candidate:
                return candidate

    # strip stopwords token by token, preserving comma-separated parts if present
    segments = [s.strip() for s in text.split(",")]
    clean_segments = [_clean_segment_tokens(seg) for seg in segments]
    clean_segments = [s for s in clean_segments if s]
    if clean_segments:
        return ", ".join(clean_segments).strip()
    return None


_LOCATION_SPLIT_RE = re.compile(
    r"\s*(?:/|\bvs\.?\b|\band\b|\b&\b|\bas well as\b)\s*", re.IGNORECASE
)


def split_multi_location(text: str | None) -> list[str]:
    """Split a location phrase that names multiple distinct places.

    'Chennai and Kolkata' -> ['Chennai', 'Kolkata']
    'Mumbai / Pune'       -> ['Mumbai', 'Pune']
    'Rajarhat, Kolkata'   -> ['Rajarhat, Kolkata'] (preserved as single qualified place)
    None / ''             -> []
    """
    if not text or not text.strip():
        return []
    parts = [p.strip(" ?.!,") for p in _LOCATION_SPLIT_RE.split(text)]
    return [p for p in parts if p]


def mentions_device_location(text: str | None) -> bool:
    """True when the raw text explicitly asks for 'my location' / 'near me' / etc.

    Used by the composer to stop the LLM refine step from overwriting a
    correctly-empty location with a hallucinated place name: if the user
    asked for their own GPS position, no place name should ever win out
    over the device coordinates.
    """
    if not text:
        return False
    return bool(_DEVICE_LOCATION_RE.search(text))



_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

def _detect_historical_range(text: str) -> tuple[str | None, str | None]:
    """Detect a concrete past-weather date/range.

    Returns ISO start/end dates. Relative phrases are resolved against the
    backend's current date; explicit dates are preserved exactly. This is
    intentionally separate from forecast horizon parsing so "last 7 days"
    can never accidentally become a seven-day forecast.
    """
    raw = _normalize_query_text(text.strip().lower())
    today = date.today()

    # Exact ISO date: 2026-08-25 / 2026.08.25 / 2026/08/25
    m = re.search(r"(?<!\d)(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)", raw)
    if m:
        try:
            d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if d < today:
                return d.isoformat(), d.isoformat()
        except ValueError:
            pass

    # Numeric day/month/year: 25/08/2026 or 25-08-2026.
    m = re.search(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](20\d{2})(?!\d)", raw)
    if m:
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if d < today:
                return d.isoformat(), d.isoformat()
        except ValueError:
            pass

    # Month name + day [+ year], including "August 25 2026".
    month_pattern = "|".join(sorted(_MONTHS, key=len, reverse=True))
    m = re.search(
        rf"\b({month_pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,\s*|\s+)(20\d{{2}})\b",
        raw, re.IGNORECASE
    )
    if m:
        try:
            d = date(int(m.group(3)), _MONTHS[m.group(1)], int(m.group(2)))
            if d < today:
                return d.isoformat(), d.isoformat()
        except ValueError:
            pass

    # "25 August 2026" / "25 Aug 2026".
    m = re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pattern})(?:,\s*|\s+)(20\d{{2}})\b",
        raw, re.IGNORECASE
    )
    if m:
        try:
            d = date(int(m.group(3)), _MONTHS[m.group(2)], int(m.group(1)))
            if d < today:
                return d.isoformat(), d.isoformat()
        except ValueError:
            pass

    # Month + day without year. Use the most recent occurrence.
    m = re.search(rf"\b({month_pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b", raw, re.IGNORECASE)
    if m:
        try:
            d = date(today.year, _MONTHS[m.group(1)], int(m.group(2)))
            if d >= today:
                d = date(today.year - 1, d.month, d.day)
            return d.isoformat(), d.isoformat()
        except ValueError:
            pass

    # Relative ranges. "last/past N days" means the N completed calendar
    # days immediately before today.
    word_pattern = "|".join(re.escape(w) for w in sorted(NUMBER_WORDS, key=len, reverse=True))
    num_token = rf"(?:\d{{1,2}}|{word_pattern})"
    m = re.search(
        rf"\b(?:last|past|previous|pichle|pichla|pichhle|গত|গত\s+গত|पिछले)\s+({num_token})\s*"
        r"(?:days?|day|din(?:s|on)?|dino|দিন(?:ে|গুলিতে|গুলি)?|दिन(?:ों|ो)?|divas(?:on)?|hafton?|হপ্তা)\b",
        raw, re.IGNORECASE
    )
    if m:
        token = m.group(1)
        count = int(token) if token.isdigit() else NUMBER_WORDS.get(token)
        if count:
            count = max(1, min(count, 31))
            start = today - timedelta(days=count)
            end = today - timedelta(days=1)
            return start.isoformat(), end.isoformat()

    # "last week" = previous completed calendar week (Monday-Sunday).
    if re.search(r"\b(?:last|previous)\s+week\b|পिछला\s+सप्ताह|पिछले\s+हफ्ते|গত\s+সপ্তাহ", raw, re.IGNORECASE):
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start.isoformat(), end.isoformat()

    # Single-day relative phrases.
    if re.search(r"\b(?:day\s+before\s+yesterday|the\s+day\s+before\s+yesterday|"
                 r"day\s+before|parso|parson)\b|परसों|গত\s+পরশু", raw, re.IGNORECASE):
        d = today - timedelta(days=2)
        return d.isoformat(), d.isoformat()

    if re.search(r"\b(?:yesterday|yesterdays|kal\s+ka|kal\s+ke|pichle\s+din)\b|"
                 r"গতকাল|গতকালের|कल\s+का|कल\s+के|पिछले\s+दिन", raw, re.IGNORECASE):
        d = today - timedelta(days=1)
        return d.isoformat(), d.isoformat()

    # A broad "past weather" request defaults to the previous 7 completed days.
    if re.search(
        r"\b(?:past|previous|historical)\s+(?:weather|weather\s+report|conditions?|report)\b|"
        r"\bweather\s+(?:history|in\s+the\s+past)\b|"
        r"\b(?:past|previous)\s+days?\b|"
        r"পূর্বের\s+আবহাওয়া|আগের\s+দিনের\s+আবহাওয়া|"
        r"पिछला\s+मौसम|पिछले\s+दिनों\s+का\s+मौसम",
        raw, re.IGNORECASE
    ):
        start = today - timedelta(days=7)
        end = today - timedelta(days=1)
        return start.isoformat(), end.isoformat()

    return None, None


def parse_query(text: str) -> ParsedQuery:
    text = text.strip()
    text_lower = text.lower()
    intent, matched = _detect_intent(text_lower)
    historical_start, historical_end = _detect_historical_range(text)

    # A concrete past date/range is authoritative: it must never be routed to
    # the forecast endpoint even if the query also contains "weather" or
    # "report". Keep climate/history requests such as "past years" untouched.
    if historical_start and historical_end:
        intent = "historical"
        day_offset, horizon = 0, 1
    else:
        day_offset, horizon = _detect_day_offset(text_lower)

    location = _extract_location(text, intent, matched)

    if intent in ("greeting", "help"):
        if location:
            intent = "forecast" if (day_offset > 0 or horizon < 7) else "current"
        else:
            location = None

    # Explicit multi-day phrasing ("প্রথম ৭ দিনে", "5 day forecast", "next 3 days")
    # should surface as forecast even when no forecast keyword was present.
    text_norm = _normalize_query_text(text_lower)
    word_pattern = "|".join(re.escape(w) for w in sorted(NUMBER_WORDS, key=len, reverse=True) if NUMBER_WORDS[w] >= 1)
    explicit_multi_day = bool(re.search(
        rf"(?:প্রথম|first|next|coming|আগামী|পরবর্তী|agle|agla)?\s*"
        rf"(?:[2-9]|1[0-6]|{word_pattern})\s*"
        r"(?:days?|din|দিন|দিয়ে|দিনে|दिन|दिवस|दिनों|hafte|सप्ताह|সপ্তাহ|সপ্তাহে)",
        text_norm,
        re.IGNORECASE,
    )) or bool(re.search(r"\b(?:week|সপ্তাহ|सप्ताह)\b", text_norm, re.IGNORECASE))
    if explicit_multi_day and intent in ("current", "greeting"):
        intent = "forecast"

    return ParsedQuery(
        intent=intent,
        location_text=location,
        day_offset=day_offset,
        horizon_days=horizon,
        historical_start_date=historical_start,
        historical_end_date=historical_end,
        raw_text=text,
        matched_keywords=matched,
    )
