"""
FaithVision Lead Generation System
audit.py — Append-only JSONL audit log. No raw secrets. No deletions.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from leadgen.redaction import safe_summary

# ── Audit log path ────────────────────────────────────────────────────────────

AUDIT_DIR_ENV = "LEADGEN_AUDIT_DIR"
_DEFAULT_AUDIT_DIR = os.path.join(os.path.dirname(__file__), "audit")
_AUDIT_FILENAME = "leadgen_audit.jsonl"


def get_audit_dir() -> str:
    """Return the active audit directory, honoring LEADGEN_AUDIT_DIR."""
    configured = os.environ.get(AUDIT_DIR_ENV)
    if configured:
        return os.path.realpath(os.path.expanduser(configured))
    return os.path.realpath(_DEFAULT_AUDIT_DIR)


def get_audit_file() -> str:
    """Return the active audit JSONL path."""
    return os.path.join(get_audit_dir(), _AUDIT_FILENAME)


def _ensure_audit_dir() -> None:
    os.makedirs(get_audit_dir(), exist_ok=True)


# ── Core log function ─────────────────────────────────────────────────────────

def log_action(
    action: str,
    actor: str,
    lead_id: str,
    decision: str,
    reason: str,
    payload_summary: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Append a single audit entry to the JSONL log.
    Payload is redacted before writing — no secrets ever stored.
    """
    _ensure_audit_dir()

    safe_payload = safe_summary(payload_summary or {})

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action":    action,
        "actor":     actor,
        "lead_id":   lead_id,
        "decision":  decision,
        "reason":    reason[:500],                     # cap reason length
        "payload_summary": safe_payload,
    }

    # Append-only write
    with open(get_audit_file(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Read log ──────────────────────────────────────────────────────────────────

def read_audit_log(limit: int = 100) -> list[Dict[str, Any]]:
    """Return the last `limit` audit entries. Returns [] if log doesn't exist."""
    _ensure_audit_dir()
    audit_file = get_audit_file()
    if not os.path.exists(audit_file):
        return []
    entries = []
    with open(audit_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries[-limit:]


def audit_stats() -> Dict[str, Any]:
    """Return summary statistics over the audit log."""
    entries = read_audit_log(limit=0)  # read all; 0 handled below
    # re-read all without limit
    _ensure_audit_dir()
    all_entries: list[Dict] = []
    audit_file = get_audit_file()
    if os.path.exists(audit_file):
        with open(audit_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        all_entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    total = len(all_entries)
    approved = sum(1 for e in all_entries if e.get("decision") == "approved")
    denied   = sum(1 for e in all_entries if e.get("decision") == "denied")
    actions  = {}
    for e in all_entries:
        a = e.get("action", "unknown")
        actions[a] = actions.get(a, 0) + 1

    return {
        "total_entries": total,
        "approved":      approved,
        "denied":        denied,
        "action_counts": actions,
        "audit_file":    audit_file,
    }
