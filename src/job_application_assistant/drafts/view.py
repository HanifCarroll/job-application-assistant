from __future__ import annotations

from datetime import datetime
from html import escape

from job_application_assistant.models import DraftResponse


def render_draft_view(draft: DraftResponse) -> str:
    title = _title(draft)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{_h(title)}</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f6f7f4;
        --surface: #ffffff;
        --text: #17201c;
        --muted: #5f6c65;
        --border: #d8ded8;
        --accent: #1f6f55;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      main {{
        width: min(900px, calc(100% - 32px));
        margin: 0 auto;
        padding: 30px 0 44px;
      }}
      header {{
        display: flex;
        gap: 16px;
        justify-content: space-between;
        align-items: start;
        margin-bottom: 18px;
      }}
      h1 {{
        margin: 0 0 6px;
        font-size: 28px;
        line-height: 1.15;
        letter-spacing: 0;
      }}
      p {{ margin: 0; color: var(--muted); }}
      .actions {{ display: flex; gap: 8px; flex-wrap: wrap; justify-content: end; }}
      a.button {{
        border: 1px solid var(--border);
        border-radius: 7px;
        padding: 9px 12px;
        background: var(--surface);
        color: var(--text);
        font-size: 13px;
        font-weight: 700;
        text-decoration: none;
      }}
      a.primary {{
        border-color: var(--accent);
        background: var(--accent);
        color: #fff;
      }}
      section {{
        border: 1px solid var(--border);
        border-radius: 8px;
        background: var(--surface);
        padding: 18px;
        margin-bottom: 12px;
      }}
      h2 {{
        margin: 0 0 10px;
        font-size: 15px;
        line-height: 1.25;
        letter-spacing: 0;
      }}
      .draft-text {{
        white-space: pre-wrap;
        font-family: ui-serif, Georgia, "Times New Roman", serif;
        font-size: 16px;
        line-height: 1.55;
      }}
      .meta-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
      }}
      .meta-item strong {{
        display: block;
        color: var(--muted);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }}
      .meta-item span {{ display: block; margin-top: 3px; }}
      ul {{ margin: 0; padding-left: 20px; }}
      li + li {{ margin-top: 5px; }}
      @media (max-width: 720px) {{
        main {{ width: min(100% - 20px, 900px); padding-top: 20px; }}
        header {{ flex-direction: column; }}
        .actions {{ justify-content: start; }}
        .meta-grid {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <div>
          <h1>{_h(title)}</h1>
          <p>{_h(_created_date(draft.created_at))}</p>
        </div>
        <div class="actions">
          <a class="button primary" href="/drafts/{_h(draft.id)}/pdf">Open PDF</a>
          <a class="button" href="/drafts/{_h(draft.id)}?format=json">JSON</a>
          <a class="button" href="/dashboard">Ledger</a>
        </div>
      </header>

      <section>
        <h2>Draft</h2>
        <div class="draft-text">{_h(draft.draft_text)}</div>
      </section>

      <section>
        <h2>Strategy</h2>
        <div class="meta-grid">
          <div class="meta-item"><strong>Type</strong><span>{_h(draft.draft_type)}</span></div>
          <div class="meta-item"><strong>Subject</strong><span>{_h(draft.subject_line or "-")}</span></div>
          <div class="meta-item"><strong>Angle</strong><span>{_h(draft.selected_angle.label)}</span></div>
          <div class="meta-item"><strong>Role</strong><span>{_h(draft.role_classification)}</span></div>
        </div>
        <p style="margin-top: 12px;">{_h(draft.application_strategy)}</p>
      </section>

      <section>
        <h2>Selected Projects</h2>
        {_list_html(draft.selected_projects)}
      </section>

      <section>
        <h2>Warnings</h2>
        {_list_html(draft.warnings)}
      </section>
    </main>
  </body>
</html>
"""


def _title(draft: DraftResponse) -> str:
    return draft.subject_line or "Application Draft"


def _created_date(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return f"Created {parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def _list_html(items: list[str]) -> str:
    if not items:
        return '<p class="muted">None</p>'
    return "<ul>" + "".join(f"<li>{_h(item)}</li>" for item in items) + "</ul>"


def _h(value: object) -> str:
    return escape(str(value), quote=True)
