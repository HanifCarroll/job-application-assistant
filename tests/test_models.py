from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from job_application_assistant.models import DraftRequest, OpportunitySnapshot, UpworkProject


def test_opportunity_snapshot_discards_obsolete_freeform_fields() -> None:
    snapshot = OpportunitySnapshot.model_validate(
        {
            "title": "Frontend contractor",
            "description": "React and TypeScript work.",
            "raw_text": "Old page-wide text should not reach prompts.",
            "source_text": "Flattened source text should not reach prompts.",
            "extraction_confidence": "high",
            "remote_status": "Remote",
        }
    )

    assert "raw_text" not in snapshot.model_dump()
    assert "source_text" not in snapshot.model_dump()
    assert "extraction_confidence" not in snapshot.model_dump()
    assert "remote_status" not in snapshot.model_dump()
    assert "Old page-wide text" not in snapshot.search_text()
    assert "Flattened source text" not in snapshot.search_text()
    assert "Remote" not in snapshot.search_text()


def test_opportunity_snapshot_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        OpportunitySnapshot.model_validate({"title": "Frontend contractor", "page_blob": "unsupported"})


def test_opportunity_snapshot_search_text_includes_company_context() -> None:
    snapshot = OpportunitySnapshot(
        title="Software Engineer",
        company="Sonitalent LLC",
        company_context="Sonitalent Corp is a global IT services company.",
    )

    assert "Sonitalent Corp is a global IT services company." in snapshot.search_text()


def test_upwork_project_budget_is_not_promoted_to_opportunity_context() -> None:
    opportunity = UpworkProject(
        title="Build a React dashboard",
        description="Need a clean frontend implementation.",
        budget="$1,000 fixed price",
    ).to_opportunity()

    assert "$1,000" not in json.dumps(opportunity.model_dump())
    assert "$1,000" not in opportunity.search_text()


@pytest.mark.parametrize("draft_type", ["question_answers", "short_application_message"])
def test_draft_request_rejects_removed_draft_types(draft_type: str) -> None:
    with pytest.raises(ValidationError):
        DraftRequest.model_validate({"opportunity": {"title": "Job"}, "draft_type": draft_type})
