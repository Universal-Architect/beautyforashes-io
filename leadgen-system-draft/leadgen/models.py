"""
FaithVision Lead Generation System
models.py — Lead data model with validation
Deny-by-default. Local draft only. No outreach without owner approval.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any


# ── Enumerations (plain strings to avoid stdlib version issues) ──────────────

LEAD_TYPES = {"individual", "nonprofit", "for_profit", "ministry", "unknown"}

TIERS = {"low", "watch", "qualified", "priority", "executive"}

APPROVAL_STATUSES = {"pending_owner_review", "approved", "rejected", "archived"}

RECOMMENDED_SERVICES = {
    "Gift Discovery / Personal Calling Session",
    "Nonprofit Solvency Review",
    "Hidden Asset & Revenue Stream Audit",
    "Executive Strategic Advisory",
    "Enterprise Transformation Engagement",
    "Speaking / Workshop Inquiry",
    "Book / FaithVision Resource Path",
    "None / Insufficient Data",
}


# ── Lead dataclass ────────────────────────────────────────────────────────────

@dataclass
class Lead:
    # Identity
    lead_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    lead_type: str = "unknown"                    # individual | nonprofit | for_profit | ministry | unknown
    name: str = ""
    organization: str = ""
    website: str = ""
    public_source: str = ""                       # where this lead was discovered
    contact_email: str = ""
    phone: str = ""
    location: str = ""
    sector: str = ""

    # Problem / opportunity
    stated_problem: str = ""
    inferred_problem: str = ""
    assets_detected: List[str] = field(default_factory=list)
    revenue_streams_detected: List[str] = field(default_factory=list)
    distress_signals: List[str] = field(default_factory=list)
    opportunity_signals: List[str] = field(default_factory=list)

    # Scoring (populated by scoring engine)
    fit_score: float = 0.0
    urgency_score: float = 0.0
    value_creation_score: float = 0.0
    total_score: float = 0.0
    tier: str = "low"
    score_explanation: str = ""

    # Recommendations
    recommended_service: str = "None / Insufficient Data"
    recommended_next_step: str = ""

    # Workflow
    owner_review_required: bool = True
    approval_status: str = "pending_owner_review"
    notes: str = ""

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def validate(self) -> List[str]:
        """Return a list of validation errors (empty = valid)."""
        errors: List[str] = []
        if self.lead_type not in LEAD_TYPES:
            errors.append(f"Invalid lead_type '{self.lead_type}'. Must be one of {LEAD_TYPES}.")
        if self.tier not in TIERS:
            errors.append(f"Invalid tier '{self.tier}'. Must be one of {TIERS}.")
        if self.approval_status not in APPROVAL_STATUSES:
            errors.append(f"Invalid approval_status '{self.approval_status}'.")
        if self.recommended_service not in RECOMMENDED_SERVICES:
            errors.append(f"Invalid recommended_service '{self.recommended_service}'.")
        if not (0.0 <= self.fit_score <= 100.0):
            errors.append("fit_score must be 0–100.")
        if not (0.0 <= self.urgency_score <= 100.0):
            errors.append("urgency_score must be 0–100.")
        if not (0.0 <= self.value_creation_score <= 100.0):
            errors.append("value_creation_score must be 0–100.")
        if not (0.0 <= self.total_score <= 100.0):
            errors.append("total_score must be 0–100.")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Lead":
        # Only pull known fields; ignore extras gracefully
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# ── Email Draft model ─────────────────────────────────────────────────────────

@dataclass
class EmailDraft:
    draft_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str = ""
    template_type: str = ""       # short_first_touch | warm_referral | nonprofit | for_profit_exec | individual_gift
    subject: str = ""
    body: str = ""
    reason_relevant: str = ""
    suggested_sender: str = ""
    approval_status: str = "pending_owner_review"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmailDraft":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# ── Review Packet model ───────────────────────────────────────────────────────

@dataclass
class ReviewPacket:
    packet_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str = ""
    lead_snapshot: Dict[str, Any] = field(default_factory=dict)
    email_drafts: List[Dict[str, Any]] = field(default_factory=list)
    score_summary: Dict[str, Any] = field(default_factory=dict)
    analysis_summary: str = ""
    owner_action_required: str = "Review all drafts before any outreach."
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
