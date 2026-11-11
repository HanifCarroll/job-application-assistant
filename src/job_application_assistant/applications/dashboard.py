from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import escape
from typing import Sequence
from urllib.parse import urlencode

from job_application_assistant.models import ApplicationRecord


@dataclass(frozen=True)
class ApplicationPage:
    records: list[ApplicationRecord]
    page: int
    page_size: int
    total_records: int
    total_pages: int
    start_index: int
    end_index: int


def filter_application_records(
    records: Sequence[ApplicationRecord],
    *,
    query: str = "",
    source: str = "",
    sent: str = "",
    today: date | None = None,
) -> list[ApplicationRecord]:
    filtered = [record for record in records if not source or record.source == source]
    if sent in {"today", "yesterday"}:
        target_date = _sent_filter_date(sent, today=today)
        filtered = [record for record in filtered if _applied_local_date(record.applied_at) == target_date]
    normalized_query = query.strip().lower()
    if not normalized_query:
        return filtered
    return [record for record in filtered if normalized_query in _search_blob(record)]


def sort_application_records(
    records: Sequence[ApplicationRecord],
    *,
    sort: str = "applied",
    direction: str = "desc",
) -> list[ApplicationRecord]:
    sort_key = sort if sort in {"applied", "source", "role", "company"} else "applied"
    reverse = direction != "asc"
    sorted_records = sorted(records, key=lambda record: _sort_value(record, sort_key), reverse=reverse)
    return sorted(sorted_records, key=lambda record: _sort_value(record, sort_key) == "")


def count_sent_today(records: Sequence[ApplicationRecord], *, today: date | None = None) -> int:
    return count_sent_in_past_days(records, days=1, today=today)


def count_sent_in_past_days(records: Sequence[ApplicationRecord], *, days: int, today: date | None = None) -> int:
    safe_days = max(days, 1)
    end_date = today or _local_today()
    start_date = end_date - timedelta(days=safe_days - 1)
    return sum(
        1
        for record in records
        if (applied_date := _applied_local_date(record.applied_at)) is not None
        and start_date <= applied_date <= end_date
    )


def paginate_application_records(
    records: Sequence[ApplicationRecord],
    *,
    page: int = 1,
    page_size: int = 500,
) -> ApplicationPage:
    safe_page_size = max(page_size, 1)
    total_records = len(records)
    total_pages = max(1, (total_records + safe_page_size - 1) // safe_page_size)
    safe_page = min(max(page, 1), total_pages)
    start_offset = (safe_page - 1) * safe_page_size
    page_records = list(records[start_offset : start_offset + safe_page_size])
    start_index = start_offset + 1 if page_records else 0
    end_index = start_offset + len(page_records) if page_records else 0
    return ApplicationPage(
        records=page_records,
        page=safe_page,
        page_size=safe_page_size,
        total_records=total_records,
        total_pages=total_pages,
        start_index=start_index,
        end_index=end_index,
    )


def render_application_dashboard(
    *,
    records: Sequence[ApplicationRecord],
    all_records: Sequence[ApplicationRecord],
    query: str = "",
    source: str = "",
    sent: str = "",
    limit: int = 500,
    page: int = 1,
    total_pages: int = 1,
    filtered_total: int | None = None,
    today_total: int | None = None,
    sort: str = "applied",
    direction: str = "desc",
    draft_ids_by_source_url: Mapping[str, str] | None = None,
) -> str:
    sort, direction = _sort_state(sort, direction)
    sent = _sent_state(sent)
    limit = max(limit, 1)
    filtered_count = len(records) if filtered_total is None else filtered_total
    today_count = today_total if today_total is not None else count_sent_today(all_records)
    page = min(max(page, 1), max(total_pages, 1))
    total_pages = max(total_pages, 1)
    draft_links = draft_ids_by_source_url or {}
    sources = sorted({record.source for record in all_records if record.source})
    latest = max((record.applied_at for record in all_records), default="")
    source_options = ['<option value="">All sources</option>']
    for item in sources:
        selected = " selected" if item == source else ""
        source_options.append(f'<option value="{_h(item)}"{selected}>{_h(item)}</option>')

    page_summary = _page_summary(page=page, page_size=limit, visible_count=len(records), total_records=filtered_count)
    pagination = _pagination_controls(
        page=page,
        total_pages=total_pages,
        query=query,
        source=source,
        sent=sent,
        limit=limit,
        sort=sort,
        direction=direction,
    )
    rows = "\n".join(_application_row(record, draft_ids_by_source_url=draft_links) for record in records)
    if not rows:
        rows = """
        <tr>
          <td colspan="5" class="empty">No applications match the current filters.</td>
        </tr>
        """

    json_url = "/applications?" + urlencode({"limit": limit, **({"source": source} if source else {})})

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Application Ledger</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f6f7f4;
        --surface: #ffffff;
        --text: #17201c;
        --muted: #5f6c65;
        --border: #d8ded8;
        --accent: #1f6f55;
        --accent-weak: #e5f1ec;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      main {{
        width: min(1180px, calc(100% - 32px));
        margin: 0 auto;
        padding: 28px 0 40px;
      }}
      header {{
        display: flex;
        gap: 18px;
        align-items: end;
        justify-content: space-between;
        margin-bottom: 20px;
      }}
      h1 {{
        margin: 0 0 5px;
        font-size: 28px;
        line-height: 1.15;
        letter-spacing: 0;
      }}
      p {{ margin: 0; color: var(--muted); }}
      .actions {{ display: flex; gap: 10px; align-items: center; }}
      a.button,
      button {{
        border: 1px solid var(--border);
        border-radius: 7px;
        padding: 9px 12px;
        background: var(--surface);
        color: var(--text);
        font: inherit;
        font-size: 13px;
        font-weight: 700;
        text-decoration: none;
        cursor: pointer;
      }}
      button.primary {{
        border-color: var(--accent);
        background: var(--accent);
        color: #fff;
      }}
      .summary {{
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 10px;
        margin-bottom: 14px;
      }}
      .metric {{
        border: 1px solid var(--border);
        border-radius: 8px;
        background: var(--surface);
        padding: 13px 14px;
      }}
      .metric strong {{
        display: block;
        font-size: 23px;
        line-height: 1.1;
      }}
      .metric span {{
        color: var(--muted);
        font-size: 12px;
        font-weight: 650;
      }}
      form {{
        display: grid;
        grid-template-columns: 1fr 190px 150px 125px auto auto;
        gap: 8px;
        align-items: center;
        margin-bottom: 14px;
      }}
      input,
      select {{
        width: 100%;
        border: 1px solid var(--border);
        border-radius: 7px;
        padding: 9px 10px;
        background: var(--surface);
        color: var(--text);
        font: inherit;
        font-size: 13px;
      }}
      .table-wrap {{
        overflow: auto;
        border: 1px solid var(--border);
        border-radius: 8px;
        background: var(--surface);
      }}
      .table-bar,
      .table-footer {{
        display: flex;
        gap: 10px;
        align-items: center;
        justify-content: space-between;
        padding: 10px 12px;
        color: var(--muted);
        font-size: 13px;
      }}
      .table-bar {{
        border-bottom: 1px solid var(--border);
      }}
      .table-footer {{
        border-top: 1px solid var(--border);
      }}
      .pagination {{
        display: flex;
        gap: 8px;
        align-items: center;
      }}
      .page-button {{
        border: 1px solid var(--border);
        border-radius: 7px;
        padding: 6px 9px;
        background: var(--surface);
        color: var(--text);
        font-size: 12px;
        font-weight: 700;
        text-decoration: none;
      }}
      .page-button.disabled {{
        color: var(--muted);
        opacity: 0.55;
      }}
      .page-count {{
        color: var(--text);
        font-weight: 700;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        min-width: 780px;
      }}
      th,
      td {{
        padding: 10px 12px;
        border-bottom: 1px solid var(--border);
        text-align: left;
        vertical-align: top;
        font-size: 13px;
      }}
      th {{
        position: sticky;
        top: 0;
        background: #eef2ee;
        color: var(--muted);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }}
      .sort-link {{
        display: inline-flex;
        gap: 6px;
        align-items: center;
        color: inherit;
        text-decoration: none;
      }}
      .sort-state {{
        color: var(--accent);
        font-size: 10px;
        letter-spacing: 0;
        text-transform: none;
      }}
      tr:last-child td {{ border-bottom: 0; }}
      .role strong {{ display: block; }}
      .source {{
        display: inline-flex;
        border-radius: 999px;
        padding: 3px 8px;
        background: var(--accent-weak);
        color: var(--accent);
        font-size: 12px;
        font-weight: 750;
      }}
      .muted {{ color: var(--muted); }}
      .empty {{
        padding: 26px 12px;
        color: var(--muted);
        text-align: center;
      }}
      td a {{
        color: var(--accent);
        font-weight: 700;
        text-decoration: none;
      }}
      td a:hover {{ text-decoration: underline; }}
      @media (max-width: 760px) {{
        main {{ width: min(100% - 20px, 1180px); padding-top: 18px; }}
        header {{ align-items: start; flex-direction: column; }}
        .summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        form {{ grid-template-columns: 1fr; }}
        .table-bar,
        .table-footer {{
          align-items: start;
          flex-direction: column;
        }}
        .actions {{ width: 100%; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <div>
          <h1>Application Ledger</h1>
          <p>SQLite-backed history of submitted applications.</p>
        </div>
        <div class="actions">
          <a class="button" href="{_h(json_url)}">JSON</a>
          <a class="button" href="/docs">API Docs</a>
        </div>
      </header>

      <section class="summary" aria-label="Ledger summary">
        <div class="metric"><strong>{len(all_records)}</strong><span>Total logged</span></div>
        <div class="metric"><strong>{today_count}</strong><span>Sent today</span></div>
        <div class="metric"><strong>{filtered_count}</strong><span>Matching filters</span></div>
        <div class="metric"><strong>{len(records)}</strong><span>This page</span></div>
        <div class="metric"><strong>{len(sources)}</strong><span>Sources</span></div>
        <div class="metric"><strong>{_h(_short_date(latest) or "-")}</strong><span>Latest applied</span></div>
      </section>

      <form method="get" action="/dashboard">
        <input name="q" value="{_h(query)}" placeholder="Search role, company, source, or URL" autocomplete="off" />
        <select name="source">
          {"".join(source_options)}
        </select>
        <select name="sent">
          {_sent_options(sent)}
        </select>
        <select name="limit">
          {_limit_options(limit)}
        </select>
        <input type="hidden" name="sort" value="{_h(sort)}" />
        <input type="hidden" name="direction" value="{_h(direction)}" />
        <button class="primary" type="submit">Filter</button>
        <a class="button" href="/dashboard">Reset</a>
      </form>

      <div class="table-wrap">
        <div class="table-bar">
          <span>{_h(page_summary)}</span>
          {pagination}
        </div>
        <table>
          <thead>
            <tr>
              <th>{_sort_header("Applied", "applied", sort=sort, direction=direction, query=query, source=source, sent=sent, limit=limit)}</th>
              <th>{_sort_header("Source", "source", sort=sort, direction=direction, query=query, source=source, sent=sent, limit=limit)}</th>
              <th>{_sort_header("Role", "role", sort=sort, direction=direction, query=query, source=source, sent=sent, limit=limit)}</th>
              <th>{_sort_header("Company", "company", sort=sort, direction=direction, query=query, source=source, sent=sent, limit=limit)}</th>
              <th>Links</th>
            </tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>
        <div class="table-footer">
          <span>{_h(page_summary)}</span>
          {pagination}
        </div>
      </div>
    </main>
  </body>
</html>
"""


def _application_row(record: ApplicationRecord, *, draft_ids_by_source_url: Mapping[str, str]) -> str:
    role = _h(record.title or "Untitled role")
    company = _h(record.company or "-")
    source_url = _h(record.source_url)
    draft_id = record.draft_id or draft_ids_by_source_url.get(record.normalized_source_url, "")
    draft_link = f'<a href="/drafts/{_h(draft_id)}">Draft</a>' if draft_id else '<span class="muted">No draft</span>'
    job_link = f'<a href="{source_url}" target="_blank" rel="noreferrer">Job</a>' if record.source_url else '<span class="muted">No URL</span>'
    return f"""
        <tr>
          <td>{_h(_display_applied_at(record))}</td>
          <td><span class="source">{_h(record.source or "unknown")}</span></td>
          <td class="role"><strong>{role}</strong><span class="muted">{source_url}</span></td>
          <td>{company}</td>
          <td>{job_link} · {draft_link}</td>
        </tr>
    """


def _search_blob(record: ApplicationRecord) -> str:
    return " ".join(
        [
            record.title,
            record.company,
            record.source,
            record.source_url,
        ]
    ).lower()


def _sort_value(record: ApplicationRecord, sort: str) -> str:
    if sort == "source":
        return record.source.lower()
    if sort == "role":
        return record.title.lower()
    if sort == "company":
        return record.company.lower()
    return record.applied_at


def _sort_state(sort: str, direction: str) -> tuple[str, str]:
    safe_sort = sort if sort in {"applied", "source", "role", "company"} else "applied"
    safe_direction = "asc" if direction == "asc" else "desc"
    return safe_sort, safe_direction


def _sent_state(sent: str) -> str:
    return sent if sent in {"today", "yesterday"} else ""


def _sort_header(
    label: str,
    key: str,
    *,
    sort: str,
    direction: str,
    query: str,
    source: str,
    sent: str,
    limit: int,
) -> str:
    is_active = sort == key
    next_direction = "asc" if not is_active or direction == "desc" else "desc"
    params = _dashboard_params(
        query=query,
        source=source,
        sent=sent,
        limit=limit,
        sort=key,
        direction=next_direction,
        page=1,
    )
    state = f'<span class="sort-state">{_h(direction)}</span>' if is_active else ""
    return f'<a class="sort-link" href="/dashboard?{_h(urlencode(params))}">{_h(label)}{state}</a>'


def _pagination_controls(
    *,
    page: int,
    total_pages: int,
    query: str,
    source: str,
    sent: str,
    limit: int,
    sort: str,
    direction: str,
) -> str:
    prev_item = _page_button(
        "Previous",
        page - 1,
        disabled=page <= 1,
        query=query,
        source=source,
        sent=sent,
        limit=limit,
        sort=sort,
        direction=direction,
    )
    next_item = _page_button(
        "Next",
        page + 1,
        disabled=page >= total_pages,
        query=query,
        source=source,
        sent=sent,
        limit=limit,
        sort=sort,
        direction=direction,
    )
    return f"""
          <nav class="pagination" aria-label="Application table pagination">
            {prev_item}
            <span class="page-count">Page {page} of {total_pages}</span>
            {next_item}
          </nav>
    """


def _page_button(
    label: str,
    page: int,
    *,
    disabled: bool,
    query: str,
    source: str,
    sent: str,
    limit: int,
    sort: str,
    direction: str,
) -> str:
    if disabled:
        return f'<span class="page-button disabled" aria-disabled="true">{_h(label)}</span>'
    params = _dashboard_params(
        query=query,
        source=source,
        sent=sent,
        limit=limit,
        sort=sort,
        direction=direction,
        page=page,
    )
    return f'<a class="page-button" href="/dashboard?{_h(urlencode(params))}">{_h(label)}</a>'


def _dashboard_params(
    *,
    query: str,
    source: str,
    sent: str,
    limit: int,
    sort: str,
    direction: str,
    page: int,
) -> dict[str, object]:
    params: dict[str, object] = {
        "limit": limit,
        "sort": sort,
        "direction": direction,
    }
    if page > 1:
        params["page"] = page
    if query:
        params["q"] = query
    if source:
        params["source"] = source
    if sent:
        params["sent"] = sent
    return params


def _page_summary(*, page: int, page_size: int, visible_count: int, total_records: int) -> str:
    if total_records == 0 or visible_count == 0:
        return "Showing 0 applications"
    start_index = ((page - 1) * page_size) + 1
    end_index = start_index + visible_count - 1
    return f"Showing {start_index}-{end_index} of {total_records} applications"


def _display_applied_at(record: ApplicationRecord) -> str:
    if record.detected_by == "csv_import":
        return _short_date(record.applied_at)
    return _display_datetime(record.applied_at)


def _display_datetime(value: str) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return value
    return parsed.strftime("%Y-%m-%d %H:%M")


def _short_date(value: str) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return value[:10]
    return parsed.strftime("%Y-%m-%d")


def _applied_local_date(value: str) -> date | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        return parsed.date()
    return parsed.astimezone().date()


def _local_today() -> date:
    return datetime.now().astimezone().date()


def _sent_filter_date(sent: str, *, today: date | None = None) -> date:
    target_date = today or _local_today()
    if sent == "yesterday":
        return target_date - timedelta(days=1)
    return target_date


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _limit_options(selected_limit: int) -> str:
    options = []
    for value in [50, 100, 250, 500, 1000]:
        selected = " selected" if selected_limit == value else ""
        options.append(f'<option value="{value}"{selected}>{value} rows</option>')
    return "".join(options)


def _sent_options(selected_sent: str) -> str:
    today_selected = " selected" if selected_sent == "today" else ""
    yesterday_selected = " selected" if selected_sent == "yesterday" else ""
    return (
        f'<option value="">All dates</option>'
        f'<option value="today"{today_selected}>Sent today</option>'
        f'<option value="yesterday"{yesterday_selected}>Sent yesterday</option>'
    )


def _h(value: object) -> str:
    return escape(str(value), quote=True)
