from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import re
import subprocess
from time import perf_counter
from uuid import uuid4

from job_application_assistant.config import AppPaths
from job_application_assistant.models import CodexRunTiming


class CodexProviderError(RuntimeError):
    pass


class CodexProvider:
    def __init__(self, paths: AppPaths, timeout_seconds: int | None = None) -> None:
        self.paths = paths
        self.timeout_seconds = timeout_seconds or paths.codex_timeout_seconds

    def generate(
        self,
        prompt: str,
        phase: str = "unknown",
        on_timing: Callable[[CodexRunTiming], None] | None = None,
        schema_path: Path | None = None,
    ) -> dict[str, object]:
        self.paths.ensure_runtime()
        run_dir = self._prepare_run_workspace()
        output_path = run_dir / "last-message.json"
        cmd = [
            self.paths.codex_binary,
            "--ask-for-approval",
            "never",
            "exec",
            "-",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "-m",
            self.paths.codex_model,
            "-c",
            f'model_reasoning_effort="{self.paths.codex_reasoning_effort}"',
            "--color",
            "never",
            "-C",
            str(run_dir),
            "--output-schema",
            str(schema_path or self.paths.draft_schema_path),
            "--output-last-message",
            str(output_path),
        ]
        started_at = _utc_now_iso()
        started = perf_counter()
        return_code: int | None = None
        timed_out = False
        stdout_bytes = 0
        stderr_bytes = 0
        output_bytes: int | None = None
        parse_duration_ms: int | None = None
        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            return_code = result.returncode
            stdout_bytes = _byte_len(result.stdout)
            stderr_bytes = _byte_len(result.stderr)
            if result.returncode != 0:
                raise CodexProviderError(_safe_process_error(result.stdout, result.stderr, result.returncode))
            if not output_path.exists():
                raise CodexProviderError("codex exec did not write an output message")
            raw = output_path.read_text(encoding="utf-8")
            output_bytes = _byte_len(raw)
            parse_started = perf_counter()
            parsed = _parse_json_message(raw)
            parse_duration_ms = _elapsed_ms(parse_started)
            return parsed
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout_bytes = _byte_len(exc.stdout)
            stderr_bytes = _byte_len(exc.stderr)
            raise CodexProviderError(f"codex exec timed out after {self.timeout_seconds} seconds") from exc
        finally:
            timing = CodexRunTiming(
                phase=phase,
                started_at=started_at,
                finished_at=_utc_now_iso(),
                duration_ms=_elapsed_ms(started),
                return_code=return_code,
                timed_out=timed_out,
                prompt_chars=len(prompt),
                stdout_bytes=stdout_bytes,
                stderr_bytes=stderr_bytes,
                output_bytes=output_bytes,
                parse_duration_ms=parse_duration_ms,
            )
            if on_timing is not None:
                on_timing(timing)

    def _prepare_run_workspace(self) -> Path:
        run_dir = self.paths.codex_runs_dir / uuid4().hex
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir


def _parse_json_message(raw: str) -> dict[str, object]:
    text = raw.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CodexProviderError("codex output was not JSON") from exc
    if not isinstance(value, dict):
        raise CodexProviderError("codex output JSON was not an object")
    return value


def _safe_process_error(stdout: str, stderr: str, return_code: int) -> str:
    text = "\n".join([stderr, stdout])
    message_match = re.search(r'"message"\s*:\s*("(?:(?:\\.)|[^"\\])*")', text)
    if message_match is not None:
        try:
            message = json.loads(message_match.group(1))
            if isinstance(message, str) and message:
                return f"codex exec failed with exit code {return_code}: {message}"
        except json.JSONDecodeError:
            pass
    code_match = re.search(r'"code"\s*:\s*("(?:(?:\\.)|[^"\\])*")', text)
    if code_match is not None:
        try:
            code = json.loads(code_match.group(1))
            if isinstance(code, str) and code:
                return f"codex exec failed with exit code {return_code}: {code}"
        except json.JSONDecodeError:
            pass
    return f"codex exec failed with exit code {return_code}. See timing metadata for output sizes."


def _byte_len(value: str | bytes | None) -> int:
    if value is None:
        return 0
    if isinstance(value, bytes):
        return len(value)
    return len(value.encode("utf-8"))


def _elapsed_ms(started: float) -> int:
    return round((perf_counter() - started) * 1000)


def _utc_now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
