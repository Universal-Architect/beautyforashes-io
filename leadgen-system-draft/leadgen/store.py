"""
FaithVision Lead Generation System
store.py — Local JSON file store. Safe paths. Atomic writes. No traversal.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, List, Optional

from leadgen.models import Lead, ReviewPacket
from leadgen.redaction import redact_dict
from leadgen.router import gate

# ── Paths ─────────────────────────────────────────────────────────────────────

DATA_DIR_ENV = "LEADGEN_DATA_DIR"
_DEFAULT_BASE_DIR = os.path.join(os.path.dirname(__file__), "data")
_LEADS_FILENAME = "leads.json"
_PACKETS_FILENAME = "review_packets.json"


def get_data_dir() -> str:
    """Return the active local data directory, honoring LEADGEN_DATA_DIR."""
    configured = os.environ.get(DATA_DIR_ENV)
    if configured:
        return os.path.realpath(os.path.expanduser(configured))
    return os.path.realpath(_DEFAULT_BASE_DIR)


# ── Path safety ───────────────────────────────────────────────────────────────

def _safe_path(filename: str, base: str) -> str:
    """
    Resolve a filename relative to base and ensure no path traversal.
    Raises ValueError if the resolved path escapes the base directory.
    """
    resolved = os.path.realpath(os.path.join(base, filename))
    base_real = os.path.realpath(base)
    if not resolved.startswith(base_real + os.sep) and resolved != base_real:
        raise ValueError(
            f"Path traversal attempt detected: '{filename}' resolves outside '{base}'."
        )
    return resolved


def data_file_path(filename: str) -> str:
    """Resolve a filename inside the active local data directory."""
    return _safe_path(filename, get_data_dir())


def _leads_file() -> str:
    return data_file_path(_LEADS_FILENAME)


def _packets_file() -> str:
    return data_file_path(_PACKETS_FILENAME)


def _ensure_data_dir() -> None:
    os.makedirs(get_data_dir(), exist_ok=True)


# ── Atomic write ──────────────────────────────────────────────────────────────

def _atomic_write(path: str, data: Any) -> None:
    """Write JSON atomically using a temp file + rename."""
    _ensure_data_dir()
    dir_name = os.path.dirname(path)
    os.makedirs(dir_name, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=dir_name,
        delete=False, suffix=".tmp"
    ) as tmp:
        json.dump(data, tmp, indent=2, default=str)
        tmp_path = tmp.name
    os.replace(tmp_path, path)


# ── Lead store ────────────────────────────────────────────────────────────────

def _load_leads() -> Dict[str, Any]:
    _ensure_data_dir()
    leads_file = _leads_file()
    if not os.path.exists(leads_file):
        return {}
    try:
        with open(leads_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_lead(lead: Lead) -> None:
    """Persist a lead to the local JSON store."""
    gate(
        action="import_lead",
        lead_id=lead.lead_id,
        actor="store",
        payload_summary={"name": lead.name, "lead_type": lead.lead_type},
    )
    db = _load_leads()
    db[lead.lead_id] = lead.to_dict()
    _atomic_write(_leads_file(), db)


def get_lead(lead_id: str) -> Optional[Lead]:
    """Retrieve a single lead by ID. Returns None if not found."""
    db = _load_leads()
    data = db.get(lead_id)
    if data is None:
        return None
    return Lead.from_dict(data)


def list_leads() -> List[Lead]:
    """Return all stored leads."""
    db = _load_leads()
    return [Lead.from_dict(v) for v in db.values()]


def update_lead(lead: Lead) -> None:
    """Update an existing lead in the store."""
    db = _load_leads()
    if lead.lead_id not in db:
        raise KeyError(f"Lead '{lead.lead_id}' not found in store.")
    lead.touch()
    db[lead.lead_id] = lead.to_dict()
    _atomic_write(_leads_file(), db)


# ── Review packet store ───────────────────────────────────────────────────────

def _load_packets() -> Dict[str, Any]:
    _ensure_data_dir()
    packets_file = _packets_file()
    if not os.path.exists(packets_file):
        return {}
    try:
        with open(packets_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}


def save_packet(packet: ReviewPacket) -> None:
    """Save a review packet (owner review bundle) locally."""
    gate(
        action="create_owner_review_packet",
        lead_id=packet.lead_id,
        actor="store",
        payload_summary={"packet_id": packet.packet_id},
    )
    db = _load_packets()
    db[packet.packet_id] = packet.to_dict()
    _atomic_write(_packets_file(), db)


def get_packet(packet_id: str) -> Optional[ReviewPacket]:
    db = _load_packets()
    data = db.get(packet_id)
    if data is None:
        return None
    return ReviewPacket(**{k: v for k, v in data.items()
                          if k in ReviewPacket.__dataclass_fields__})  # type: ignore


def list_packets() -> List[ReviewPacket]:
    db = _load_packets()
    return [ReviewPacket(**{k: v for k, v in p.items()
                            if k in ReviewPacket.__dataclass_fields__})  # type: ignore
            for p in db.values()]


# ── Local JSON export ─────────────────────────────────────────────────────────

def export_local_json(output_path: str) -> str:
    """
    Export all leads + packets to a single local JSON file.
    Redacts sensitive fields before export.
    Requires export_local_json policy gate.
    """
    if os.path.isabs(output_path):
        resolved_out = os.path.realpath(output_path)
        base_real = os.path.realpath(get_data_dir())
        if not resolved_out.startswith(base_real + os.sep):
            raise ValueError(
                "Export path must stay inside the configured leadgen data folder."
            )
    else:
        resolved_out = data_file_path(output_path)

    gate(
        action="export_local_json",
        lead_id="ALL",
        actor="store",
        payload_summary={"output_path": resolved_out, "leads_count": len(_load_leads())},
    )

    leads = [redact_dict(l.to_dict()) for l in list_leads()]
    packets = [redact_dict(p.to_dict()) for p in list_packets()]
    export_data = {"leads": leads, "review_packets": packets}
    _atomic_write(resolved_out, export_data)
    return resolved_out
