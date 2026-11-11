# Job Application Assistant

A local Chrome extension and Python backend for drafting auditable job applications with `codex exec`.

The extension extracts the current job opportunity, lets you review it, and sends it to a local FastAPI service. The backend sends the full saved context to Codex for a structured draft with strategy and audit metadata in one pass. Apply-enabled posting automation can open selected Dice, Indeed, and LinkedIn flows, advance result pages, and finish supported application steps.

This project is not affiliated with Upwork, Dice, Indeed, ZipRecruiter, Robert Half, LinkedIn, or any other job platform.

This is a personal local tool shared as-is for people who want to use or adapt it. No support is guaranteed.

## Features

- Extracts title, company, location, compensation, description, skills, and URL from supported job pages.
- Supports Upwork, Dice, Indeed, ZipRecruiter, Robert Half, and LinkedIn.
- Lets you edit the extracted job snapshot before drafting.
- Uses local saved context about you: profile, service offers, and project proof points.
- Runs one Codex pass over the full portfolio context to choose strategy and generate the draft.
- Returns structured audit data for decisions, claims, source evidence, and warnings.
- Persists draft jobs in SQLite so long Codex runs can be polled.
- Logs applied jobs in SQLite, including one-time CSV migration from the old spreadsheet.
- Provides a local dashboard for reviewing the SQLite application ledger.
- Shows an already-applied indicator in the extension side panel and supported job pages when the current URL is already in the ledger.
- Keeps side-panel state in `chrome.storage.local`, so closing and reopening the panel resumes an active job.
- Provides a Chrome options page for configuring the local backend URL.
- Drafts cover letters and Upwork proposals.
- Generates professional PDF cover letters and can reveal the generated file in Finder.
- Opens a persistent side panel on Dice, Indeed, and LinkedIn result pages for visible apply-enabled postings, selected application flows, and next-page navigation.

## Architecture

```text
Chrome action side panel
  -> content script chooses a site adapter
  -> adapter extracts a normalized OpportunitySnapshot
  -> background service worker starts a draft job
  -> FastAPI backend persists and runs the job
  -> codex exec draft pass sees profile, all offers, all projects, and the opportunity
  -> SQLite stores request and draft JSON
  -> side panel polls job status and displays draft + audit trail
  -> side panel or platform confirmation logs applied jobs to SQLite
```

## Requirements

- Python 3.13
- `uv`
- Chrome or another Chromium browser that supports Manifest V3 extensions
- OpenAI Codex CLI available as `codex` on your `PATH`

## Quick Start

```bash
git clone https://github.com/HanifCarroll/job-application-assistant.git
cd job-application-assistant
uv sync
uv run jaa reindex
uv run jaa serve
```

Then load the Chrome extension:

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Click "Load unpacked".
4. Select the repository's `extension/` directory.
5. Open the extension options page and confirm the backend URL, usually `http://127.0.0.1:8787`.

The checked-in `examples/portfolio` directory is only sample data. Replace it with your own context before using the tool seriously.

## Supported Sites

The extension uses site adapters that convert each page into the same normalized opportunity model.

| Site | Supported page shape |
| --- | --- |
| Upwork | Job feed cards and proposal/job-detail pages. |
| Dice | Job-detail pages, using `JobPosting` JSON-LD when available. Search result pages open a side panel that can list visible Easy Apply postings, open selected application flows, and advance to the next results page manually or after selected flows start. |
| Indeed | Search result pages with the selected job detail panel and `Apply with Indeed` postings. |
| ZipRecruiter | Search result pages with the selected job detail pane. |
| Robert Half | Search result pages with the selected job detail card. |
| LinkedIn | Job search/detail pages, Easy Apply result cards, and gated Easy Apply modal automation. |

The extension reads the job page you are viewing. Clicking the extension action opens a persistent side panel. On Dice, Indeed, and LinkedIn search results, the panel can list visible apply-enabled postings from the current page, open selected postings in new tabs, click each platform's apply control, then advance the original results tab to the next page and refresh the list. The panel also has a `Next page` button for skipping a results page without opening anything. It does not crawl job boards. On Dice application wizard pages, the side panel shows all active cover-letter PDF runs, keeps completed PDF actions available, and the page automation can click `Next` after the generated cover letter is attached and click `Submit` when Dice shows the review submit control. On LinkedIn Easy Apply modals opened through the posting picker, the assistant clicks familiar `Next`, `Review`, and `Submit application` controls, skips optional top-choice selection, unchecks `Follow`, closes LinkedIn's post-submit `Done` or `Not now` prompt when it appears, and stops on unfamiliar question screens until you move to a familiar step.

Application logging is conservative. The draft side panel provides a manual `Mark Applied` action for the current job snapshot. A separate content script also records a pending snapshot when a known platform submit control is clicked, then logs the application only after a platform-specific confirmation selector or confirmation URL is observed. Unknown application flows are not guessed from page-wide text.

## Configuration

Copy `.env.example` if you want local overrides:

```bash
cp .env.example .env
```

Supported environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `JOB_APPLICATION_ASSISTANT_PORTFOLIO_ROOT` | `examples/portfolio` | Source directory for profile, offers, and project proof points. |
| `JOB_APPLICATION_ASSISTANT_CONTEXT_DIR` | `data/context` | Generated context cache. |
| `JOB_APPLICATION_ASSISTANT_RUNTIME_DIR` | `.runtime` | Runtime directory for local backend artifacts. |
| `JOB_APPLICATION_ASSISTANT_PDF_OUTPUT_DIR` | `.runtime/cover-letters` | Directory where generated cover letter PDFs are saved. |
| `JOB_APPLICATION_ASSISTANT_PDF_ARCHIVE_DIR` | `.runtime/cover-letters/archive` | Directory where submitted cover letter PDFs are moved after the application is logged. |
| `JOB_APPLICATION_ASSISTANT_RESUME_PDF_PATH` | `~/Library/Mobile Documents/com~apple~CloudDocs/Downloads/Hanif-Carroll-Resume.pdf` | Resume PDF indexed into draft context and used for cover letter letterhead data. Phone-like contact items are omitted from exports. |
| `JOB_APPLICATION_ASSISTANT_DB_PATH` | `.runtime/drafts.db` | SQLite database path. |
| `JOB_APPLICATION_ASSISTANT_CODEX_RUNS_DIR` | `.runtime/codex-runs` | Per-run Codex workspaces. |
| `JOB_APPLICATION_ASSISTANT_CODEX_BINARY` | `codex` | Codex CLI executable. |
| `JOB_APPLICATION_ASSISTANT_CODEX_MODEL` | `gpt-5.5` | Model passed explicitly to `codex exec`. |
| `JOB_APPLICATION_ASSISTANT_CODEX_REASONING_EFFORT` | `low` | Reasoning effort passed explicitly to `codex exec`. |
| `JOB_APPLICATION_ASSISTANT_CODEX_TIMEOUT_SECONDS` | `180` | Timeout per Codex pass. |
| `JOB_APPLICATION_ASSISTANT_MAX_WORKERS` | `5` | Maximum concurrent async draft jobs. |

Example:

```bash
JOB_APPLICATION_ASSISTANT_PORTFOLIO_ROOT=/path/to/my/context uv run jaa reindex
uv run jaa serve
```

## Context Source Format

The context source directory can contain:

```text
my-context/
  profile.md
  offers.json
  projects/
    project-one.json
    project-two.json
```

`profile.md` is freeform Markdown about your positioning and working style.

Resume text is extracted from `JOB_APPLICATION_ASSISTANT_RESUME_PDF_PATH` during `jaa reindex` and cached in `data/context/resume.json`. Missing or unreadable resume PDFs produce an explicit context warning instead of made-up resume details.

`offers.json` is an array of proposal angles:

```json
[
  {
    "key": "saas_stabilization",
    "label": "SaaS stabilization",
    "use_when": ["production", "saas", "existing codebase"],
    "promise": "Stabilize production workflows through small, well-tested fixes.",
    "source_ref": "offers.saas_stabilization"
  }
]
```

Each project JSON should include proof points the proposal system is allowed to use:

```json
{
  "slug": "saas-stabilization",
  "title": "Production SaaS Stabilization",
  "description": "Took over an existing SaaS app and shipped targeted reliability fixes.",
  "proofType": "client",
  "service": "Full-stack product engineering",
  "track": "workflow_automation",
  "role": "Senior full-stack engineer",
  "timeline": "Ongoing",
  "technologies": ["React", "TypeScript", "PostgreSQL"],
  "result": ["Improved critical flows without a rewrite."],
  "deliveryHighlights": ["Repo audit", "Bug triage", "Targeted tests"],
  "sourceUrl": "https://example.com/projects/saas-stabilization"
}
```

The generated cache in `data/context` is intentionally ignored by Git. Rebuild it with:

```bash
uv run jaa reindex
```

The backend runs `codex exec` with `--ignore-user-config` and `--ignore-rules` so unrelated local MCP servers, plugins, hooks, or execpolicy files do not slow down or destabilize proposal generation. Model and reasoning effort are passed explicitly through the environment variables above.

## API

Useful local endpoints:

- `GET /health`: backend health and context count.
- `POST /context/reindex`: rebuild context from the configured source.
- `POST /draft-jobs`: create an async draft job.
- `GET /draft-jobs/{job_id}`: poll job status and result.
- `POST /applications`: log an applied job. Reuses an existing row when the normalized source URL already exists.
- `GET /applications`: list logged applications.
- `GET /applications/lookup?source_url=...`: check whether a normalized source URL already exists in the application ledger.
- `GET /dashboard`: browser dashboard for the application ledger.
- `POST /draft`: synchronous draft endpoint for debugging.
- `GET /drafts/{draft_id}`: show a readable draft page in a browser; fetch JSON with `?format=json`.
- `POST /drafts/{draft_id}/pdf`: generate a PDF for a stored cover letter draft.
- `GET /drafts/{draft_id}/pdf`: download the generated cover letter PDF.
- `POST /drafts/{draft_id}/pdf/reveal`: generate the PDF if needed and reveal it in Finder on macOS.

Job stages:

- `queued`
- `codex_draft`
- `saving`
- `done`
- `failed`

`POST /draft-jobs` accepts a normalized `opportunity` and `draft_type`. Supported draft types are `cover_letter` and `upwork_proposal`.

`GET /draft-jobs/{job_id}` also returns privacy-safe timing instrumentation under `timings`: queue time, per-stage durations, and per-`codex exec` subprocess metrics such as duration, exit code, timeout flag, output size, and JSON parse time. It does not include prompts, job descriptions, draft text, or personal context.

## Auditability

Every draft response includes:

- `draft_text`: the generated application body.
- `selected_angle`: the chosen application angle.
- `selected_projects[]`: project proof points used in the draft.
- `rejected_projects[]`: plausible but intentionally skipped proof points.
- `role_classification`: the model's concrete classification of the role.
- `application_strategy`: the drafting strategy used.
- `decisions[]`: why the system chose an angle or proof point.
- `claims[]`: factual claims used in the draft.
- `caused_by[]`: source refs that support each decision or claim.
- `warnings[]`: issues the model surfaced during drafting.

The backend stores the original request and one draft JSON payload. The draft includes role classification, application strategy, selected and rejected projects, decisions, claims, and warnings. That makes it possible to trace application language back to the job snapshot, personal context, or user notes that caused it.

## Application Ledger

Applications are stored in the same SQLite database as drafts. Rows are deduplicated by normalized source URL so importing historical data and later logging the same job does not create duplicates. The first `applied_at` value is preserved; later logs can attach draft IDs or refresh title, company, and location from a better page snapshot.

Import a Numbers-exported CSV with the columns `Role`, `Company`, `Link`, and `Date Sent`:

```bash
uv run jaa applications import "/path/to/Job Search.csv"
```

List or export the SQLite ledger:

```bash
uv run jaa applications list --limit 25
uv run jaa applications export --output applications.csv
```

View the local dashboard while the backend is running:

```text
http://127.0.0.1:8787/dashboard
```

The dashboard supports search, source/date filters including `Sent today` and `Sent yesterday`, sortable columns, paginated rows, and top-level ledger totals.

The extension checks the current job source URL against `/applications/lookup`. If the normalized URL is already in SQLite, the side panel shows an already-applied status and supported job pages show a small already-applied badge. Immediately after a supported platform confirms a submitted application, the page badge confirms `Submission recorded` for that submission instead of treating it as a prior application.

## PDF Cover Letters

PDF export is available for completed `cover_letter` drafts. The backend renders the saved `draft_text` without rewriting it, adds a restrained resume-derived letterhead, and saves the file under `JOB_APPLICATION_ASSISTANT_PDF_OUTPUT_DIR`.

Generated cover letter PDFs are named `Hanif-Carroll-Cover-Letter-{Company}.pdf`; the scraped role title remains available inside the letter context but is not included in the upload filename.

The default resume source is the iCloud Downloads resume path shown in Configuration. Reindexing extracts the resume text into draft context; PDF export reads only the resume header/contact lines needed for letterhead and skips phone-like contact items.

After an application is logged with an attached cover letter draft, the backend moves the already-generated PDF from `JOB_APPLICATION_ASSISTANT_PDF_OUTPUT_DIR` into `JOB_APPLICATION_ASSISTANT_PDF_ARCHIVE_DIR`. If no PDF was generated for that draft, application logging still succeeds and no archive file is created.

The draft side panel enables `Generate PDF` after a cover letter draft succeeds. PDF generation is started through the extension background service worker and persisted in `chrome.storage.local`, so closing the side panel does not own or clear the in-progress export state. After generation, `Finder` asks the local backend to reveal the generated PDF file. The backend only reveals files it generated under the configured PDF output directory.

On Dice application wizard pages, the extension can automatically generate the cover letter PDF and reports each in-progress or completed run in the side panel. Completed runs expose `Open PDF`, `Finder`, and regenerate actions from the side panel. After generation, the assistant attaches the PDF to Dice's cover-letter upload input. After Dice shows the attached PDF in the cover-letter card, the assistant clicks `Next`, clicks `Submit` on the review step, records the confirmed application, and closes the submitted Dice tab. Indeed Smart Apply automation generates and attaches a cover-letter PDF when the review step offers a supporting-document upload, then submits after the attachment is visible. LinkedIn Easy Apply automation records the confirmed application after LinkedIn shows an applied state.

## Privacy And Data Retention

This is a local-first tool, but it does store sensitive working data.

Stored locally:

- Chrome extension state in `chrome.storage.local`: current request, job id, progress, draft text, and audit text.
- Chrome extension queued application logs in `chrome.storage.local` when the backend is unavailable.
- SQLite data in `.runtime/drafts.db`: job details, user notes, draft text, audit trail, and applied-job ledger.
- Generated cover letter PDFs in `.runtime/cover-letters/` by default.
- Archived submitted cover letter PDFs in `.runtime/cover-letters/archive/` by default.
- Codex run workspaces in `.runtime/codex-runs/`: final JSON messages from individual Codex runs.
- Generated context in `data/context/`: profile, offers, and project proof points derived from your configured context source.

Not intentionally stored or sent:

- Outside Dice, Indeed, and LinkedIn apply automation, the extension does not submit applications or proposals.
- The backend does not call job-board APIs.
- The project does not include analytics.

Important data note:

- Drafting uses `codex exec`. Job/application inputs are sent through whatever Codex/OpenAI account and runtime you have configured locally.

To wipe local data:

```bash
rm -rf .runtime data/context
```

To clear extension state, open the extension's options/details in Chrome and clear extension site data, or remove and reload the unpacked extension.

Before publishing your fork, make sure `.runtime/`, `data/context/`, `.env`, and any personal context source directories are not committed.

## Development

Run checks:

```bash
scripts/check
```

## License

MIT
