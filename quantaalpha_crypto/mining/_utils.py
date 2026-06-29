"""Shared internal helpers for the crypto mining module.

These were previously duplicated across mining modules. Keeping a single
implementation avoids drift, which is especially important for
``_redact_secrets`` (a secret-leak surface).
"""

from __future__ import annotations

import re
from typing import Any, Callable


def _progress(progress_callback: Callable[[str], None] | None, message: str) -> None:
    if progress_callback is not None:
        progress_callback(message)


def _redact_secrets(value: Any) -> Any:
    sensitive_key_pattern = re.compile(
        r"(api[_-]?key|secret|token|password|authorization)",
        re.IGNORECASE,
    )
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if sensitive_key_pattern.search(str(key))
                else _redact_secrets(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    if isinstance(value, str):
        return re.sub(
            r'(?i)("?(?:api[_-]?key|secret|token|password|authorization)"?\s*[:=]\s*)(".*?"|[^,\s}]+)',
            r"\1[REDACTED]",
            value,
        )
    return value
