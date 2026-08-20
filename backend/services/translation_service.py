import os
import json
import logging
from typing import Optional

from services.ai_client import (
    PURPOSE_INTERACTIVE,
    AIProviderError,
    ai_chat_completion,
    build_openai_client,
)

logger = logging.getLogger(__name__)

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")

_client = None

def _get_client():
    global _client
    if _client is None and AI_INTEGRATIONS_OPENAI_API_KEY and AI_INTEGRATIONS_OPENAI_BASE_URL:
        _client = build_openai_client(
            PURPOSE_INTERACTIVE,
            api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
            base_url=AI_INTEGRATIONS_OPENAI_BASE_URL,
        )
    return _client


def is_available():
    return bool(AI_INTEGRATIONS_OPENAI_API_KEY and AI_INTEGRATIONS_OPENAI_BASE_URL)


def detect_language(text: str) -> str:
    if not text or not text.strip():
        return "unknown"
    for ch in text:
        if '\u0600' <= ch <= '\u06FF' or '\u0750' <= ch <= '\u077F' or '\uFB50' <= ch <= '\uFDFF' or '\uFE70' <= ch <= '\uFEFF':
            return "ar"
    return "en"


async def translate_text(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    if not text or not text.strip():
        return None
    client = _get_client()
    if not client:
        logger.warning("Translation service unavailable: OpenAI not configured")
        return None
    try:
        lang_names = {"ar": "Arabic", "en": "English"}
        src = lang_names.get(source_lang, source_lang)
        tgt = lang_names.get(target_lang, target_lang)
        model_name = os.environ.get("AI_MODEL") or os.environ.get("OPENAI_MODEL") or "gemini-3.5-flash"
        response = await ai_chat_completion(
            client,
            purpose=PURPOSE_INTERACTIVE,
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": f"You are a professional translator for a school management platform called NASSAQ (نَسَّق). Translate the following text from {src} to {tgt}. Return ONLY the translation, nothing else. Preserve any proper nouns, numbers, and formatting."
                },
                {"role": "user", "content": text}
            ],
            max_completion_tokens=2000,
            reasoning_effort="minimal",
        )
        translated = response.choices[0].message.content.strip()
        return translated
    except AIProviderError as e:
        # Timeout / provider outage — degrade to the untranslated text.
        logger.warning(f"Translation unavailable ({e.code}): {e}")
        return None
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return None


async def translate_fields(data: dict, fields: list[str]) -> dict:
    result = dict(data)
    for field in fields:
        ar_key = f"{field}_ar"
        en_key = f"{field}_en"
        base_val = data.get(field) or data.get(ar_key) or data.get(en_key)
        ar_val = data.get(ar_key)
        en_val = data.get(en_key)

        if base_val and not ar_val and not en_val:
            lang = detect_language(base_val)
            if lang == "ar":
                result[ar_key] = base_val
                translated = await translate_text(base_val, "ar", "en")
                if translated:
                    result[en_key] = translated
            else:
                result[en_key] = base_val
                translated = await translate_text(base_val, "en", "ar")
                if translated:
                    result[ar_key] = translated
        elif ar_val and not en_val:
            translated = await translate_text(ar_val, "ar", "en")
            if translated:
                result[en_key] = translated
        elif en_val and not ar_val:
            translated = await translate_text(en_val, "en", "ar")
            if translated:
                result[ar_key] = translated

    return result


async def translate_batch(items: list[dict], fields: list[str]) -> list[dict]:
    results = []
    for item in items:
        translated = await translate_fields(item, fields)
        results.append(translated)
    return results
