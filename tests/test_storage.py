from __future__ import annotations

from pathlib import Path

import pytest

from job_application_assistant.models import DraftRequest, UpworkProject
from job_application_assistant.drafts.storage import DraftStore, DraftStoreValidationError, make_stored_draft


def test_store_round_trips_draft_response(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts.db")
    store.init()
    request = DraftRequest(project=UpworkProject(title="Job"))
    draft = make_stored_draft(
        request,
        {
            "draft_text": "I can help with this.",
            "draft_type": "cover_letter",
            "subject_line": "",
            "selected_angle": {
                "key": "ai",
                "label": "AI",
                "promise": "AI",
                "caused_by": ["offer.ai"],
            },
            "role_classification": "AI workflow",
            "application_strategy": "Lead with relevant workflow proof.",
            "selected_projects": [],
            "rejected_projects": [],
            "decisions": [],
            "claims": [],
            "warnings": [],
        },
    )

    store.insert(draft)
    response = store.get_response(draft.id)

    assert response is not None
    assert response.draft_text == "I can help with this."
    assert response.selected_angle.label == "AI"


def test_store_reports_obsolete_stored_draft_schema(tmp_path: Path) -> None:
    store = DraftStore(tmp_path / "drafts.db")
    store.init()
    request = DraftRequest(project=UpworkProject(title="Job"))
    draft = make_stored_draft(
        request,
        {
            "draft_text": "I can help with this.",
            "draft_type": "cover_letter",
            "subject_line": "",
            "selected_angle": {
                "key": "ai",
                "label": "AI",
                "promise": "AI",
                "caused_by": ["offer.ai"],
            },
            "role_classification": "AI workflow",
            "application_strategy": "Lead with relevant workflow proof.",
            "selected_projects": [],
            "rejected_projects": [],
            "decisions": [],
            "claims": [],
            "warnings": [],
        },
    )
    store.insert(draft)
    with store._connect() as conn:
        conn.execute(
            """
            update drafts
            set draft_json = json_set(draft_json, '$.question_answers', json('[]'))
            where id = ?
            """,
            (draft.id,),
        )

    with pytest.raises(DraftStoreValidationError, match="Regenerate the draft"):
        store.get_stored_draft(draft.id)

    with pytest.raises(DraftStoreValidationError, match="Regenerate the draft"):
        store.list_stored_drafts()

    assert store.list_stored_drafts(skip_invalid=True) == []
