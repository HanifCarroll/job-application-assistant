from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime, time
from pathlib import Path
from urllib.parse import urlsplit

from job_application_assistant.applications.store import ApplicationStore
from job_application_assistant.models import ApplicationLogRequest, ApplicationRecord, OpportunitySnapshot


CSV_COLUMNS = {"Role", "Company", "Link", "Date Sent"}


@dataclass(frozen=True)
class ApplicationImportResult:
    row_count: int
    application_count: int
    records: list[ApplicationRecord]


def import_applications_csv(path: Path, store: ApplicationStore) -> ApplicationImportResult:
    requests = list(read_application_csv(path))
    records = [store.log(request) for request in requests]
    return ApplicationImportResult(
        row_count=len(requests),
        application_count=len({record.id for record in records}),
        records=records,
    )


def read_application_csv(path: Path) -> list[ApplicationLogRequest]:
    delimiter = csv_delimiter(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty")
        missing = CSV_COLUMNS.difference(reader.fieldnames)
        if missing:
            columns = ", ".join(sorted(missing))
            raise ValueError(f"CSV is missing required columns: {columns}")
        rows = []
        for row_number, row in enumerate(reader, start=2):
            rows.append(application_request_from_row(row, row_number))
        return rows


def application_request_from_row(row: dict[str, str], row_number: int) -> ApplicationLogRequest:
    role = (row.get("Role") or "").strip()
    company = (row.get("Company") or "").strip()
    link = (row.get("Link") or "").strip()
    sent = (row.get("Date Sent") or "").strip()
    warnings = []
    if not sent:
        warnings.append("Date Sent was missing in the CSV row.")
    return ApplicationLogRequest(
        opportunity=OpportunitySnapshot(
            source=source_from_url(link),
            source_url=link,
            title=role,
            company=company,
        ),
        applied_at=parse_csv_date(sent, row_number) if sent else "",
        detected_by="csv_import",
        warnings=warnings,
    )


def parse_csv_date(value: str, row_number: int) -> str:
    for date_format in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, date_format).date()
        except ValueError:
            continue
        return datetime.combine(parsed, time.min, tzinfo=UTC).isoformat()
    raise ValueError(f"Row {row_number} has an unsupported Date Sent value: {value}")


def source_from_url(value: str) -> str:
    raw = value.strip()
    if not raw:
        return "csv"
    try:
        host = urlsplit(raw).netloc.lower()
    except ValueError:
        return "csv"
    if not host:
        return "csv"
    if "linkedin.com" in host:
        return "linkedin"
    for source in ("upwork", "dice", "indeed", "ziprecruiter", "roberthalf"):
        if source in host.replace("-", ""):
            return source
    return host.removeprefix("www.").split(".", 1)[0] or "csv"


def csv_delimiter(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        first_line = handle.readline()
    return ";" if first_line.count(";") > first_line.count(",") else ","
