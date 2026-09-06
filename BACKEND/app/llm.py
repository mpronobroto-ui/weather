"""
Optional LLM-in-the-loop layer.

The platform works fully offline-of-LLM using nlu.py's rule engine (so the
demo never breaks for want of an API key). If any of the environment
variables below are set, this module additionally asks a real LLM to
(a) double-check/refine intent+location extraction and (b) rephrase the
final answer more conversationally / in a requested regional language it
wasn't explicitly templated for. This mirrors how a production WeatherGPT
would plug into OpenAI / Llama / Gemini per the suggested tech stack.

Supported (set ONE of these):
  OPENAI_API_KEY        -> uses OpenAI-compatible /v1/chat/completions
  GEMINI_API_KEY         -> uses Gemini generateContent REST endpoint
  OLLAMA_URL              -> e.g. http://localhost:11434 for a local Llama model
"""
from __future__ import annotations

import json
import logging
import os
import httpx

logger = logging.getLogger("llm")

def _env(name: str, default: str | None = None) -> str | None:
    """Read env var and strip accidental whitespace/newlines (common when pasting keys into .env)."""
    val = os.getenv(name, default)
    if val is None:
        return None
    cleaned = val.strip()
    return cleaned or None


OPENAI_API_KEY = _env("OPENAI_API_KEY")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini"
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash"
OLLAMA_URL = _env("OLLAMA_URL")
OLLAMA_MODEL = _env("OLLAMA_MODEL", "llama3") or "llama3"


def llm_available() -> bool:
    return bool(OPENAI_API_KEY or GEMINI_API_KEY or OLLAMA_URL)


async def _call_openai(prompt: str) -> str | None:
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {"model": OPENAI_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
    async with httpx.AsyncClient(timeout=6.0) as client:
        try:
            r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("OpenAI call failed: %s", exc)
            return None


async def _call_gemini(prompt: str) -> str | None:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.post(url, json=body)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except httpx.HTTPStatusError as exc:
            # Surface WHY it failed (bad key, revoked key, wrong model name,
            # quota) instead of silently falling back — this is the single
            # most common cause of "I added the key but nothing changed".
            logger.warning("Gemini call failed: HTTP %s — %s", exc.response.status_code, exc.response.text[:300])
            return None
        except Exception as exc:
            logger.warning("Gemini call failed: %s", exc)
            return None


async def _call_ollama(prompt: str) -> str | None:
    if not OLLAMA_URL:
        return None
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            r = await client.post(
                f"{OLLAMA_URL.rstrip('/')}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            r.raise_for_status()
            return r.json().get("response")
        except Exception:
            return None



async def ask_llm(prompt: str) -> str | None:
    if OPENAI_API_KEY:
        return await _call_openai(prompt)
    if GEMINI_API_KEY:
        return await _call_gemini(prompt)
    if OLLAMA_URL:
        return await _call_ollama(prompt)
    return None


async def refine_query_understanding(raw_text: str, fallback: dict) -> dict:
    """Ask the LLM to extract {intent, location, day_offset, horizon_days}.
    Falls back to the rule-engine result on any failure or if no LLM is configured.
    """
    if not llm_available():
        return fallback

    prompt = (
        "Extract weather-query intent from the user's message, which may be in English or any "
        "Indian language (Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Punjabi, Kannada, "
        "Malayalam, Odia, Urdu) and may contain spelling mistakes or transliteration. "
        "Return STRICT JSON only, no prose, no markdown fences, with keys: "
        'intent (one of: current, forecast, umbrella, aqi, alert, climate, agriculture, aviation, marine, urban, energy, retail, construction, greeting, help), '
        "location (the place name mentioned, in English/romanized form, or null if none is mentioned). "
        "IMPORTANT: phrases like 'my location', 'near me', 'around me', 'here', 'this area' are NOT place "
        "names — they mean the user wants their own GPS position used, so location MUST be null for those, "
        "even if you think you recognize a place. Never invent or guess a place name that isn't in the text. "
        "day_offset (integer, 0=today, 1=tomorrow, etc.), horizon_days (integer 1-16, how many days of "
        "outlook are being asked for; default 7 if unclear).\n\n"
        f"User message: {raw_text!r}"
    )
    raw = await ask_llm(prompt)
    if not raw:
        return fallback
    try:
        cleaned = raw.strip().strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        parsed = json.loads(cleaned)
        merged = dict(fallback)
        merged.update({k: v for k, v in parsed.items() if v not in (None, "")})
        return merged
    except Exception:
        return fallback


async def phrase_reply(context_summary: str, lang_name: str, fallback_text: str, user_question: str | None = None) -> str:
    """Ask the LLM to turn a factual summary into a natural, directly-relevant
    answer in the target language. Falls back to the template-generated text
    if no LLM is configured or the call fails.
    """
    if not llm_available():
        return fallback_text

    question_line = f'The user actually asked: "{user_question}"\n' if user_question else ""
    prompt = (
        f"You are WeatherGPT — respond like Google Gemini: clear, friendly, structured, and accurate. {question_line}"
        f"IMPORTANT: The selected reply language is {lang_name}. Ignore the language/script used in the user's question. "
        f"Write the ENTIRE reply in {lang_name} only. Do not switch languages because the user typed in another language. "
        f"Using ONLY the verified weather data below, write a natural answer in {lang_name} "
        "(short paragraphs or bullets OK, max ~120 words). "
        "Keep every number, %, date, and place EXACTLY as given — never invent temperatures, storm names, or wind speeds. "
        "Add at most one practical tip that follows directly from the data "
        "(umbrella, heat safety, travel caution).\n\n"
        "Verified data:\n" + context_summary
    )
    result = await ask_llm(prompt)
    result = result.strip() if result else ""
    if not result:
        return fallback_text

    # Never let an LLM override the language selected in the UI. The user's
    # question may be Bengali/Hindi/etc. even when the reply-language selector
    # is English (or vice versa). Reject clearly off-language generations and
    # use the deterministic translated template instead.
    if not _matches_requested_language(result, lang_name):
        return fallback_text
    return result


def _matches_requested_language(text: str, lang_name: str) -> bool:
    """Conservative script check for LLM replies. Mixed-script place names and
    numbers are allowed; a response dominated by a different script is not."""
    if not text:
        return False
    import unicodedata
    counts = {}
    for ch in text:
        if not ch.isalpha():
            continue
        try:
            name = unicodedata.name(ch)
        except ValueError:
            continue
        script = (
            "latin" if "LATIN" in name else
            "devanagari" if "DEVANAGARI" in name else
            "bengali" if "BENGALI" in name else
            "tamil" if "TAMIL" in name else
            "telugu" if "TELUGU" in name else
            "gujarati" if "GUJARATI" in name else
            "gurmukhi" if "GURMUKHI" in name else
            "kannada" if "KANNADA" in name else
            "malayalam" if "MALAYALAM" in name else
            "oriya" if "ORIYA" in name else
            "arabic" if "ARABIC" in name else
            "other"
        )
        counts[script] = counts.get(script, 0) + 1
    if not counts:
        return True
    dominant = max(counts, key=counts.get)
    target = {
        "English": "latin", "Hinglish (Hindi + English)": "latin",
        "हिन्दी": "devanagari", "বাংলা": "bengali", "தமிழ்": "tamil",
        "తెలుగు": "telugu", "मराठी": "devanagari", "ગુજરાતી": "gujarati",
        "ਪੰਜਾਬੀ": "gurmukhi", "ಕನ್ನಡ": "kannada", "മലയാളം": "malayalam",
        "ଓଡ଼ିଆ": "oriya", "اردو": "arabic",
    }.get(lang_name, "latin")
    return dominant == target


async def general_weather_answer(user_question: str, lang_name: str) -> str | None:
    """For questions that don't need a specific location (e.g. 'why does it
    rain more during monsoon', 'what is a heat wave') — answer directly from
    the model's general meteorology knowledge. Returns None if no LLM is
    configured, so the caller can fall back to asking for a location.

    If a Google Custom Search key (GOOGLE_API_KEY + GOOGLE_CSE_ID) is
    configured, a few live snippets are folded in as grounding context so
    the answer can reference current information instead of only the
    model's training data — this never blocks the answer if search is
    unavailable, it's a pure quality boost.
    """
    if not llm_available():
        return None

    grounding = ""
    try:
        from . import google_search
        if google_search.search_available():
            grounding = await google_search.grounding_snippets(user_question)
    except Exception:
        grounding = ""

    grounding_block = (
        f"\n\nHere is some current, real web search context you may use if relevant "
        f"(cite the source name inline where you use it, don't fabricate URLs):\n{grounding}\n"
        if grounding else ""
    )

    prompt = (
        "You are WeatherGPT with a Gemini-like conversational style: warm, precise, and helpful. "
        f"Answer in {lang_name} in 3–8 clear sentences. Explain weather/climate concepts simply. "
        "If a specific place is required and missing, ask for the city/region in the same language. "
        "Do not invent live storm names or current temperatures — say when the user should check a live forecast."
        f"{grounding_block}\n"
        f"Question: {user_question}"
    )
    result = await ask_llm(prompt)
    return result.strip() if result else None
