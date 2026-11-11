from __future__ import annotations

from datetime import date

from job_application_assistant.applications.dashboard import (
    count_sent_in_past_days,
    filter_application_records,
    paginate_application_records,
    render_application_dashboard,
    sort_application_records,
)
from job_application_assistant.models import ApplicationDetectedBy, ApplicationRecord, OpportunitySnapshot


def test_filter_application_records_searches_core_fields() -> None:
    dice = application_record(source="dice", title="Software Engineer", company="SkyBridge Resources", location="Remote")
    indeed = application_record(source="indeed", title="Backend Developer", company="Acme", location="New York")

    assert filter_application_records([dice, indeed], query="skybridge") == [dice]
    assert filter_application_records([dice, indeed], source="indeed") == [indeed]
    assert filter_application_records([dice, indeed], query="remote") == []


def test_filter_application_records_can_show_only_sent_today() -> None:
    today = application_record(source="dice", title="Today Role", company="Acme", applied_at="2026-06-20T12:00:00+00:00")
    yesterday = application_record(
        source="indeed",
        title="Yesterday Role",
        company="Globex",
        applied_at="2026-06-19T12:00:00+00:00",
    )

    assert filter_application_records([today, yesterday], sent="today", today=date(2026, 6, 20)) == [today]


def test_filter_application_records_can_show_only_sent_yesterday() -> None:
    today = application_record(source="dice", title="Today Role", company="Acme", applied_at="2026-06-20T12:00:00+00:00")
    yesterday = application_record(
        source="indeed",
        title="Yesterday Role",
        company="Globex",
        applied_at="2026-06-19T12:00:00+00:00",
    )

    assert filter_application_records([today, yesterday], sent="yesterday", today=date(2026, 6, 20)) == [yesterday]


def test_count_sent_in_past_days_uses_inclusive_local_date_window() -> None:
    today = application_record(source="dice", title="Today Role", company="Acme", applied_at="2026-06-20T12:00:00+00:00")
    recent = application_record(
        source="indeed",
        title="Recent Role",
        company="Globex",
        applied_at="2026-06-18T12:00:00+00:00",
    )
    old = application_record(
        source="linkedin",
        title="Old Role",
        company="Umbrella",
        applied_at="2026-06-17T12:00:00+00:00",
    )

    assert count_sent_in_past_days([today, recent, old], days=3, today=date(2026, 6, 20)) == 2


def test_sort_application_records_sorts_before_display_limit() -> None:
    dice = application_record(source="dice", title="Software Engineer", company="SkyBridge Resources", location="Remote")
    indeed = application_record(source="indeed", title="Backend Developer", company="Acme", location="New York")

    assert sort_application_records([dice, indeed], sort="company", direction="asc") == [indeed, dice]
    assert sort_application_records([dice, indeed], sort="role", direction="desc") == [dice, indeed]


def test_paginate_application_records_slices_after_filtering_and_sorting() -> None:
    records = [
        application_record(source=f"source-{index}", title=f"Role {index}", company="Acme")
        for index in range(5)
    ]

    page = paginate_application_records(records, page=2, page_size=2)

    assert page.records == records[2:4]
    assert page.page == 2
    assert page.total_records == 5
    assert page.total_pages == 3
    assert page.start_index == 3
    assert page.end_index == 4


def test_render_application_dashboard_escapes_application_fields() -> None:
    record = application_record(
        source="dice",
        title="<script>alert(1)</script>",
        company="Acme & Sons",
        location="Remote",
    )

    html = render_application_dashboard(records=[record], all_records=[record], query="<script>", source="dice", limit=50)

    assert "Application Ledger" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Acme &amp; Sons" in html
    assert '<script>alert(1)</script>' not in html
    assert "/applications?limit=50&amp;source=dice" in html
    assert "Detected By" not in html
    assert "Location" not in html
    assert "Remote" not in html
    assert "sort=company" in html


def test_render_application_dashboard_shows_today_filter_pagination_and_totals() -> None:
    today = application_record(source="dice", title="Today Role", company="Acme", applied_at="2026-06-20T12:00:00+00:00")
    yesterday = application_record(
        source="indeed",
        title="Yesterday Role",
        company="Globex",
        applied_at="2026-06-19T12:00:00+00:00",
    )

    html = render_application_dashboard(
        records=[today],
        all_records=[today, yesterday],
        query="role",
        source="dice",
        sent="today",
        limit=1,
        page=2,
        total_pages=3,
        filtered_total=3,
        today_total=1,
    )

    assert '<option value="today" selected>Sent today</option>' in html
    assert '<option value="yesterday">Sent yesterday</option>' in html
    assert "Sent today" in html
    assert "Matching filters" in html
    assert "This page" in html
    assert "Showing 2-2 of 3 applications" in html
    assert "Page 2 of 3" in html
    assert "Previous" in html
    assert "Next" in html
    assert "page=3" in html
    assert "q=role" in html
    assert "source=dice" in html
    assert "sent=today" in html


def test_render_application_dashboard_shows_yesterday_filter_selection() -> None:
    record = application_record(
        source="indeed",
        title="Yesterday Role",
        company="Globex",
        applied_at="2026-06-19T12:00:00+00:00",
    )

    html = render_application_dashboard(
        records=[record],
        all_records=[record],
        query="role",
        sent="yesterday",
        limit=50,
    )

    assert '<option value="yesterday" selected>Sent yesterday</option>' in html
    assert "sent=yesterday" in html


def test_render_application_dashboard_hides_imported_application_time() -> None:
    record = application_record(
        source="linkedin",
        title="Imported Role",
        company="Acme",
        location="Remote",
        detected_by="csv_import",
    )

    html = render_application_dashboard(records=[record], all_records=[record], limit=50)

    assert "2026-06-19" in html
    assert "2026-06-19 12:00" not in html


def test_render_application_dashboard_links_draft_by_source_url_fallback() -> None:
    record = application_record(
        source="dice",
        title="Software Engineer",
        company="Sonitalent LLC",
        location="Remote",
    )

    html = render_application_dashboard(
        records=[record],
        all_records=[record],
        draft_ids_by_source_url={record.normalized_source_url: "draft-123"},
    )

    assert 'href="/drafts/draft-123"' in html
    assert "No draft" not in html


def application_record(
    *,
    source: str,
    title: str,
    company: str,
    location: str = "",
    applied_at: str = "2026-06-19T12:00:00+00:00",
    detected_by: ApplicationDetectedBy = "manual",
) -> ApplicationRecord:
    opportunity = OpportunitySnapshot(
        source=source,
        source_url=f"https://example.com/{source}/{title.replace(' ', '-').lower()}",
        title=title,
        company=company,
        location=location,
    )
    return ApplicationRecord(
        id=f"{source}-1",
        status="applied",
        applied_at=applied_at,
        source=source,
        source_url=opportunity.source_url,
        normalized_source_url=opportunity.source_url,
        title=title,
        company=company,
        location=location,
        draft_id="",
        draft_job_id="",
        opportunity=opportunity,
        detected_by=detected_by,
        warnings=[],
        created_at=applied_at,
        updated_at=applied_at,
    )
