"""
FaithVision Lead Generation System
router.py — Deny-by-default action router.
Every action passes through this gate. Forbidden actions are BLOCKED.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Callable, Optional

from leadgen.audit import log_action


# ── Load policy ───────────────────────────────────────────────────────────────

def _load_policy() -> Dict[str, Any]:
    policy_path = os.path.join(os.path.dirname(__file__), "policy.json")
    with open(policy_path, "r", encoding="utf-8") as f:
        return json.load(f)


_POLICY = _load_policy()
_ALLOWED: set[str] = set(_POLICY["allowed_local_actions"])
_FORBIDDEN: set[str] = set(_POLICY["forbidden_actions"])


# ── Policy Gate ───────────────────────────────────────────────────────────────

class PolicyViolation(Exception):
    """Raised when an action is forbidden by the deny-by-default policy."""
    pass


def gate(action: str, lead_id: Optional[str] = None,
         actor: str = "system", payload_summary: Optional[Dict] = None) -> None:
    """
    Evaluate an action against the policy.
    - If forbidden: raise PolicyViolation and log the denial.
    - If not in allowed list: raise PolicyViolation (deny-by-default).
    - If allowed: log the approval and return normally.
    """
    reason: str
    decision: str

    if action in _FORBIDDEN:
        decision = "denied"
        reason = (
            f"Action '{action}' is explicitly FORBIDDEN by FaithVision deny-by-default policy. "
            f"Description: {_POLICY.get('forbidden_action_descriptions', {}).get(action, 'No description.')}"
        )
        log_action(
            action=action,
            actor=actor,
            lead_id=lead_id or "N/A",
            decision=decision,
            reason=reason,
            payload_summary=payload_summary or {},
        )
        raise PolicyViolation(reason)

    if action not in _ALLOWED:
        decision = "denied"
        reason = (
            f"Action '{action}' is not in the allowed_local_actions list. "
            "Default policy is DENY. Only explicitly allowed actions may proceed."
        )
        log_action(
            action=action,
            actor=actor,
            lead_id=lead_id or "N/A",
            decision=decision,
            reason=reason,
            payload_summary=payload_summary or {},
        )
        raise PolicyViolation(reason)

    # Action is allowed
    decision = "approved"
    reason = f"Action '{action}' is in the allowed_local_actions list."
    log_action(
        action=action,
        actor=actor,
        lead_id=lead_id or "N/A",
        decision=decision,
        reason=reason,
        payload_summary=payload_summary or {},
    )


def is_allowed(action: str) -> bool:
    """Non-raising check: returns True if the action is permitted."""
    return action in _ALLOWED and action not in _FORBIDDEN


def is_forbidden(action: str) -> bool:
    """Returns True if the action is explicitly forbidden."""
    return action in _FORBIDDEN


def get_policy_summary() -> Dict[str, Any]:
    """Return a human-readable policy summary (no secrets)."""
    return {
        "default_action": _POLICY.get("default_action", "deny"),
        "allowed_local_actions": list(_ALLOWED),
        "forbidden_actions": list(_FORBIDDEN),
        "owner_emails": {
            "primary": _POLICY.get("owner_emails", {}).get("primary", ""),
            "catchall": _POLICY.get("owner_emails", {}).get("catchall", ""),
        },
        "approval_required_for": _POLICY.get("approval_required_for", []),
    }
