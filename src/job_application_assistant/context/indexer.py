from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from job_application_assistant.context.resume import extract_resume_context
from job_application_assistant.models import ContextBundle, ContextProject, OfferAngle, ResumeContext


DEFAULT_PROFILE_TEXT = """# Your Name

Product-minded software engineer.

Positioning:
- Builds scoped, testable software from messy product requirements.
- Works close to founders, users, and operators.
- Values clear tradeoffs, reliable delivery, and maintainable systems.

Working style:
- Start with the real constraint.
- Reduce before building.
- Explain product, UX, architecture, and implementation tradeoffs directly.
- Prefer auditable workflows with verification, logs, and human review.
"""


DEFAULT_OFFERS = [
    OfferAngle(
        key="mvp_launch",
        label="MVP launch",
        use_when=["mvp", "prototype", "launch", "nontechnical founder", "first version", "mobile app", "web app"],
        promise="Cut the first version to the smallest useful shape, build it, and leave a clear path after launch.",
        source_ref="default.offers.mvp_launch",
    ),
    OfferAngle(
        key="fractional_product_engineering",
        label="Fractional product engineering",
        use_when=["founder-led", "architecture", "ux", "scope", "technical decisions", "team", "shipping"],
        promise="Bring senior product judgment close to implementation so active product constraints turn into shipped work.",
        source_ref="default.offers.fractional_product_engineering",
    ),
    OfferAngle(
        key="ai_workflow_system",
        label="AI workflow system",
        use_when=["ai", "agent", "rag", "eval", "llm", "openai", "anthropic", "mcp", "scraping", "playwright", "automation"],
        promise="Build grounded AI workflows where retrieval, evidence, async jobs, and auditability matter more than a demo.",
        source_ref="default.offers.ai_workflow_system",
    ),
    OfferAngle(
        key="operations_tooling",
        label="Operations tooling",
        use_when=["internal tool", "spreadsheet", "manual workflow", "operations", "inventory", "dashboard", "admin", "workflow"],
        promise="Turn messy operational work into a small product system people can actually use.",
        source_ref="default.offers.operations_tooling",
    ),
]


TRACK_BEST_FOR: dict[str, list[str]] = {
    "mvp_build": ["mvp", "prototype", "launch", "founder", "product strategy"],
    "mvp_validation": ["validation", "fake door", "market test", "landing page"],
    "ai_systems": ["ai", "llm", "agent", "rag", "evals", "automation", "evidence"],
    "workflow_automation": ["internal tool", "operations", "workflow", "admin", "automation"],
    "launch_site": ["website", "portfolio", "launch site", "marketing site"],
}


PROJECT_BEST_FOR: dict[str, list[str]] = {}


def build_context(portfolio_root: Path, context_dir: Path, resume_pdf_path: Path) -> ContextBundle:
    context_dir.mkdir(parents=True, exist_ok=True)
    project_paths = _project_paths(portfolio_root)
    projects = [_project_from_json(path) for path in project_paths]
    bundle = ContextBundle(
        profile=_profile_text(portfolio_root),
        resume=extract_resume_context(resume_pdf_path),
        offers=_offers(portfolio_root),
        projects=projects,
    )

    (context_dir / "me.md").write_text(bundle.profile, encoding="utf-8")
    (context_dir / "resume.json").write_text(json.dumps(bundle.resume.model_dump(), indent=2), encoding="utf-8")
    (context_dir / "offers.json").write_text(
        json.dumps([offer.model_dump() for offer in bundle.offers], indent=2),
        encoding="utf-8",
    )
    with (context_dir / "projects.jsonl").open("w", encoding="utf-8") as handle:
        for project in bundle.projects:
            handle.write(json.dumps(project.model_dump(), ensure_ascii=False) + "\n")

    return bundle


def load_context(context_dir: Path) -> ContextBundle:
    profile_path = context_dir / "me.md"
    resume_path = context_dir / "resume.json"
    offers_path = context_dir / "offers.json"
    projects_path = context_dir / "projects.jsonl"
    if not profile_path.exists() or not resume_path.exists() or not offers_path.exists() or not projects_path.exists():
        raise FileNotFoundError(f"Context files missing in {context_dir}. Run `jaa reindex` first.")

    profile = profile_path.read_text(encoding="utf-8")
    resume = ResumeContext.model_validate(json.loads(resume_path.read_text(encoding="utf-8")))
    offers = [OfferAngle.model_validate(item) for item in json.loads(offers_path.read_text(encoding="utf-8"))]
    projects = [
        ContextProject.model_validate(json.loads(line))
        for line in projects_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return ContextBundle(profile=profile, resume=resume, offers=offers, projects=projects)


def ensure_context(portfolio_root: Path, context_dir: Path, resume_pdf_path: Path) -> ContextBundle:
    try:
        return load_context(context_dir)
    except FileNotFoundError:
        return build_context(portfolio_root, context_dir, resume_pdf_path)


def _project_from_json(path: Path) -> ContextProject:
    data = json.loads(path.read_text(encoding="utf-8"))
    slug = str(data["slug"])
    source_url = str(data.get("sourceUrl") or data.get("url") or "")
    source_refs = _source_refs(slug, data)
    configured_best_for = data.get("bestFor") or data.get("best_for") or []
    best_for = [
        *TRACK_BEST_FOR.get(str(data.get("track", "")), []),
        *PROJECT_BEST_FOR.get(slug, []),
        *[str(item) for item in configured_best_for],
    ]
    claim = _first_sentence(data.get("description")) or _join_field(data.get("result")) or str(data.get("title", slug))
    return ContextProject(
        slug=slug,
        title=str(data.get("title", slug)),
        track=str(data.get("track", "")),
        proof_type=str(data.get("proofType", "")),
        service=str(data.get("service", "")),
        role=str(data.get("role", "")),
        timeline=str(data.get("timeline", "")),
        technologies=[str(item) for item in data.get("technologies", [])],
        best_for=sorted(set(best_for)),
        claim=claim,
        source_url=source_url,
        source_refs=source_refs,
    )


def _source_refs(slug: str, data: dict[str, Any]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for field in ["description", "problem", "solution", "result", "deliveryHighlights", "outcomes", "technologies"]:
        if field in data:
            refs[f"project.{slug}.{field}"] = _join_field(data[field])
    refs[f"project.{slug}.title"] = str(data.get("title", slug))
    refs[f"project.{slug}.track"] = str(data.get("track", ""))
    return refs


def _profile_text(portfolio_root: Path) -> str:
    for filename in ["profile.md", "me.md"]:
        path = portfolio_root / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
    return DEFAULT_PROFILE_TEXT


def _offers(portfolio_root: Path) -> list[OfferAngle]:
    path = portfolio_root / "offers.json"
    if not path.exists():
        return DEFAULT_OFFERS
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [OfferAngle.model_validate(item) for item in raw]


def _project_paths(portfolio_root: Path) -> list[Path]:
    candidates = [
        portfolio_root / "projects",
        portfolio_root / "src" / "lib" / "projects",
    ]
    paths: list[Path] = []
    for directory in candidates:
        if directory.exists():
            paths.extend(sorted(directory.glob("*.json")))
    return sorted(set(paths))


def _join_field(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    if isinstance(value, str):
        return value
    return ""


def _first_sentence(value: object) -> str:
    text = _join_field(value).strip()
    if not text:
        return ""
    return text.split(". ")[0].rstrip(".") + "."
