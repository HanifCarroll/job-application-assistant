from __future__ import annotations

import json
from pathlib import Path

from job_application_assistant.models import ContextBundle, DraftRequest, OpportunitySnapshot, ResumeContext
from job_application_assistant.drafts.prompts import build_draft_prompt


SECTION_HEADINGS = {
    "Information rules:",
    "Writing rules:",
    "Language rules:",
    "Draft rules:",
    "Explain experience simply:",
    "Audit fields only:",
    "Context packet:",
}

APPLICANT_FACING_SECTIONS = [
    "Writing rules",
    "Language rules",
    "Draft rules",
    "Explain experience simply",
]

REQUIRED_AUDIT_FIELDS = ["claims[]", "decisions[]", "warnings", "caused_by"]

BANNED_APPLICANT_FACING_TERMS = [
    "supplied context",
    "source evidence",
    "source refs",
    "proof",
    "claim",
    "claims[]",
    "decisions[]",
    "warnings",
    "caused_by",
    "audit",
    "source-tracking",
]


def test_prompt_contract_includes_required_output_fields() -> None:
    prompt = _prompt()
    upwork_prompt = _upwork_prompt()

    assert "information below" in prompt
    assert "Do not invent" in prompt
    assert "`draft_type`" in prompt
    assert "`draft_text`" in prompt
    assert "`cover_letter`" in prompt
    assert "`upwork_proposal`" not in prompt
    assert "`upwork_proposal`" in upwork_prompt
    assert "`cover_letter`" not in upwork_prompt
    assert "`selected_angle.key`" in prompt
    assert "primary_text" not in prompt
    assert "`proposal`" not in prompt
    assert "short_application_message" not in prompt
    assert "question_answers[]" not in prompt


def test_prompt_includes_resume_context_and_source_label() -> None:
    prompt = _prompt()

    assert '"resume"' in prompt
    assert "Senior product engineer with Python systems work." in prompt
    assert "`resume.text`" in prompt


def test_prompt_contract_separates_applicant_copy_from_audit_fields() -> None:
    for prompt in (_prompt(), _upwork_prompt()):
        sections = _sections(prompt)
        applicant_copy_sections = "\n".join(sections[name] for name in APPLICANT_FACING_SECTIONS)
        audit_section = sections["Audit fields only"]

        for term in BANNED_APPLICANT_FACING_TERMS:
            assert term not in applicant_copy_sections.lower()

        for field in REQUIRED_AUDIT_FIELDS:
            assert field in audit_section

        assert "where it came from" in audit_section
        assert "applicant-facing draft" in audit_section


def test_prompt_language_rules_target_nontechnical_plain_language() -> None:
    for prompt in (_prompt(), _upwork_prompt()):
        sections = _sections(prompt)
        language_rules = sections["Language rules"]

        for required in ["smart nontechnical hiring manager or client", "simple, clear, concise, direct language"]:
            assert required in language_rules

        for required in ["Avoid jargon", "buzzwords", "abstract phrases", "business or product outcomes"]:
            assert required in language_rules

        for vague_phrase in ["scalable architecture", "robust solution", "end-to-end", "production-ready", "leveraging technology"]:
            assert vague_phrase in language_rules

        assert "one clear idea per sentence" in language_rules
        assert "revise the draft once to remove jargon" in language_rules


def test_cover_letter_prompt_targets_job_platform_contracts() -> None:
    sections = _sections(_prompt())
    draft_rules = sections["Draft rules"]

    for required in ["cover letter", "Dice", "Indeed", "ZipRecruiter", "real applicant", "plain language"]:
        assert required in draft_rules

    for required in ["exactly match", "named tool or industry", "do not apologize", "closest real experience"]:
        assert required in draft_rules

    assert "Best,\nHanif Carroll" in draft_rules
    assert "Upwork client" not in draft_rules
    assert "next-step question" not in draft_rules
    assert "compliance report" in draft_rules
    assert "Prefer framing like" not in "\n".join(sections.values())


def test_upwork_prompt_targets_freelancer_proposal_contracts() -> None:
    sections = _sections(_upwork_prompt())
    draft_rules = sections["Draft rules"]
    experience_rules = sections["Explain experience simply"]

    for required in ["freelancer proposal", "Upwork client", "90-140 words", "3 short paragraphs maximum"]:
        assert required in draft_rules

    for required in ["preview-friendly", "Do not open with generic enthusiasm", "next-step question"]:
        assert required in draft_rules

    for banned_opener in ['"You need"', '"You\'re looking for"', "generic restatement of the job post"]:
        assert banned_opener in draft_rules

    assert "direct fit statement" in draft_rules
    assert "names the project in plain language" in draft_rules
    assert "job-board cover letter" in draft_rules
    assert "signoff" in draft_rules
    assert "Best,\nHanif Carroll" not in draft_rules
    assert "Dice" not in draft_rules
    assert "most relevant project example" in experience_rules
    assert "Prefer framing like" not in "\n".join(sections.values())


def test_draft_schema_rejects_old_output_fields() -> None:
    schema = json.loads(Path("schemas/draft_response.schema.json").read_text(encoding="utf-8"))

    assert "draft_text" in schema["required"]
    assert "draft_text" in schema["properties"]
    assert "primary_text" not in schema["properties"]
    assert "proposal" not in schema["properties"]
    assert "short_message" not in schema["properties"]
    assert "question_answers" not in schema["required"]
    assert "question_answers" not in schema["properties"]
    assert schema["properties"]["draft_type"]["enum"] == ["cover_letter", "upwork_proposal"]


def _prompt() -> str:
    return build_draft_prompt(
        DraftRequest(opportunity=OpportunitySnapshot(source="dice", title="Software Engineer")),
        ContextBundle(
            profile="Product-minded full-stack engineer.",
            resume=ResumeContext(text="Senior product engineer with Python systems work."),
            offers=[],
            projects=[],
        ),
    )


def _upwork_prompt() -> str:
    return build_draft_prompt(
        DraftRequest(
            opportunity=OpportunitySnapshot(source="upwork", title="Build a CMS website"),
            draft_type="upwork_proposal",
        ),
        ContextBundle(
            profile="Product-minded full-stack engineer.",
            resume=ResumeContext(text="Senior product engineer with Python systems work."),
            offers=[],
            projects=[],
        ),
    )


def _sections(prompt: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"Preamble": []}
    current = "Preamble"
    for line in prompt.splitlines():
        stripped = line.strip()
        if stripped in SECTION_HEADINGS:
            current = stripped.removesuffix(":")
            sections[current] = []
            continue
        sections[current].append(line)
    return {name: "\n".join(lines) for name, lines in sections.items()}
