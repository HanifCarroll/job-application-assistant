from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORTFOLIO_ROOT = REPO_ROOT / "examples" / "portfolio"


def env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default.expanduser()


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    return int(value)


def default_resume_pdf_path() -> Path:
    return Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "Downloads" / "Hanif-Carroll-Resume.pdf"


@dataclass(frozen=True)
class AppPaths:
    repo_root: Path = REPO_ROOT
    portfolio_root: Path = env_path("JOB_APPLICATION_ASSISTANT_PORTFOLIO_ROOT", DEFAULT_PORTFOLIO_ROOT)
    context_dir: Path = env_path("JOB_APPLICATION_ASSISTANT_CONTEXT_DIR", REPO_ROOT / "data" / "context")
    runtime_dir: Path = env_path("JOB_APPLICATION_ASSISTANT_RUNTIME_DIR", REPO_ROOT / ".runtime")
    pdf_output_dir: Path = env_path("JOB_APPLICATION_ASSISTANT_PDF_OUTPUT_DIR", REPO_ROOT / ".runtime" / "cover-letters")
    pdf_archive_dir: Path = env_path("JOB_APPLICATION_ASSISTANT_PDF_ARCHIVE_DIR", REPO_ROOT / ".runtime" / "cover-letters" / "archive")
    resume_pdf_path: Path = env_path("JOB_APPLICATION_ASSISTANT_RESUME_PDF_PATH", default_resume_pdf_path())
    db_path: Path = env_path("JOB_APPLICATION_ASSISTANT_DB_PATH", REPO_ROOT / ".runtime" / "drafts.db")
    codex_runs_dir: Path = env_path("JOB_APPLICATION_ASSISTANT_CODEX_RUNS_DIR", REPO_ROOT / ".runtime" / "codex-runs")
    codex_binary: str = os.environ.get("JOB_APPLICATION_ASSISTANT_CODEX_BINARY", "codex")
    codex_model: str = os.environ.get("JOB_APPLICATION_ASSISTANT_CODEX_MODEL", "gpt-5.5")
    codex_reasoning_effort: str = os.environ.get("JOB_APPLICATION_ASSISTANT_CODEX_REASONING_EFFORT", "low")
    codex_timeout_seconds: int = env_int("JOB_APPLICATION_ASSISTANT_CODEX_TIMEOUT_SECONDS", 180)
    max_workers: int = env_int("JOB_APPLICATION_ASSISTANT_MAX_WORKERS", 5)
    draft_schema_path: Path = REPO_ROOT / "schemas" / "draft_response.schema.json"

    def ensure_runtime(self) -> None:
        self.context_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_output_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_archive_dir.mkdir(parents=True, exist_ok=True)
        self.codex_runs_dir.mkdir(parents=True, exist_ok=True)
