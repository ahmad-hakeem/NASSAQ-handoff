"""
NASSAQ Hakim LLM Service
========================
Centralized, field-aware LLM orchestration for the "حكيم" assistant.

Responsibilities:
- Single OpenAI client (singleton, reused)
- Field-aware prompt template registry (mode x field)
- Output validation (empty / too short / wrong language / quote artifacts)
- One automatic retry on validation failure
- Structured logging + per-call generation metadata

Public API:
    await hakim_generate(mode, field, *, text, context, language="ar")

Returns dict:
    {
        "success": bool,
        "text": str,                # validated final text (or original on improve fallback)
        "mode": "generate" | "improve",
        "field": str,
        "model": str,
        "language": "ar" | "en",
        "generation_id": str,
        "elapsed_ms": int,
        "reason": str | None,       # set when success is False
        "retried": bool,
    }
"""

from __future__ import annotations

import os
import time
import uuid
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("nassaq.hakim")

# ---------------------------------------------------------------------------
# Client (singleton)
# ---------------------------------------------------------------------------

_client = None
_client_failed = False

DEFAULT_MODEL = "gpt-4o-mini"


def _get_client():
    """Lazy-initialised OpenAI client. Returns None if no API key configured."""
    global _client, _client_failed
    if _client is not None:
        return _client
    if _client_failed:
        return None
    api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
    base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        _client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)
        return _client
    except Exception as e:
        logger.error(f"[Hakim] failed to init OpenAI client: {e}")
        _client_failed = True
        return None


def is_available() -> bool:
    return _get_client() is not None


# ---------------------------------------------------------------------------
# Field registry
# ---------------------------------------------------------------------------
# Each entry defines per-field behaviour so prompts and validation are
# specialised rather than relying on one generic template.

_AR_RANGE = (
    ('\u0600', '\u06FF'),
    ('\u0750', '\u077F'),
    ('\uFB50', '\uFDFF'),
    ('\uFE70', '\uFEFF'),
)


def _is_arabic_char(ch: str) -> bool:
    for lo, hi in _AR_RANGE:
        if lo <= ch <= hi:
            return True
    return False


def _arabic_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    arabic = sum(1 for c in letters if _is_arabic_char(c))
    return arabic / len(letters)


SYSTEM_AR_BASE = (
    "أنت 'حكيم'، المساعد الذكي في منصة نسّاق التعليمية. "
    "تكتب بالعربية الفصحى الواضحة، بأسلوب مهني تربوي، بدون مبالغة، "
    "وبدون أي مقدمات أو شروحات حول النص."
)

SYSTEM_EN_BASE = (
    "You are 'Hakim', the AI assistant inside the NASSAQ education platform. "
    "Write in clear professional English without preambles or meta commentary."
)


def _system_prompt(language: str) -> str:
    return SYSTEM_EN_BASE if language == "en" else SYSTEM_AR_BASE


FIELD_REGISTRY: Dict[str, Dict[str, Any]] = {
    # --- Portfolio evidence ----------------------------------------------
    "evidence_title": {
        "max_tokens": 80,
        "temp_generate": 0.7,
        "temp_improve": 0.55,
        "min_chars": 6,
        "max_chars": 120,
        "ar_only": True,
        "rule_ar": (
            "عنوان موجز ودقيق لشاهد ملف إنجاز معلم، بحد أقصى جملة واحدة قصيرة (٤-١٢ كلمة)، "
            "بدون علامات اقتباس وبدون نقطة في النهاية."
        ),
        "rule_en": (
            "A concise descriptive title for a teacher portfolio evidence item, "
            "one short sentence (4-12 words), no quotes, no trailing period."
        ),
    },
    "evidence_description": {
        "max_tokens": 400,
        "temp_generate": 0.75,
        "temp_improve": 0.6,
        "min_chars": 40,
        "max_chars": 1200,
        "ar_only": True,
        "rule_ar": (
            "وصف مهني واضح لشاهد في ملف إنجاز معلم، من ٢ إلى ٤ جمل، يبيّن الهدف والمحتوى والأثر التعليمي، "
            "بأسلوب رسمي مهني خالٍ من المبالغة."
        ),
        "rule_en": (
            "A clear professional description of a teacher portfolio evidence item, "
            "2-4 sentences covering purpose, content and educational impact."
        ),
    },
    # --- Portfolio profile fields ----------------------------------------
    "portfolio_intro": {
        "max_tokens": 350,
        "temp_generate": 0.75,
        "temp_improve": 0.6,
        "min_chars": 60,
        "max_chars": 900,
        "ar_only": True,
        "rule_ar": (
            "نبذة تعريفية للمعلم في ملف إنجازه الوظيفي، من ٣ إلى ٥ جمل، تبرز التخصص والخبرة "
            "والرؤية التربوية، بأسلوب مهني محترم خالٍ من المبالغة."
        ),
        "rule_en": (
            "A teacher's professional self-introduction (3-5 sentences) covering specialty, "
            "experience and educational vision, in a professional tone."
        ),
    },
    "portfolio_vision": {
        "max_tokens": 160,
        "temp_generate": 0.7,
        "temp_improve": 0.55,
        "min_chars": 20,
        "max_chars": 400,
        "ar_only": True,
        "rule_ar": "رؤية تربوية موجزة وملهمة في جملة أو جملتين دون شعارات فضفاضة.",
        "rule_en": "A short inspiring educational vision (1-2 sentences) without empty slogans.",
    },
    "portfolio_mission": {
        "max_tokens": 200,
        "temp_generate": 0.7,
        "temp_improve": 0.55,
        "min_chars": 25,
        "max_chars": 500,
        "ar_only": True,
        "rule_ar": "رسالة عمل قابلة للتنفيذ في ٢-٣ جمل تبيّن ما يلتزم المعلم بفعله مع طلابه.",
        "rule_en": "An actionable mission (2-3 sentences) describing what the teacher commits to deliver.",
    },
    "portfolio_values": {
        "max_tokens": 220,
        "temp_generate": 0.7,
        "temp_improve": 0.55,
        "min_chars": 25,
        "max_chars": 500,
        "ar_only": True,
        "rule_ar": (
            "قيم تربوية واضحة في صورة قائمة قصيرة من ٣ إلى ٥ قيم، كل قيمة كلمة أو عبارة موجزة، "
            "افصل بينها بفواصل عربية أو بأسطر."
        ),
        "rule_en": "3-5 short educational values, separated by commas or newlines.",
    },
}


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _format_context(context: Optional[Dict[str, Any]], language: str) -> str:
    if not context:
        return "—"
    label_map_ar = {
        "evidence_type": "نوع الشاهد",
        "subject": "المادة",
        "grade": "الصف",
        "class": "الفصل",
        "title": "عنوان الشاهد",
        "teacher_name": "اسم المعلم",
        "specialty": "التخصص",
        "experience_years": "سنوات الخبرة",
        "school_name": "المدرسة",
        "section": "القسم",
    }
    label_map_en = {
        "evidence_type": "Evidence type",
        "subject": "Subject",
        "grade": "Grade",
        "class": "Class",
        "title": "Title",
        "teacher_name": "Teacher",
        "specialty": "Specialty",
        "experience_years": "Years of experience",
        "school_name": "School",
        "section": "Section",
    }
    labels = label_map_en if language == "en" else label_map_ar
    lines = []
    for k, v in context.items():
        if v in (None, "", []):
            continue
        label = labels.get(k, k.replace("_", " "))
        if isinstance(v, (list, tuple)):
            v = "، ".join(str(x) for x in v if x)
        lines.append(f"{label}: {v}")
    return "\n".join(lines) if lines else "—"


def _build_prompts(
    *, mode: str, field: str, text: str, context: Optional[Dict[str, Any]],
    language: str, sharpen: bool = False,
) -> tuple[str, str]:
    cfg = FIELD_REGISTRY[field]
    rule = cfg.get("rule_en" if language == "en" else "rule_ar", "")
    context_block = _format_context(context, language)
    system = _system_prompt(language)

    if mode == "generate":
        if language == "en":
            user = (
                f"Context:\n{context_block}\n\n"
                f"Required: {rule}\n\n"
                "Return ONLY the final text, with no preface or commentary."
            )
        else:
            user = (
                f"السياق:\n{context_block}\n\n"
                f"المطلوب: {rule}\n\n"
                "أعد النص النهائي فقط دون أي مقدمات أو شروحات."
            )
    else:  # improve
        if language == "en":
            user = (
                f"Context:\n{context_block}\n\n"
                f"Original text:\n{text}\n\n"
                f"Required: {rule}\n"
                "Preserve the original meaning. Improve clarity, structure and tone. "
                "Do not invent new facts. Return ONLY the improved text."
            )
        else:
            user = (
                f"السياق:\n{context_block}\n\n"
                f"النص الأصلي:\n{text}\n\n"
                f"المطلوب: {rule}\n"
                "حافظ على المعنى الأصلي. حسّن الوضوح والبناء والأسلوب فقط. "
                "لا تخترع معلومات جديدة. أعد النص المُحسَّن فقط دون مقدمات."
            )

    if sharpen:
        if language == "en":
            user += (
                "\n\nIMPORTANT: previous attempt was rejected. Be more concrete and specific, "
                "do not repeat phrases, respect the required length."
            )
        else:
            user += (
                "\n\nملاحظة: المحاولة السابقة لم تُقبل. كن أكثر تحديداً ودقة، "
                "لا تكرر العبارات، والتزم بالطول المطلوب."
            )
    return system, user


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

def _strip_artifacts(text: str) -> str:
    if not text:
        return ""
    out = text.strip()
    # Strip wrapping quotes
    while out and out[0] in ('"', "'", "«", "“", "”", "‘", "’") and out[-1] in ('"', "'", "»", "“", "”", "‘", "’"):
        out = out[1:-1].strip()
    # Common LLM preface artifacts
    for junk in ("النص النهائي:", "Final text:", "النص:", "Output:"):
        if out.startswith(junk):
            out = out[len(junk):].strip()
    return out


def _validate(text: str, field: str, language: str, original: str = "") -> Optional[str]:
    """Return None if valid, else a reason code."""
    cfg = FIELD_REGISTRY.get(field, {})
    if not text:
        return "EMPTY"
    n = len(text)
    if n < cfg.get("min_chars", 1):
        return "TOO_SHORT"
    if n > cfg.get("max_chars", 5000):
        return "TOO_LONG"
    if cfg.get("ar_only") and language == "ar":
        if _arabic_ratio(text) < 0.55:
            return "WRONG_LANGUAGE"
    # On improve, output identical to original is a failure
    if original and text.strip() == original.strip():
        return "UNCHANGED"
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def hakim_generate(
    mode: str,
    field: str,
    *,
    text: str = "",
    context: Optional[Dict[str, Any]] = None,
    language: str = "ar",
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """Generate or improve a field via the Hakim LLM service."""
    gen_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()

    mode = (mode or "").strip().lower()
    field = (field or "").strip().lower()
    language = (language or "ar").strip().lower()
    if language not in ("ar", "en"):
        language = "ar"

    if mode not in ("generate", "improve"):
        return _result(False, text or "", mode, field, model, language, gen_id, started, reason="INVALID_MODE")
    if field not in FIELD_REGISTRY:
        return _result(False, text or "", mode, field, model, language, gen_id, started, reason="INVALID_FIELD")

    text_in = (text or "").strip()
    if mode == "improve" and len(text_in) < 5:
        return _result(False, text_in, mode, field, model, language, gen_id, started, reason="TEXT_TOO_SHORT")

    client = _get_client()
    if client is None:
        return _result(False, text_in, mode, field, model, language, gen_id, started, reason="AI_DISABLED")

    cfg = FIELD_REGISTRY[field]
    temperature = cfg["temp_improve"] if mode == "improve" else cfg["temp_generate"]
    max_tokens = cfg["max_tokens"]

    retried = False
    last_reason: Optional[str] = None
    out_text = ""

    for attempt in (0, 1):
        sharpen = attempt == 1
        system, user = _build_prompts(
            mode=mode, field=field, text=text_in, context=context,
            language=language, sharpen=sharpen,
        )
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=max(0.2, temperature - (0.15 if sharpen else 0.0)),
            )
            raw = (response.choices[0].message.content or "")
        except Exception as e:
            logger.warning(
                f"[Hakim:{gen_id}] LLM call failed mode={mode} field={field} attempt={attempt}: {e}"
            )
            return _result(False, text_in, mode, field, model, language, gen_id, started,
                           reason="LLM_ERROR", retried=retried)

        out_text = _strip_artifacts(raw)
        last_reason = _validate(out_text, field, language, original=text_in if mode == "improve" else "")
        if last_reason is None:
            return _result(True, out_text, mode, field, model, language, gen_id, started, retried=retried)

        # Validation failed — try once more with sharpened prompt.
        retried = True
        logger.info(
            f"[Hakim:{gen_id}] validation={last_reason} mode={mode} field={field} attempt={attempt} "
            f"len={len(out_text)} — retrying"
        )

    # Both attempts failed validation — return best-effort with reason.
    logger.warning(
        f"[Hakim:{gen_id}] gave up after retry mode={mode} field={field} reason={last_reason}"
    )
    return _result(False, text_in or out_text, mode, field, model, language, gen_id, started,
                   reason=last_reason or "VALIDATION_FAILED", retried=True)


def _result(success, text, mode, field, model, language, gen_id, started,
            reason: Optional[str] = None, retried: bool = False) -> Dict[str, Any]:
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    payload = {
        "success": success,
        "text": text,
        "mode": mode,
        "field": field,
        "model": model,
        "language": language,
        "generation_id": gen_id,
        "elapsed_ms": elapsed_ms,
        "retried": retried,
    }
    if reason:
        payload["reason"] = reason
    if success:
        logger.info(
            f"[Hakim:{gen_id}] OK mode={mode} field={field} ms={elapsed_ms} retried={retried} len={len(text or '')}"
        )
    return payload


def supported_fields() -> Dict[str, Dict[str, Any]]:
    """Public read-only view of the registry, for diagnostics or tests."""
    return {
        f: {
            "max_chars": cfg.get("max_chars"),
            "min_chars": cfg.get("min_chars"),
            "ar_only": cfg.get("ar_only", False),
        }
        for f, cfg in FIELD_REGISTRY.items()
    }
