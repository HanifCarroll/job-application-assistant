from __future__ import annotations

import csv
from pathlib import Path
import sys

import typer
import uvicorn

from job_application_assistant.applications.importer import import_applications_csv
from job_application_assistant.applications.store import ApplicationStore
from job_application_assistant.config import DEFAULT_PORTFOLIO_ROOT, AppPaths
from job_application_assistant.context.indexer import build_context
from job_application_assistant.models import ApplicationRecord


app = typer.Typer(help="Local job application assistant.")
applications_app = typer.Typer(help="Import, list, and export logged applications.")
app.add_typer(applications_app, name="applications")


@app.command()
def reindex(
    portfolio_root: Path = typer.Option(
        DEFAULT_PORTFOLIO_ROOT,
        help="Portfolio or context directory used as the source.",
    ),
) -> None:
    paths = AppPaths(portfolio_root=portfolio_root)
    bundle = build_context(paths.portfolio_root, paths.context_dir, paths.resume_pdf_path)
    typer.echo(f"Indexed {len(bundle.projects)} projects into {paths.context_dir}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    uvicorn.run("job_application_assistant.api:create_app", factory=True, host=host, port=port)


@applications_app.command("import")
def import_applications(path: Path) -> None:
    store = _application_store()
    result = import_applications_csv(path, store)
    typer.echo(f"Imported {result.row_count} CSV rows into {result.application_count} applications.")


@applications_app.command("list")
def list_applications(
    limit: int = typer.Option(25, min=1, help="Maximum number of applications to print."),
    source: str | None = typer.Option(None, help="Only print applications from one source."),
) -> None:
    store = _application_store()
    for record in store.list(limit=limit, source=source):
        typer.echo(_application_line(record))


@applications_app.command("export")
def export_applications(output: Path | None = typer.Option(None, "--output", "-o")) -> None:
    store = _application_store()
    records = store.list(limit=0)
    fieldnames = ["Role", "Company", "Link", "Date Sent", "Source", "Draft ID", "Draft Job ID"]
    if output is None:
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(_application_export_row(record))
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(_application_export_row(record))
    typer.echo(f"Exported {len(records)} applications to {output}")


def _application_store() -> ApplicationStore:
    paths = AppPaths()
    store = ApplicationStore(paths.db_path)
    store.init()
    return store


def _application_line(record: ApplicationRecord) -> str:
    return "\t".join([record.applied_at, record.source, record.title, record.company, record.source_url])


def _application_export_row(record: ApplicationRecord) -> dict[str, str]:
    return {
        "Role": record.title,
        "Company": record.company,
        "Link": record.source_url,
        "Date Sent": record.applied_at,
        "Source": record.source,
        "Draft ID": record.draft_id,
        "Draft Job ID": record.draft_job_id,
    }


if __name__ == "__main__":
    app()
