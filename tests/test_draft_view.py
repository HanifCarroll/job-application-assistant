from __future__ import annotations

from job_application_assistant.drafts.view import render_draft_view
from job_application_assistant.models import DraftResponse


def test_render_draft_view_shows_readable_draft_and_links() -> None:
    draft = DraftResponse.model_validate(
        {
            "id": "draft-123",
            "created_at": "2026-06-19T20:00:00+00:00",
            "draft_text": "Dear Team,\n\nI can help.",
            "draft_type": "cover_letter",
            "subject_line": "Software Engineer Application",
            "selected_angle": {
                "key": "platform",
                "label": "Platform",
                "promise": "Ship reliable platform work.",
                "caused_by": ["offer.platform"],
            },
            "role_classification": "backend platform",
            "application_strategy": "Lead with service reliability.",
            "selected_projects": ["genrupt"],
            "rejected_projects": [],
            "decisions": [],
            "claims": [],
            "warnings": ["Review before sending."],
        }
    )

    html = render_draft_view(draft)

    assert "Software Engineer Application" in html
    assert "Dear Team," in html
    assert "I can help." in html
    assert 'href="/drafts/draft-123/pdf"' in html
    assert 'href="/drafts/draft-123?format=json"' in html
    assert "Review before sending." in html
