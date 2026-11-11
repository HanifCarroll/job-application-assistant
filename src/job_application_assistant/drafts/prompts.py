from __future__ import annotations

import json

from job_application_assistant.models import ContextBundle, DraftRequest


LANGUAGE_RULES = """Language rules:
- Write for a smart nontechnical hiring manager or client.
- Use simple, clear, concise, direct language.
- Avoid jargon, buzzwords, and abstract phrases.
- Prefer business or product outcomes over technical explanation.
- If a technical term from the job post is necessary, use it once and connect it to the client's outcome.
- Replace vague phrases like "scalable architecture", "robust solution", "end-to-end", "production-ready", and "leveraging technology" with concrete plain-English descriptions of what was built or improved.
- Keep sentences short. Prefer one clear idea per sentence.
- Before returning, revise the draft once to remove jargon and make it sound like a capable person explaining their fit plainly."""


def build_draft_prompt(request: DraftRequest, context: ContextBundle) -> str:
    if request.draft_type == "upwork_proposal":
        return build_upwork_proposal_prompt(request, context)
    return build_cover_letter_prompt(request, context)


def build_cover_letter_prompt(request: DraftRequest, context: ContextBundle) -> str:
    return _build_prompt(
        request,
        context,
        purpose="job-platform cover letter",
        draft_rules="""Draft rules:
- Write a concise employer-facing job-platform cover letter for Dice, Indeed, ZipRecruiter, recruiter portals, or similar job boards.
- Use 3-4 short paragraphs and 160-240 words unless the opportunity clearly needs less.
- Address the hiring team directly and professionally.
- Write like a real applicant to a recruiter. Be direct, calm, and specific. Use plain language. Do not sound like a compliance report.
- Open with the role and the strongest honest reason this background fits.
- Connect 1-2 specific experience points to the job requirements.
- Add useful context beyond a resume: working style, similar domain fit, availability, contract setup, or ability to adapt to new tools and domains.
- If the background does not exactly match a named tool or industry, do not apologize or list what is missing. Instead, connect the closest real experience and keep the statement modest.
- Close with interest in discussing fit for the role.
- End the cover letter with this exact signoff:
Best,
Hanif Carroll""",
        experience_rules="""Explain experience simply:
- Lead each example with the product, team, or business problem.
- Explain the applicant's responsibility in plain business or product language.
- Name only the 1-2 technical details that most directly connect to the role.
- Prefer outcomes, ownership, collaboration, and reliability over implementation inventory.
- Use specialist terms when they appear in the job post or are essential to the fit.
- Group many technical details under a simpler theme, such as access control, background processing, service reliability, data modeling, or role-based workflows.""",
    )


def build_upwork_proposal_prompt(request: DraftRequest, context: ContextBundle) -> str:
    return _build_prompt(
        request,
        context,
        purpose="Upwork freelancer proposal",
        draft_rules="""Draft rules:
- Write a short freelancer proposal for the Upwork client, not a job-board cover letter.
- Use 90-140 words by default. Use up to 180 words only when the job post is complex and the extra detail directly improves fit.
- Use 3 short paragraphs maximum.
- Make the first sentence client-specific and preview-friendly: name the concrete problem, product, workflow, or outcome from the job post.
- Do not open with generic enthusiasm, a greeting, or a summary of the applicant's background.
- Do not start with "You need", "You're looking for", or a generic restatement of the job post.
- Start with a direct fit statement that names the project in plain language.
- Paragraph 1: show understanding of the client's project and the strongest honest fit.
- Paragraph 2: give 1 highly relevant example, or 2 brief examples only if both map directly to stated needs.
- Paragraph 3: describe the likely first step or implementation approach, then end with one useful next-step question.
- Prefer client outcomes, scope clarity, risk reduction, and execution plan over biography.
- Do not include a signoff, contact information, hourly-rate discussion, or availability unless the user notes specifically ask for it.""",
        experience_rules="""Explain experience simply:
- Lead each example with the product, team, or business problem.
- Explain the applicant's responsibility in plain business or product language.
- Name only the 1-2 technical details that most directly connect to the role.
- Prefer outcomes, ownership, collaboration, and reliability over implementation inventory.
- Use specialist terms when they appear in the job post or are essential to the fit.
- Group many technical details under a simpler theme, such as access control, background processing, service reliability, data modeling, or role-based workflows.
- Use only the most relevant project example; omit otherwise strong examples if they do not directly map to the client's stated project.""",
    )


def _build_prompt(
    request: DraftRequest,
    context: ContextBundle,
    *,
    purpose: str,
    draft_rules: str,
    experience_rules: str,
) -> str:
    opportunity = request.opportunity_snapshot()
    packet = {
        "profile": context.profile,
        "resume": context.resume.model_dump(),
        "opportunity": opportunity.model_dump(),
        "draft_type": request.draft_type,
        "user_notes": request.user_notes,
        "style": request.style,
        "available_offers": [offer.model_dump() for offer in context.offers],
        "available_projects": [project.model_dump() for project in context.projects],
    }
    return f"""You write one {purpose} from the information below.

Information rules:
- Use only the information below. Do not invent experience, metrics, tools, client names, timelines, or outcomes.
- Treat `resume.text` as the only resume content. If `resume.warnings` says the resume is missing or unreadable, do not fill resume details from memory or assumptions.

Return JSON matching the provided schema.

Writing rules:
- Set `draft_type` to `{request.draft_type}`.
- Put the generated application body in `draft_text`.
- Classify the role in `role_classification` in plain terms, such as "frontend staff augmentation", "founder MVP build", or "AI workflow automation".
- Choose the strongest angle for this job. You may reuse an available offer, narrow it, or create a custom angle when the offers do not fit.
- Choose 0-3 project slugs from `available_projects`; prefer 1-2. Use no project if none is genuinely relevant.

{LANGUAGE_RULES}

{draft_rules}

{experience_rules}

Audit fields only:
- Set `selected_angle.key` to an available offer key when reusing one; otherwise set a short custom key such as "frontend_staff_augmentation".
- Include rejected projects when they seem plausible from surface wording but are strategically weak.
- Every application claim must appear in `claims[]` with where it came from in `caused_by`.
- Every meaningful drafting or strategy decision must appear in `decisions[]` with where it came from in `caused_by`.
- Add warnings for weak experience matches, noisy extraction, missing job details, missing exact tool or industry matches, or a role that should not use a project example.
- When exact tool or industry experience is weak but the profile or projects show relevant adaptation across tools, domains, or product constraints, include one honest adaptability claim with where it came from.
- Use these labels in `caused_by`: `profile`, `resume.text`, opportunity fields like `opportunity.description`, offer `source_ref` values, and project labels from each project's `source_refs`, `project.<slug>.claim`, and `project.<slug>.technologies`.
- Keep audit and source-tracking language in these JSON audit fields, not in the applicant-facing draft.

Context packet:
```json
{json.dumps(packet, indent=2)}
```
"""
