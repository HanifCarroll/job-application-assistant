from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from job_application_assistant.codex_provider import CodexProvider
from job_application_assistant.config import AppPaths
from job_application_assistant.drafts.pipeline import run_draft_pipeline
from job_application_assistant.models import (
    CodexRunTiming,
    ContextBundle,
    ContextProject,
    DraftRequest,
    OfferAngle,
    OpportunitySnapshot,
)
from job_application_assistant.drafts.storage import DraftStore


class FakeCodex:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths
        self.calls: list[tuple[str, str, Path | None]] = []

    def generate(
        self,
        prompt: str,
        phase: str = "unknown",
        on_timing: Callable[[CodexRunTiming], None] | None = None,
        schema_path: Path | None = None,
    ) -> dict[str, object]:
        self.calls.append((phase, prompt, schema_path))
        return _draft_json("Draft from frontend staff augmentation.")


def test_pipeline_uses_single_full_context_draft_pass(tmp_path: Path) -> None:
    paths = AppPaths(runtime_dir=tmp_path, codex_runs_dir=tmp_path / "codex-runs")
    codex = FakeCodex(paths)
    store = DraftStore(tmp_path / "drafts.db")
    store.init()
    context = _context_bundle()
    request = DraftRequest(
        opportunity=OpportunitySnapshot.model_validate(
            {
                "source": "dice",
                "title": "Senior Software Engineer",
                "company": "Motion Recruitment Partners, LLC",
                "description": (
                    "The client is looking to add one additional resource to support an existing team member. "
                    "This is not a lead or stakeholder-facing role. The primary need is TypeScript, React, NextJS, "
                    "Jira, and roadmap execution."
                ),
                "skills": ["React", "TypeScript"],
                "source_text": "Similar job says launch your career, but that text is unrelated page chrome.",
            }
        )
    )

    result = run_draft_pipeline(
        request=request,
        context=context,
        codex=cast(CodexProvider, codex),
        store=store,
    )

    assert [call[0] for call in codex.calls] == ["draft"]
    assert codex.calls[0][2] is None
    assert '"available_offers"' in codex.calls[0][1]
    assert '"available_projects"' in codex.calls[0][1]
    assert "mucho-hangouts" in codex.calls[0][1]
    assert "source_text" not in codex.calls[0][1]
    assert "unrelated page chrome" not in codex.calls[0][1]
    assert result.stored.draft.draft_text == "Draft from frontend staff augmentation."
    assert result.stored.draft.selected_angle.key == "frontend_staff_augmentation"
    assert result.stored.draft.selected_projects == ["genrupt"]
    assert result.stored.draft.rejected_projects[0].slug == "mucho-hangouts"


def _context_bundle() -> ContextBundle:
    return ContextBundle(
        profile="# Hanif\n\nBased in Buenos Aires, works US hours, contracts through HC Studio LLC.",
        offers=[
            OfferAngle(
                key="mvp_launch",
                label="MVP launch",
                use_when=["mvp", "launch"],
                promise="Cut and ship the first useful version.",
                source_ref="portfolio.service_offers.mvp",
            )
        ],
        projects=[
            ContextProject(
                slug="mucho-hangouts",
                title="Social Events Platform",
                track="mvp_build",
                proof_type="client",
                service="Fractional CTO",
                technologies=["Node.js", "TypeScript", "React"],
                best_for=["launch", "team support"],
                claim="Helped a live React product stabilize.",
                source_refs={
                    "project.mucho-hangouts.solution": "Improved typed patterns and messaging flows.",
                    "project.mucho-hangouts.technologies": "Node.js TypeScript React",
                },
            ),
            ContextProject(
                slug="genrupt",
                title="Amazon Creative Ops Platform",
                track="ai_systems",
                proof_type="client",
                service="Product engineering",
                technologies=["Next.js", "TypeScript", "React", "Zustand"],
                best_for=["ai", "automation"],
                claim="Helped clean up a production Next.js product.",
                source_refs={
                    "project.genrupt.solution": "Cleaned up routes, services, client state, and request ownership.",
                    "project.genrupt.technologies": "Next.js TypeScript React Zustand",
                },
            ),
        ],
    )


def _draft_json(text: str) -> dict[str, object]:
    return {
        "draft_text": text,
        "draft_type": "cover_letter",
        "subject_line": "",
        "selected_angle": {
            "key": "frontend_staff_augmentation",
            "label": "Frontend staff augmentation",
            "promise": "Add dependable TypeScript, React, and Next.js capacity inside the existing team.",
            "caused_by": ["opportunity.description", "opportunity.skills", "profile"],
        },
        "role_classification": "frontend staff augmentation",
        "application_strategy": "Lead with hands-on frontend execution for an existing team, not MVP launch work.",
        "selected_projects": ["genrupt"],
        "rejected_projects": [
            {
                "slug": "mucho-hangouts",
                "reason": "Relevant React proof, but weaker than Genrupt for Next.js-specific work.",
                "caused_by": ["project.mucho-hangouts.technologies", "project.genrupt.technologies"],
            }
        ],
        "decisions": [],
        "claims": [],
        "warnings": [],
    }
