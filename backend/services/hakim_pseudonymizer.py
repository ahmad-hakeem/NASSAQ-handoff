"""
NASSAQ Hakim Pseudonymization Layer (Phase 3 — children's-data protection)
==========================================================================

Substitutes student / teacher / parent personal names with stable, opaque
tokens *before* an LLM prompt is constructed, and rehydrates the tokens back
to the real names in the LLM's response.

The pseudonymizer is intentionally local (no DB, no I/O): the mapping lives
for the lifetime of a single `hakim_generate` call. The provider never sees
real names; rehydration happens server-side after the response is validated.

Public API:
    p = Pseudonymizer()
    sanitized_text = p.sanitize(text, names=[...])
    sanitized_ctx  = p.sanitize_context(context_dict)
    real_response  = p.rehydrate(llm_response_text)
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional


# Context keys that may carry a personal name. Any string value at these keys
# will be tokenised. Add to this set when new context shapes are introduced.
_NAME_KEYS = {
    "student_name", "student_full_name", "student",
    "teacher_name", "teacher_full_name", "teacher",
    "parent_name", "parent_full_name", "parent", "guardian_name",
    "child_name", "name", "full_name", "actor_name",
}

# Context keys that MUST NEVER reach the LLM, even pseudonymised.
# These identify a real person well enough to deanonymise the token outside
# our system, so we drop them entirely.
_FORBIDDEN_KEYS = {
    "national_id", "iqama_id", "phone", "email", "address",
    "birthdate", "date_of_birth", "passport", "ssn",
}


class Pseudonymizer:
    def __init__(self) -> None:
        # real_name -> token
        self._fwd: Dict[str, str] = {}
        # token -> real_name (for rehydration)
        self._rev: Dict[str, str] = {}
        self._student_idx = 0
        self._teacher_idx = 0
        self._parent_idx = 0
        self._person_idx = 0

    # ------------------------------------------------------------------ tokens
    def _next_token(self, kind: str) -> str:
        kind = kind.lower()
        if kind.startswith("student"):
            self._student_idx += 1
            return f"[STUDENT_{self._student_idx}]"
        if kind.startswith("teacher"):
            self._teacher_idx += 1
            return f"[TEACHER_{self._teacher_idx}]"
        if kind.startswith(("parent", "guardian")):
            self._parent_idx += 1
            return f"[PARENT_{self._parent_idx}]"
        self._person_idx += 1
        return f"[PERSON_{self._person_idx}]"

    def _token_for(self, name: str, kind: str) -> str:
        name = (name or "").strip()
        if not name:
            return ""
        existing = self._fwd.get(name)
        if existing:
            return existing
        token = self._next_token(kind)
        self._fwd[name] = token
        self._rev[token] = name
        return token

    # ---------------------------------------------------------------- sanitize
    def register(self, name: str, kind: str = "person") -> str:
        """Register a name and return its stable token."""
        return self._token_for(name, kind)

    def sanitize(self, text: str, *, names: Optional[Iterable[str]] = None) -> str:
        """Substitute every occurrence of a registered/known name in `text`
        with its token. If `names` is provided, those are registered first."""
        if not text:
            return text or ""
        if names:
            for n in names:
                self._token_for(n, "person")
        if not self._fwd:
            return text
        # Replace longest names first to avoid partial collisions
        # (e.g. "محمد علي" before "محمد"). Use a word-boundary-aware regex
        # so a short name like "Ali" does not corrupt "Alignment".
        for real, token in sorted(self._fwd.items(), key=lambda kv: -len(kv[0])):
            if not real:
                continue
            pattern = re.compile(
                r"(?<![\w\u0600-\u06FF])"
                + re.escape(real)
                + r"(?![\w\u0600-\u06FF])"
            )
            text = pattern.sub(token, text)
        return text

    def sanitize_context(self, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Walk a context dict, tokenising any string value whose key matches
        a known personal-name key, and dropping forbidden direct identifiers."""
        if not context:
            return {}
        out: Dict[str, Any] = {}
        for k, v in context.items():
            kl = k.lower() if isinstance(k, str) else ""
            if kl in _FORBIDDEN_KEYS:
                # Drop direct identifiers entirely — we never want them in the
                # outbound prompt, even pseudonymised.
                continue
            if isinstance(v, str) and kl in _NAME_KEYS and v.strip():
                kind = "student" if "student" in kl or "child" in kl else (
                    "teacher" if "teacher" in kl else (
                        "parent" if "parent" in kl or "guardian" in kl else "person"
                    )
                )
                out[k] = self._token_for(v, kind)
            elif isinstance(v, dict):
                out[k] = self.sanitize_context(v)
            elif isinstance(v, list):
                out[k] = [
                    self.sanitize_context(item) if isinstance(item, dict)
                    else (self._token_for(item, "person") if isinstance(item, str) and kl in _NAME_KEYS
                          else item)
                    for item in v
                ]
            else:
                out[k] = v
        return out

    # --------------------------------------------------------------- rehydrate
    def rehydrate(self, text: str) -> str:
        """Replace every token in `text` with its real name. Tokens that the
        LLM hallucinated (no mapping) are passed through untouched."""
        if not text or not self._rev:
            return text or ""
        # Use a single regex pass for efficiency.
        pattern = re.compile(r"\[(?:STUDENT|TEACHER|PARENT|PERSON)_\d+\]")
        return pattern.sub(lambda m: self._rev.get(m.group(0), m.group(0)), text)

    # ------------------------------------------------------------------ debug
    @property
    def mapping(self) -> Dict[str, str]:
        return dict(self._fwd)


def collect_names_from_context(context: Optional[Dict[str, Any]]) -> List[str]:
    """Best-effort extractor for downstream callers that want to seed the
    pseudonymizer from a context dict before sanitising free-form text."""
    if not context:
        return []
    out: List[str] = []
    for k, v in context.items():
        kl = k.lower() if isinstance(k, str) else ""
        if isinstance(v, str) and kl in _NAME_KEYS and v.strip():
            out.append(v.strip())
        elif isinstance(v, dict):
            out.extend(collect_names_from_context(v))
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    out.extend(collect_names_from_context(item))
                elif isinstance(item, str) and kl in _NAME_KEYS:
                    out.append(item.strip())
    return out
