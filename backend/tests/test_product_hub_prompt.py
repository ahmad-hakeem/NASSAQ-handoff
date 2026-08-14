"""Unit tests for the Hakim engineering-prompt generation (product-hub).

These cover the deterministic fallback structure and the strict validator that
enforces the canonical Replit execution-ready section contract. They are pure
(no DB / no LLM) so they run fast and deterministically.
"""

import re

from src.modules.platform.controllers.product_hub_routes import (
    _validate_engineering_prompt,
    _fallback_engineering_prompt,
    _collect_issue_facts,
    _sanitize_fact,
    _section_header,
    ENGINEERING_PROMPT_SECTIONS,
    _LEGACY_PROMPT_MARKERS,
    _HEADER_RE,
)


def _make_facts(**over):
    issue = {
        "issue_number": 7,
        "issue_type": "bug",
        "title": "تحسين عرض الملفات المرفقة",
        "priority": "high",
        "section": "مركز ذكاء المنتج",
        "page": "إدارة الفئة",
        "account_type": "platform_admin",
        "current_behavior": "لا تظهر الملفات المرفقة بعد الإنشاء",
        "expected_behavior": "يجب أن تظهر الملفات المرفقة",
        "steps_to_reproduce": "افتح الصفحة\nأنشئ تحدي",
        "reproducibility": "always",
        "error_message": "TypeError: x",
        "url": "https://nassaqapp.com/admin/product-hub/submit",
        "device": "desktop",
        "browser": "Chrome",
        "impact": ["blocks_work"],
        "hakim_analysis": {"suggested_team": "Backend", "technical_notes": "tn"},
        "attachments": [{"file_url": "data:..."}],
    }
    issue.update(over)
    return _collect_issue_facts(issue)


def _good_prompt(subheaders=False):
    blocks = []
    for s in ENGINEERING_PROMPT_SECTIONS:
        body = "This is substantive, issue-specific content for the section."
        if subheaders and s == "Investigation Steps":
            body = "### Backend\nInspect routes.\n### Frontend\nInspect components."
        blocks.append(f"{_section_header(s)}\n{body}")
    return "\n\n".join(blocks)


# --- Fallback compliance -----------------------------------------------------

def test_fallback_validates():
    assert _validate_engineering_prompt(_fallback_engineering_prompt(_make_facts()))


def test_fallback_starts_with_objective_no_h1():
    fb = _fallback_engineering_prompt(_make_facts())
    lines = [ln for ln in fb.split("\n") if ln.strip()]
    assert lines[0].strip() == "## Objective"
    # No H1 banner anywhere.
    assert not any(re.match(r"^#\s+", ln) for ln in fb.split("\n"))


def test_fallback_has_all_sections_in_order():
    fb = _fallback_engineering_prompt(_make_facts())
    found = [ln[3:].strip() for ln in fb.split("\n") if ln.startswith("## ")]
    assert found == ENGINEERING_PROMPT_SECTIONS


def test_fallback_without_issue_number_still_valid():
    facts = _make_facts(issue_number="")
    assert _validate_engineering_prompt(_fallback_engineering_prompt(facts))


# --- Validator: positive cases ----------------------------------------------

def test_well_formed_prompt_validates():
    assert _validate_engineering_prompt(_good_prompt())


def test_subheaders_inside_sections_allowed():
    assert _validate_engineering_prompt(_good_prompt(subheaders=True))


def test_trailing_whitespace_on_header_tolerated():
    p = _good_prompt().replace("## Objective", "## Objective   ")
    assert _validate_engineering_prompt(p)


# --- Validator: negative cases ----------------------------------------------

def test_empty_text_rejected():
    assert not _validate_engineering_prompt("")
    assert not _validate_engineering_prompt("   \n  ")


def test_preamble_before_first_header_rejected():
    assert not _validate_engineering_prompt("Some intro text\n" + _good_prompt())


def test_h1_banner_rejected():
    assert not _validate_engineering_prompt("# NASSAQ Prompt\n" + _good_prompt())


def test_wrong_header_level_rejected():
    p = _good_prompt().replace("## Objective", "### Objective")
    assert not _validate_engineering_prompt(p)


def test_extra_top_level_header_rejected():
    p = _good_prompt() + "\n\n## Extra Section\nSome additional content here."
    assert not _validate_engineering_prompt(p)


def test_duplicate_header_rejected():
    p = _good_prompt() + "\n\n## Objective\nDuplicated objective content here."
    assert not _validate_engineering_prompt(p)


def test_out_of_order_rejected():
    p = "\n\n".join([
        f"{_section_header('Investigation Steps')}\nLong enough content here for the section.",
        f"{_section_header('Objective')}\nLong enough content here for the section.",
    ])
    assert not _validate_engineering_prompt(p)


def test_missing_section_rejected():
    sections = ENGINEERING_PROMPT_SECTIONS[:-1]
    p = "\n\n".join(f"{_section_header(s)}\nLong enough content here." for s in sections)
    assert not _validate_engineering_prompt(p)


def test_empty_section_content_rejected():
    p = "\n".join(_section_header(s) for s in ENGINEERING_PROMPT_SECTIONS)
    assert not _validate_engineering_prompt(p)


def test_legacy_markers_rejected():
    p = _good_prompt().replace(
        "This is substantive, issue-specific content for the section.",
        "[ISSUE TYPE]: bug — legacy descriptive content",
        1,
    )
    assert not _validate_engineering_prompt(p)
    assert not _validate_engineering_prompt(_good_prompt() + "\nEXECUTION INSTRUCTIONS")


# --- Sanitizer: user-controlled text cannot break the contract ---------------

def test_sanitize_escapes_leading_headers():
    out = _sanitize_fact("# H1 banner\n## injected section\nnormal line")
    assert not any(re.match(r"^#{1,6}\s", ln) for ln in out.split("\n"))


def test_sanitize_neutralizes_legacy_markers():
    for marker in _LEGACY_PROMPT_MARKERS:
        out = _sanitize_fact(f"prefix {marker.lower()} suffix")
        assert marker.upper() not in out.upper()


def test_fallback_validates_with_injected_headers_in_free_text():
    facts = _make_facts(
        current_behavior="Broken.\n# Fake H1\n## Fake Section\nmore detail",
        steps_to_reproduce="step one\n## Injected\nstep two",
        error_message="Trace:\n### deep\n# top",
        expected_behavior="Works.\n## Another fake",
    )
    assert _validate_engineering_prompt(_fallback_engineering_prompt(facts))


def test_fallback_validates_with_legacy_markers_in_free_text():
    facts = _make_facts(
        current_behavior="see [CURRENT BEHAVIOR] and EXECUTION INSTRUCTIONS here",
        hakim_analysis={"suggested_team": "Backend", "technical_notes": "HAKIM AI ANALYSIS notes"},
        title="[ISSUE TYPE] weird title",
    )
    assert _validate_engineering_prompt(_fallback_engineering_prompt(facts))


def test_llm_input_builder_runs_on_adversarial_facts():
    from src.modules.platform.controllers.product_hub_routes import _build_engineering_user_prompt
    facts = _make_facts(current_behavior="# x\n## y\n[ISSUE TYPE]")
    prompt = _build_engineering_user_prompt(facts)
    assert "Issue Type:" in prompt


# --- CommonMark edge cases: indented headers, CR endings, empty heading ------

def test_validator_rejects_indented_extra_header():
    # CommonMark allows 0-3 spaces of indent before an ATX heading.
    p = _good_prompt() + "\n\n   ## Sneaky Indented Section\nsome content here."
    assert not _validate_engineering_prompt(p)


def test_validator_rejects_indented_h1():
    p = "  # Indented Banner\n" + _good_prompt()
    assert not _validate_engineering_prompt(p)


def test_validator_handles_crlf_line_endings():
    p = _good_prompt().replace("\n", "\r\n")
    assert _validate_engineering_prompt(p)


def test_validator_rejects_empty_atx_heading():
    # '##' with no title is a valid (empty) ATX heading in CommonMark.
    p = _good_prompt() + "\n\n##\nstray content under empty heading."
    assert not _validate_engineering_prompt(p)


def test_sanitize_escapes_indented_and_empty_headers():
    out = _sanitize_fact("  ## indented\n\t# tabbed\n##\nplain")
    for ln in out.split("\n"):
        assert _HEADER_RE.match(ln) is None


def test_fallback_validates_with_indented_and_cr_injection():
    facts = _make_facts(
        current_behavior="Broken.\r\n   ## Indented Fake\r\n\t## Tabbed Fake",
        steps_to_reproduce="one\r## CR Fake\rtwo",
        error_message="oops\n##\nempty-heading injection",
    )
    assert _validate_engineering_prompt(_fallback_engineering_prompt(facts))
