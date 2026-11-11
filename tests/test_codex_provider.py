from __future__ import annotations

import pytest

from job_application_assistant.codex_provider import CodexProviderError, _parse_json_message, _safe_process_error


def test_safe_process_error_extracts_message_without_prompt_text() -> None:
    stderr = """
user
SECRET PROMPT CONTENT
ERROR: {
  "error": {
    "message": "Invalid schema for response_format",
    "code": "invalid_json_schema"
  }
}
"""

    message = _safe_process_error("", stderr, 1)

    assert message == "codex exec failed with exit code 1: Invalid schema for response_format"
    assert "SECRET PROMPT CONTENT" not in message


def test_safe_process_error_falls_back_without_process_output() -> None:
    message = _safe_process_error("plain stdout with prompt", "plain stderr with prompt", 2)

    assert message == "codex exec failed with exit code 2. See timing metadata for output sizes."
    assert "plain stdout" not in message
    assert "plain stderr" not in message


def test_parse_json_message_requires_exact_json_object() -> None:
    assert _parse_json_message('{"draft_text": "ok"}') == {"draft_text": "ok"}


def test_parse_json_message_rejects_wrapped_json() -> None:
    with pytest.raises(CodexProviderError, match="codex output was not JSON"):
        _parse_json_message('Here is the JSON:\n{"draft_text": "ok"}')
