"""
FaithVision Lead Generation System
cli.py — Command-line interface.
Usage:
  python -m leadgen.cli import sample_leads.json
  python -m leadgen.cli import-widget widget_leads.json
  python -m leadgen.cli import-widget widget_leads.csv
  python -m leadgen.cli list
  python -m leadgen.cli show LEAD_ID
  python -m leadgen.cli score LEAD_ID
  python -m leadgen.cli draft LEAD_ID
  python -m leadgen.cli packet LEAD_ID
  python -m leadgen.cli audit
  python -m leadgen.cli export output.json
  python -m leadgen.cli policy
"""

from __future__ import annotations

import json
import os
import sys
from textwrap import indent
from typing import List

from leadgen.models import Lead, ReviewPacket
from leadgen.store import (
    data_file_path,
    export_local_json,
    get_lead,
    list_leads,
    save_lead,
    save_packet,
)
from leadgen.analyzer import analyze_lead
from leadgen.scoring import score_lead
from leadgen.email_drafter import draft_emails, drafts_to_dict_list
from leadgen.audit import read_audit_log, audit_stats
from leadgen.router import get_policy_summary, PolicyViolation
from leadgen.redaction import redact_dict
from leadgen.widget_importer import import_widget_file


# ── Pretty print helpers ──────────────────────────────────────────────────────

def _sep(char: str = "─", width: int = 72) -> str:
    return char * width


def _header(title: str) -> None:
    print(f"\n{_sep('═')}")
    print(f"  FaithVision LeadGen  |  {title}")
    print(_sep("═"))


def _print_lead_summary(lead: Lead) -> None:
    print(f"  ID:         {lead.lead_id}")
    print(f"  Name/Org:   {lead.name or lead.organization or '(unnamed)'}")
    print(f"  Type:       {lead.lead_type.upper()}")
    print(f"  Tier:       {lead.tier.upper()}")
    print(f"  Score:      {lead.total_score:.1f}/100")
    print(f"  Service:    {lead.recommended_service}")
    print(f"  Urgency:    {lead.urgency_score:.1f}")
    print(f"  Review:     {lead.approval_status}")
    print(f"  Sector:     {lead.sector or '—'}")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_import(args: List[str]) -> None:
    if not args:
        print("ERROR: provide a JSON file path.  e.g.  python -m leadgen.cli import sample_leads.json")
        sys.exit(1)
    path = args[0]
    if not os.path.exists(path):
        # Try relative to this file's directory
        alt = os.path.join(os.path.dirname(__file__), path)
        if os.path.exists(alt):
            path = alt
        else:
            print(f"ERROR: File not found: {path}")
            sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raw = [raw]

    imported = 0
    for item in raw:
        try:
            lead = Lead.from_dict(item)
            errors = lead.validate()
            if errors:
                print(f"  SKIP {lead.lead_id}: validation errors — {errors}")
                continue
            # Run analysis + scoring on import
            analyze_lead(lead)
            score_lead(lead)
            save_lead(lead)
            print(f"  ✓ Imported [{lead.lead_type.upper()}] {lead.name or lead.organization or lead.lead_id}  |  Tier: {lead.tier.upper()}  Score: {lead.total_score:.1f}")
            imported += 1
        except Exception as e:
            print(f"  ERROR importing item: {e}")

    print(f"\n  {imported}/{len(raw)} leads imported successfully.")


def cmd_import_widget(args: List[str]) -> None:
    if not args:
        print("ERROR: provide a widget export file path.  e.g.  python -m leadgen.cli import-widget widget_leads.json")
        sys.exit(1)
    path = args[0]
    if not os.path.exists(path):
        alt = os.path.join(os.path.dirname(__file__), path)
        if os.path.exists(alt):
            path = alt
        else:
            print(f"ERROR: File not found: {path}")
            sys.exit(1)

    result = import_widget_file(path)
    for lead in result.imported:
        print(
            f"  ✓ Imported widget lead {lead.name or lead.organization or lead.lead_id}  |  "
            f"Type: {lead.lead_type.upper()}  Tier: {lead.tier.upper()}  "
            f"Score: {lead.total_score:.1f}"
        )
    for skipped in result.skipped:
        print(f"  SKIP widget item {skipped.index} ({skipped.lead_id}): {skipped.reason}")

    print(
        f"\n  {result.imported_count}/{result.total} widget leads imported successfully "
        "(local only; no outreach generated or sent)."
    )


def cmd_list(_args: List[str]) -> None:
    _header("All Leads")
    leads = list_leads()
    if not leads:
        print("  No leads found. Run:  python -m leadgen.cli import sample_leads.json")
        return
    # Sort by total_score descending
    leads.sort(key=lambda l: l.total_score, reverse=True)
    print(f"  {'ID':36} {'Type':12} {'Tier':12} {'Score':8} {'Name/Org'}")
    print(f"  {_sep('-', 36)} {_sep('-', 12)} {_sep('-', 12)} {_sep('-', 8)} {_sep('-', 30)}")
    for lead in leads:
        print(f"  {lead.lead_id} {lead.lead_type.upper():12} {lead.tier.upper():12} "
              f"{lead.total_score:7.1f}  {lead.name or lead.organization or '—'}")
    print(f"\n  Total: {len(leads)} lead(s)")


def cmd_show(args: List[str]) -> None:
    if not args:
        print("ERROR: provide a LEAD_ID")
        sys.exit(1)
    lead = get_lead(args[0])
    if not lead:
        print(f"ERROR: Lead '{args[0]}' not found.")
        sys.exit(1)
    _header(f"Lead Detail — {lead.lead_id[:8]}…")
    _print_lead_summary(lead)
    print(f"\n  Stated Problem:\n{indent(lead.stated_problem or '—', '    ')}")
    print(f"\n  Inferred Problem:\n{indent(lead.inferred_problem or '—', '    ')}")
    print(f"\n  Assets Detected:     {', '.join(lead.assets_detected) or '—'}")
    print(f"  Distress Signals:    {', '.join(lead.distress_signals) or '—'}")
    print(f"  Opportunity Signals: {', '.join(lead.opportunity_signals) or '—'}")
    print(f"\n  Recommended Next Step:\n{indent(lead.recommended_next_step or '—', '    ')}")
    print(f"\n  Score Explanation:\n{indent(lead.score_explanation or '—', '    ')}")


def cmd_score(args: List[str]) -> None:
    if not args:
        print("ERROR: provide a LEAD_ID")
        sys.exit(1)
    from leadgen.store import update_lead
    lead = get_lead(args[0])
    if not lead:
        print(f"ERROR: Lead '{args[0]}' not found.")
        sys.exit(1)
    _header(f"Scoring — {lead.lead_id[:8]}…")
    result = score_lead(lead)
    update_lead(lead)
    print(f"  Total Score: {result.total_score:.2f}/100")
    print(f"  Tier:        {result.tier.upper()}")
    print(f"\n  Dimension Scores:")
    for dim, val in result.dimension_scores.items():
        print(f"    {dim.replace('_', ' ').title():40} {val:.1f}")
    print(f"\n  Recommended Action:\n{indent(result.recommended_action, '    ')}")
    if result.flags:
        print(f"\n  Flags:")
        for flag in result.flags[:8]:
            print(f"    • {flag}")


def cmd_draft(args: List[str]) -> None:
    if not args:
        print("ERROR: provide a LEAD_ID")
        sys.exit(1)
    lead = get_lead(args[0])
    if not lead:
        print(f"ERROR: Lead '{args[0]}' not found.")
        sys.exit(1)
    _header(f"Email Drafts (DRAFT ONLY — owner approval required) — {lead.lead_id[:8]}…")
    try:
        drafts = draft_emails(lead)
    except PolicyViolation as e:
        print(f"POLICY BLOCKED: {e}")
        sys.exit(1)
    for i, draft in enumerate(drafts, 1):
        print(f"\n  ── Draft {i}: {draft.template_type} ──")
        print(f"  Subject:  {draft.subject}")
        print(f"  Sender:   {draft.suggested_sender}")
        print(f"  Status:   {draft.approval_status}")
        print(f"  Reason:   {draft.reason_relevant}")
        print(f"\n  Body:\n{indent(draft.body, '    ')}")
        print(f"  {_sep()}")
    print(f"\n  ⚠  {len(drafts)} draft(s) generated. ALL require owner review before any outreach.")


def cmd_packet(args: List[str]) -> None:
    if not args:
        print("ERROR: provide a LEAD_ID")
        sys.exit(1)
    lead = get_lead(args[0])
    if not lead:
        print(f"ERROR: Lead '{args[0]}' not found.")
        sys.exit(1)
    _header(f"Owner Review Packet — {lead.lead_id[:8]}…")
    try:
        drafts = draft_emails(lead)
    except PolicyViolation as e:
        print(f"POLICY BLOCKED: {e}")
        sys.exit(1)

    result = score_lead(lead)
    analysis = analyze_lead(lead)

    packet = ReviewPacket(
        lead_id=lead.lead_id,
        lead_snapshot=redact_dict(lead.to_dict()),
        email_drafts=drafts_to_dict_list(drafts),
        score_summary=result.to_dict(),
        analysis_summary=json.dumps(analysis, indent=2, default=str),
        owner_action_required=(
            "OWNER: Review all email drafts above. Approve, edit, or reject each one "
            "before any outreach. No emails have been sent. This packet is local only."
        ),
    )
    save_packet(packet)
    packet_file = data_file_path(f"packet_{packet.packet_id[:8]}.json")
    with open(packet_file, "w", encoding="utf-8") as f:
        json.dump(redact_dict(packet.to_dict()), f, indent=2, default=str)
    print(f"  ✓ Review packet saved: {packet_file}")
    print(f"  Packet ID: {packet.packet_id}")
    print(f"  Drafts:    {len(drafts)}")
    print(f"  Score:     {result.total_score:.1f} / Tier: {result.tier.upper()}")
    print(f"\n  ⚠  Owner action required. Nothing has been sent or published.")


def cmd_audit(_args: List[str]) -> None:
    _header("Audit Log")
    stats = audit_stats()
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  Approved:      {stats['approved']}")
    print(f"  Denied:        {stats['denied']}")
    print(f"  File:          {stats['audit_file']}")
    if stats["action_counts"]:
        print(f"\n  Action Counts:")
        for action, count in sorted(stats["action_counts"].items(), key=lambda x: -x[1]):
            print(f"    {action:40} {count}")
    entries = read_audit_log(limit=10)
    if entries:
        print(f"\n  Last {min(10, len(entries))} entries:")
        for e in entries:
            print(f"    [{e.get('timestamp','?')[:19]}] {e.get('decision','?').upper():8} "
                  f"{e.get('action','?'):30} lead={e.get('lead_id','?')[:8]}")


def cmd_export(args: List[str]) -> None:
    out = args[0] if args else "export.json"
    try:
        path = export_local_json(out)
        print(f"  ✓ Exported to: {path}")
    except PolicyViolation as e:
        print(f"POLICY BLOCKED: {e}")
        sys.exit(1)


def cmd_policy(_args: List[str]) -> None:
    _header("Active Policy")
    policy = get_policy_summary()
    print(f"  Default Action: {policy['default_action'].upper()}")
    print(f"\n  Allowed Actions:")
    for a in sorted(policy["allowed_local_actions"]):
        print(f"    ✓ {a}")
    print(f"\n  Forbidden Actions:")
    for a in sorted(policy["forbidden_actions"]):
        print(f"    ✗ {a}")
    print(f"\n  Owner Emails:")
    print(f"    Primary:  {policy['owner_emails']['primary']}")
    print(f"    Catch-all: {policy['owner_emails']['catchall']}")


# ── Main entrypoint ───────────────────────────────────────────────────────────

COMMANDS = {
    "import":        cmd_import,
    "import-widget": cmd_import_widget,
    "list":          cmd_list,
    "show":          cmd_show,
    "score":         cmd_score,
    "draft":         cmd_draft,
    "packet":        cmd_packet,
    "audit":         cmd_audit,
    "export":        cmd_export,
    "policy":        cmd_policy,
}


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        print("\n  Commands: " + " | ".join(COMMANDS.keys()))
        sys.exit(0)

    cmd = args[0]
    if cmd not in COMMANDS:
        print(f"ERROR: Unknown command '{cmd}'. Available: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    try:
        COMMANDS[cmd](args[1:])
    except PolicyViolation as e:
        print(f"\n🚫 POLICY VIOLATION: {e}")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)


if __name__ == "__main__":
    main()
