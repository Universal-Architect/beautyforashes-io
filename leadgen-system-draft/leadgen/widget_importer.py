"""
FaithVision Lead Generation System
widget_importer.py - Local importer for website widget lead exports.

Converts the website widget localStorage/admin export shape into Lead objects,
then runs the normal local analysis, scoring, and save pipeline.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, List, Optional

from leadgen.analyzer import analyze_lead
from leadgen.models import Lead, RECOMMENDED_SERVICES
from leadgen.router import gate
from leadgen.scoring import score_lead
from leadgen.store import get_lead, save_lead


_LEAD_TYPE_KEYWORDS = (
    ("ministry", ("ministry", "church", "pastor", "congregation")),
    ("nonprofit", ("nonprofit", "non-profit", "charity", "foundation", "ngo")),
    ("for_profit", ("for_profit", "for-profit", "for profit", "business",
                    "company", "enterprise", "startup", "corporation")),
    ("individual", ("individual", "personal", "person", "myself", "solo")),
)

_SERVICE_KEYWORDS = (
    ("Gift Discovery / Personal Calling Session", ("gift-intensive", "gift discovery",
                                                   "gift", "calling", "purpose")),
    ("Nonprofit Solvency Review", ("turnaround-sprint", "turnaround sprint",
                                   "90-day turnaround", "nonprofit", "solvency",
                                   "deficit", "funding")),
    ("Hidden Asset & Revenue Stream Audit", ("hidden asset", "revenue stream",
                                             "asset audit", "monetize")),
    ("Executive Strategic Advisory", ("retainer", "executive", "strategic", "advisory")),
    ("Enterprise Transformation Engagement", ("enterprise", "transformation")),
    ("Speaking / Workshop Inquiry", ("speaking", "workshop", "keynote")),
    ("Book / FaithVision Resource Path", ("mastermind", "planner", "book", "resource",
                                          "faithvision")),
)

_WIDGET_SERVICE_MAP = {
    "gift-intensive": "Gift Discovery / Personal Calling Session",
    "gift_discovery_intensive": "Gift Discovery / Personal Calling Session",
    "gift discovery intensive": "Gift Discovery / Personal Calling Session",
    "turnaround-sprint": "Nonprofit Solvency Review",
    "90-day turnaround sprint": "Nonprofit Solvency Review",
    "retainer": "Executive Strategic Advisory",
    "fractional strategist retainer": "Executive Strategic Advisory",
    "enterprise": "Enterprise Transformation Engagement",
    "enterprise transformation": "Enterprise Transformation Engagement",
    "mastermind": "Book / FaithVision Resource Path",
    "gifts mastermind group": "Book / FaithVision Resource Path",
}


@dataclass
class WidgetImportSkip:
    index: int
    lead_id: str
    reason: str


@dataclass
class WidgetImportResult:
    total: int
    imported: List[Lead] = field(default_factory=list)
    skipped: List[WidgetImportSkip] = field(default_factory=list)

    @property
    def imported_count(self) -> int:
        return len(self.imported)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


def load_widget_export(path: str) -> List[Mapping[str, Any]]:
    """Load widget leads from JSON or CSV exported from the website widget."""
    with open(path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    stripped = raw_text.lstrip()
    if stripped.startswith("[") or stripped.startswith("{"):
        return widget_records_from_data(json.loads(raw_text))

    return widget_records_from_csv(raw_text.splitlines())


def widget_records_from_data(raw: Any) -> List[Mapping[str, Any]]:
    """Return widget lead records from the supported export shapes."""
    if isinstance(raw, list):
        records = raw
    elif isinstance(raw, Mapping) and isinstance(raw.get("leads"), list):
        records = raw["leads"]
    else:
        raise ValueError("Widget export must be a JSON array or an object with a 'leads' array.")

    normalized: List[Mapping[str, Any]] = []
    for index, item in enumerate(records):
        if not isinstance(item, Mapping):
            raise ValueError(f"Widget lead at index {index} must be an object.")
        normalized.append(item)
    return normalized


def widget_records_from_csv(lines: List[str]) -> List[Mapping[str, Any]]:
    """Return widget lead records from LeadStore.exportCSV() output."""
    reader = csv.DictReader(lines)
    if not reader.fieldnames:
        raise ValueError("Widget CSV export must include a header row.")

    records: List[Mapping[str, Any]] = []
    for row in reader:
        answers = {}
        for key in ("situation", "org_type", "budget", "urgency"):
            label = _clean_str(row.get(key))
            if label:
                answers[key] = {"label": label, "value": label}

        payload: dict[str, Any] = {}
        for key in (
            "id",
            "timestamp",
            "firstName",
            "email",
            "phone",
            "score",
            "tier",
            "recommendedService",
            "page",
            "referrer",
        ):
            value = _clean_str(row.get(key))
            if value:
                payload[key] = value
        if answers:
            payload["answers"] = answers
        records.append(payload)

    return records


def widget_payload_to_lead(payload: Mapping[str, Any]) -> Lead:
    """Convert one website widget payload into a FaithVision Lead."""
    answers = payload.get("answers")
    if not isinstance(answers, Mapping):
        answers = {}

    lead_id = _widget_lead_id(payload.get("id"))
    timestamp = _clean_str(payload.get("timestamp"))
    first_name = _clean_str(payload.get("firstName") or payload.get("first_name"))
    last_name = _clean_str(payload.get("lastName") or payload.get("last_name"))
    name = " ".join(part for part in (first_name, last_name) if part)

    situation = _answer_display(answers.get("situation"))
    org_type_answer = _answer_display(answers.get("org_type") or answers.get("orgType"))
    budget = _answer_display(answers.get("budget"))
    urgency = _answer_display(answers.get("urgency"))

    stated_parts = []
    if situation:
        stated_parts.append(situation)
    if urgency:
        stated_parts.append(f"Urgency: {urgency}")
    stated_problem = " | ".join(stated_parts)

    notes = _build_notes(
        payload=payload,
        answers=answers,
        situation=situation,
        org_type=org_type_answer,
        budget=budget,
        urgency=urgency,
    )

    lead_type = _infer_lead_type(org_type_answer, situation)

    lead_kwargs: dict[str, Any] = {
        "lead_type": lead_type,
        "name": name,
        "public_source": _source_summary(payload),
        "contact_email": _clean_str(payload.get("email")),
        "phone": _clean_str(payload.get("phone")),
        "sector": _sector_from_lead_type(lead_type),
        "stated_problem": stated_problem,
        "urgency_score": _urgency_score(answers.get("urgency")),
        "recommended_service": _normalize_service(payload.get("recommendedService")),
        "owner_review_required": True,
        "approval_status": "pending_owner_review",
        "notes": notes,
    }
    if lead_id:
        lead_kwargs["lead_id"] = lead_id
    if timestamp:
        lead_kwargs["created_at"] = timestamp
        lead_kwargs["updated_at"] = timestamp

    return Lead(**lead_kwargs)


def import_widget_file(path: str) -> WidgetImportResult:
    """
    Import widget leads from a local JSON file.

    Each valid lead is analyzed, scored, and saved through the existing policy
    gates. Invalid records are skipped and reported in the result.
    """
    records = load_widget_export(path)
    result = WidgetImportResult(total=len(records))

    for index, record in enumerate(records):
        lead_id = _clean_str(record.get("id")) if isinstance(record, Mapping) else ""
        try:
            lead = widget_payload_to_lead(record)
            errors = lead.validate()
            if errors:
                result.skipped.append(
                    WidgetImportSkip(index=index, lead_id=lead.lead_id, reason="; ".join(errors))
                )
                continue
            if get_lead(lead.lead_id):
                result.skipped.append(
                    WidgetImportSkip(
                        index=index,
                        lead_id=lead.lead_id,
                        reason="duplicate lead_id already exists; skipped without overwrite",
                    )
                )
                continue

            gate(
                action="classify_lead",
                lead_id=lead.lead_id,
                actor="widget_importer",
                payload_summary={"source": "website_widget", "lead_type": lead.lead_type},
            )
            analyze_lead(lead)

            gate(
                action="score_lead",
                lead_id=lead.lead_id,
                actor="widget_importer",
                payload_summary={"source": "website_widget", "lead_type": lead.lead_type},
            )
            score_lead(lead)

            save_lead(lead)
            result.imported.append(lead)
        except Exception as exc:
            result.skipped.append(
                WidgetImportSkip(index=index, lead_id=lead_id or "unknown", reason=str(exc))
            )

    return result


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _widget_lead_id(value: Any) -> str:
    raw = _clean_str(value)
    if not raw:
        return ""

    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in raw)
    while "--" in safe:
        safe = safe.replace("--", "-")
    safe = safe.strip("-._")
    if not safe:
        return ""
    if safe.startswith(("widget-", "website-widget-")):
        return safe
    return f"website-widget-{safe}"


def _answer_display(answer: Any) -> str:
    if isinstance(answer, Mapping):
        label = _clean_str(answer.get("label"))
        value = _clean_str(answer.get("value"))
        if label and value and label.lower() != value.lower():
            return f"{label} ({value})"
        return label or value
    return _clean_str(answer)


def _answer_score(answer: Any) -> Optional[float]:
    if isinstance(answer, Mapping):
        value = answer.get("score")
    else:
        value = None
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _urgency_score(answer: Any) -> float:
    text = _answer_display(answer).lower()
    explicit_score = _answer_score(answer)
    if explicit_score is not None:
        if 0.0 <= explicit_score <= 10.0:
            explicit_score *= 10.0
        return _clamp(explicit_score)

    if any(word in text for word in ("urgent", "immediate", "now", "asap", "crisis")):
        return 90.0
    if any(word in text for word in ("soon", "30", "60", "this month")):
        return 70.0
    if any(word in text for word in ("exploring", "eventually", "later")):
        return 30.0
    if "not urgent" in text:
        return 10.0
    return 50.0 if text else 0.0


def _clamp(value: float) -> float:
    return max(0.0, min(float(value), 100.0))


def _infer_lead_type(org_type_answer: str, situation: str = "") -> str:
    text = f"{org_type_answer} {situation}".lower()
    for lead_type, keywords in _LEAD_TYPE_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return lead_type
    return "unknown"


def _sector_from_lead_type(lead_type: str) -> str:
    if lead_type == "individual":
        return "Individual / FaithVision widget"
    if lead_type == "ministry":
        return "Faith / Ministry"
    if lead_type == "nonprofit":
        return "Nonprofit / FaithVision widget"
    if lead_type == "for_profit":
        return "For-profit / Business"
    return "FaithVision lead widget"


def _normalize_service(value: Any) -> str:
    service = _clean_str(value)
    if service in RECOMMENDED_SERVICES:
        return service

    text = service.replace("_", " ").replace("-", " ").lower()
    mapped = _WIDGET_SERVICE_MAP.get(text) or _WIDGET_SERVICE_MAP.get(service.lower())
    if mapped:
        return mapped

    for known_service, keywords in _SERVICE_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return known_service
    return "None / Insufficient Data"


def _source_summary(payload: Mapping[str, Any]) -> str:
    parts = ["Website widget"]
    page = _clean_str(payload.get("page"))
    referrer = _clean_str(payload.get("referrer"))
    if page:
        parts.append(f"page={page}")
    if referrer:
        parts.append(f"referrer={referrer}")
    return "; ".join(parts)


def _build_notes(
    payload: Mapping[str, Any],
    answers: Mapping[str, Any],
    situation: str,
    org_type: str,
    budget: str,
    urgency: str,
) -> str:
    lines = ["Lead widget import."]

    widget_id = _clean_str(payload.get("id"))
    widget_score = _clean_str(payload.get("score"))
    widget_tier = _clean_str(payload.get("tier"))
    widget_service = _clean_str(payload.get("recommendedService"))
    widget_service_route = _normalize_service(widget_service)
    if widget_id:
        lines.append(f"widget_id: {widget_id}")
    if widget_score:
        lines.append(f"widget_score: {widget_score}")
    if widget_tier:
        lines.append(f"widget_tier: {widget_tier}")
    if widget_service:
        if widget_service_route != "None / Insufficient Data" and widget_service_route != widget_service:
            lines.append(
                f"widget_recommended_service: {widget_service_route} (widget_id={widget_service})"
            )
        else:
            lines.append(f"widget_recommended_service: {widget_service}")

    for label, display in (
        ("situation", situation),
        ("org_type", org_type),
        ("budget", budget),
        ("urgency", urgency),
    ):
        if not display:
            continue
        score = _answer_score(answers.get(label))
        suffix = f" score={score:g}" if score is not None else ""
        lines.append(f"answer_{label}: {display}{suffix}")

    page = _clean_str(payload.get("page"))
    referrer = _clean_str(payload.get("referrer"))
    if page:
        lines.append(f"source_page: {page}")
    if referrer:
        lines.append(f"source_referrer: {referrer}")

    return "\n".join(lines)
