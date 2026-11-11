from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

from job_application_assistant.context.indexer import build_context, load_context


def test_build_context_indexes_portfolio_projects(tmp_path: Path) -> None:
    portfolio = tmp_path / "portfolio"
    resume_path = tmp_path / "resume.pdf"
    projects_dir = portfolio / "projects"
    projects_dir.mkdir(parents=True)
    (portfolio / "profile.md").write_text("# Test Profile\n\nBuilds reliable software.", encoding="utf-8")
    _write_pdf(resume_path, ["Hanif Carroll", "Senior product engineer", "Built Python and TypeScript systems."])
    (portfolio / "offers.json").write_text(
        json.dumps(
            [
                {
                    "key": "reliability",
                    "label": "Reliability",
                    "use_when": ["reliable"],
                    "promise": "Make critical flows reliable.",
                    "source_ref": "offers.reliability",
                }
            ]
        ),
        encoding="utf-8",
    )
    (projects_dir / "demo.json").write_text(
        json.dumps(
            {
                "slug": "demo",
                "title": "Demo AI Workflow",
                "description": "Built an auditable AI workflow.",
                "proofType": "experiment",
                "service": "Product Engineering Prototype",
                "track": "ai_systems",
                "technologies": ["Python", "Playwright", "OpenAI"],
                "bestFor": ["browser automation"],
                "result": ["Kept evidence visible for review."],
            }
        ),
        encoding="utf-8",
    )

    bundle = build_context(portfolio, tmp_path / "context", resume_path)
    loaded = load_context(tmp_path / "context")

    assert len(bundle.projects) == 1
    assert bundle.profile.startswith("# Test Profile")
    assert "Built Python and TypeScript systems." in bundle.resume.text
    assert bundle.resume.warnings == []
    assert bundle.offers[0].key == "reliability"
    assert "Senior product engineer" in loaded.resume.text
    assert json.loads((tmp_path / "context" / "resume.json").read_text(encoding="utf-8"))["warnings"] == []
    assert loaded.projects[0].slug == "demo"
    assert "ai" in loaded.projects[0].best_for
    assert "browser automation" in loaded.projects[0].best_for


def test_build_context_records_missing_resume_warning(tmp_path: Path) -> None:
    portfolio = tmp_path / "portfolio"
    portfolio.mkdir()

    bundle = build_context(portfolio, tmp_path / "context", tmp_path / "missing-resume.pdf")
    loaded = load_context(tmp_path / "context")

    assert bundle.resume.text == ""
    assert "Resume PDF was not found" in bundle.resume.warnings[0]
    assert loaded.resume == bundle.resume


def _write_pdf(path: Path, lines: list[str]) -> None:
    canvas = Canvas(str(path), pagesize=letter)
    y = 740
    for line in lines:
        canvas.drawString(72, y, line)
        y -= 16
    canvas.save()
