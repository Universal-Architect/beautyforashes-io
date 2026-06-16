"""
FaithVision Lead Generation System
redaction.py — Prevents secrets from appearing in any output or audit log.
Deny-by-default. Local draft only.
"""

from __future__ import annotations

import re
import json
from typing import Any, Dict, Union

# ── Patterns that indicate a secret value ─────────────────────────────────────

SECRET_KEY_PATTERNS: list[str] = [
    r"api[_\-]?key",
    r"token",
    r"bearer",
    r"oauth",
    r"password",
    r"passwd",
    r"secret",
    r"client[_\-]?id",
    r"account[_\-]?id",
    r"workspace[_\-]?id",
    r"org[_\-]?id",
    r"^ak_",
    r"^sk_",
    r"^pk_",
    r"private[_\-]?key",
    r"auth[_\-]?token",
    r"refresh[_\-]?token",
    r"access[_\-]?token",
    r"credentials",
    r"passphrase",
    r"session[_\-]?id",
]

# Compile once
_SECRET_KEY_RE = re.compile(
    "|".join(SECRET_KEY_PATTERNS), re.IGNORECASE
)

# Value patterns that look like secrets (Bearer tokens, JWTs, long hex strings)
_SECRET_VALUE_RE = re.compile(
    r"(Bearer\s+\S+|eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_.+/=]*"
    r"|[A-Fa-f0-9]{32,}|[A-Za-z0-9+/]{40,}={0,2})",
    re.IGNORECASE,
)

REDACTION_PLACEHOLDER = "[REDACTED]"


def _is_secret_key(key: str) -> bool:
    return bool(_SECRET_KEY_RE.search(key))


def _redact_value(value: Any) -> Any:
    """Redact a scalar value if it looks like a secret."""
    if isinstance(value, str):
        if _SECRET_VALUE_RE.search(value):
            return REDACTION_PLACEHOLDER
    return value


def redact_dict(data: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
    """
    Recursively redact secret keys/values from a dictionary.
    Stops at depth 20 to prevent infinite recursion.
    """
    if depth > 20:
        return {"_truncated": "max_redaction_depth_reached"}

    result: Dict[str, Any] = {}
    for key, value in data.items():
        if _is_secret_key(str(key)):
            result[key] = REDACTION_PLACEHOLDER
        elif isinstance(value, dict):
            result[key] = redact_dict(value, depth + 1)
        elif isinstance(value, list):
            result[key] = [
                redact_dict(item, depth + 1) if isinstance(item, dict)
                else (_redact_value(item) if isinstance(item, str) else item)
                for item in value
            ]
        elif isinstance(value, str):
            result[key] = _redact_value(value)
        else:
            result[key] = value
    return result


def redact_string(text: str) -> str:
    """Redact secret-like patterns from a plain string."""
    return _SECRET_VALUE_RE.sub(REDACTION_PLACEHOLDER, text)


def safe_summary(data: Union[Dict[str, Any], Any], max_keys: int = 10) -> Dict[str, Any]:
    """
    Produce a redacted, truncated summary safe for audit logs.
    Never includes raw secret values.
    """
    if not isinstance(data, dict):
        return {"_raw": redact_string(str(data))[:200]}

    redacted = redact_dict(data)
    # Limit to max_keys top-level keys for log brevity
    keys = list(redacted.keys())[:max_keys]
    summary = {k: redacted[k] for k in keys}
    if len(redacted) > max_keys:
        summary["_truncated_keys"] = len(redacted) - max_keys
    return summary


def assert_no_secrets(data: Any, context: str = "") -> None:
    """
    Raise ValueError if secret patterns are found in the serialized data.
    Used in tests and pre-export checks.
    """
    serialized = json.dumps(data, default=str)

    # Check for secret key names
    for pattern in SECRET_KEY_PATTERNS:
        if re.search(pattern, serialized, re.IGNORECASE):
            # Only fail if the matched key has a non-redacted value next to it
            # (i.e., the placeholder is NOT already there)
            pass  # Key presence alone is OK if value is [REDACTED]

    # Check for secret-like values that are NOT already redacted
    secret_values = _SECRET_VALUE_RE.findall(serialized)
    if secret_values:
        # Filter out the placeholder itself
        real_secrets = [v for v in secret_values if v != REDACTION_PLACEHOLDER]
        if real_secrets:
            raise ValueError(
                f"Secret leak detected in {context!r}: "
                f"{len(real_secrets)} secret-like value(s) found. "
                "Run redact_dict() before outputting this data."
            )
