"""
FaithVision Lead Generation System
email_drafter.py — Draft-only email composer. NO SENDING. Ever.
All drafts require owner review before any outreach.
"""

from __future__ import annotations

from typing import List, Dict, Any

from leadgen.models import Lead, EmailDraft
from leadgen.router import gate
from leadgen.redaction import redact_dict


# ── Sender routing ────────────────────────────────────────────────────────────

PRIMARY_EMAIL   = "andersonraymond7@icloud.com"   # high-value / priority leads
CATCHALL_EMAIL  = "pastorpaol@gmail.com"          # watch / lower-tier leads

TIER_TO_SENDER = {
    "executive": PRIMARY_EMAIL,
    "priority":  PRIMARY_EMAIL,
    "qualified": PRIMARY_EMAIL,
    "watch":     CATCHALL_EMAIL,
    "low":       CATCHALL_EMAIL,
}


# ── Template builders ─────────────────────────────────────────────────────────

def _short_first_touch(lead: Lead) -> EmailDraft:
    name_or_org = lead.name or lead.organization or "there"
    subject = f"A Quick Thought for {name_or_org} — From Pastor Anderson"
    body = f"""\
Hi {name_or_org},

My name is Pastor Raymond Anderson — I work with individuals, nonprofits, and \
companies to uncover hidden value and unlock sustainable growth grounded in purpose.

I came across {lead.organization or 'your work'} and noticed {lead.stated_problem or 'some challenges and opportunities worth discussing'}.

I'd love to share a thought or two — no pitch, just a brief conversation to see if \
there's a natural fit for what we do.

Would 20 minutes this week work for you?

Grateful for your time,
Pastor Raymond Anderson
FaithVision Consulting
{PRIMARY_EMAIL}

— All outreach from FaithVision is values-driven and confidential. —
"""
    return EmailDraft(
        lead_id=lead.lead_id,
        template_type="short_first_touch",
        subject=subject,
        body=body,
        reason_relevant=(
            f"Short, low-friction first contact. Lead type: {lead.lead_type}. "
            f"Stated problem: {lead.stated_problem[:120] if lead.stated_problem else 'N/A'}."
        ),
        suggested_sender=TIER_TO_SENDER.get(lead.tier, CATCHALL_EMAIL),
        approval_status="pending_owner_review",
    )


def _warm_referral(lead: Lead) -> EmailDraft:
    name_or_org = lead.name or lead.organization or "there"
    subject = f"Thought of You — {name_or_org} — Pastor Raymond Anderson"
    body = f"""\
Hi {name_or_org},

Someone whose judgment I trust mentioned {lead.organization or 'your name'} — \
and after learning a little more, I wanted to reach out personally.

At FaithVision, we specialize in finding the value that organizations and individuals \
often can't see themselves — dormant assets, untapped revenue streams, and the kind of \
strategic clarity that changes trajectories.

Based on what I understand about {lead.sector or 'your sector'}, I think there may be \
some genuinely useful conversations we could have — particularly around \
{lead.inferred_problem[:150] if lead.inferred_problem else 'your current season of growth or challenge'}.

No agenda. Just a 30-minute conversation to see if this resonates.

Honored to connect,
Pastor Raymond Anderson
FaithVision Consulting
{PRIMARY_EMAIL}

— This communication is confidential and for informational purposes only. —
"""
    return EmailDraft(
        lead_id=lead.lead_id,
        template_type="warm_referral",
        subject=subject,
        body=body,
        reason_relevant=(
            f"Warm referral framing — builds trust quickly. "
            f"Tier: {lead.tier}. Service fit: {lead.recommended_service}."
        ),
        suggested_sender=PRIMARY_EMAIL,
        approval_status="pending_owner_review",
    )


def _nonprofit_version(lead: Lead) -> EmailDraft:
    name_or_org = lead.name or lead.organization or "your organization"
    subject = f"Financial Resilience for {name_or_org} — FaithVision"
    body = f"""\
Dear {name_or_org} Leadership,

I'm reaching out because FaithVision works with nonprofits navigating financial \
complexity — whether that's funding shortfalls, solvency challenges, donor diversification, \
or discovering hidden assets that can be converted to sustainable cash flow.

We understand the mission is sacred. Which is exactly why the financial foundation \
must be strong.

We've helped organizations uncover:
  • Underutilized real estate and equipment that can generate revenue
  • Dormant donor segments that can be re-engaged
  • Grant and funding opportunities hidden in plain sight
  • Structural changes that reduce overhead without cutting mission delivery

Given what I know about {lead.sector or 'your sector'}, I believe {name_or_org} \
may benefit from a confidential Nonprofit Solvency Review — a structured 3-phase \
engagement that typically identifies 6–12 months of additional runway.

I'd welcome a brief conversation with your Executive Director or Board Chair.

Serving the mission with you,
Pastor Raymond Anderson
FaithVision Consulting
{PRIMARY_EMAIL}

— CONFIDENTIAL — For review purposes only. No commitments implied. —
"""
    return EmailDraft(
        lead_id=lead.lead_id,
        template_type="nonprofit_version",
        subject=subject,
        body=body,
        reason_relevant=(
            f"Nonprofit-specific outreach. Distress signals: "
            f"{', '.join(lead.distress_signals[:3]) or 'none detected'}. "
            f"Recommended service: {lead.recommended_service}."
        ),
        suggested_sender=PRIMARY_EMAIL,
        approval_status="pending_owner_review",
    )


def _for_profit_exec_version(lead: Lead) -> EmailDraft:
    name_or_org = lead.name or lead.organization or "your company"
    subject = f"Revenue & Value Discovery for {name_or_org} — Confidential"
    body = f"""\
Dear Executive Team at {name_or_org},

I'm Pastor Raymond Anderson — I advise companies on uncovering the revenue and \
asset value that typical consultants walk right past.

My work focuses on three high-leverage areas:
  1. Hidden Asset Identification — turning dormant assets into active capital
  2. Revenue Stream Discovery — finding the 20% of opportunities producing 80% of future growth
  3. Strategic Repositioning — finding the blue ocean hiding inside your current market position

I've reviewed what I know about {lead.sector or 'your industry'}, and based on \
{lead.stated_problem[:100] if lead.stated_problem else 'your current trajectory'}, \
I believe a brief Hidden Asset & Revenue Stream Audit could surface significant \
opportunity within 30 days.

This is a confidential executive engagement — no public disclosure, no obligations.

Would your leadership team have 45 minutes in the next two weeks?

With strategic intent,
Pastor Raymond Anderson
FaithVision Strategic Advisory
{PRIMARY_EMAIL}

— CONFIDENTIAL — Draft only. Requires owner review before any delivery. —
"""
    return EmailDraft(
        lead_id=lead.lead_id,
        template_type="for_profit_exec_version",
        subject=subject,
        body=body,
        reason_relevant=(
            f"Executive-level for-profit outreach. "
            f"Opportunity signals: {', '.join(lead.opportunity_signals[:3]) or 'TBD'}. "
            f"Tier: {lead.tier}."
        ),
        suggested_sender=PRIMARY_EMAIL,
        approval_status="pending_owner_review",
    )


def _individual_gift_dev(lead: Lead) -> EmailDraft:
    name = lead.name or "Friend"
    subject = f"Unlocking What's Already Inside You — {name}"
    body = f"""\
Hi {name},

I don't know exactly where you are right now — but I have a sense that something \
in you is ready to move.

I'm Pastor Raymond Anderson. My life's work is helping people like you identify the \
gifts, experiences, and assets they already have — and build a clear, monetizable \
path forward grounded in purpose.

Sometimes that looks like:
  • Discovering a calling you've been sitting on for years
  • Turning a life story into a speaking career, book, or coaching practice
  • Finding the income stream hiding in your unique combination of skill and experience

No fluff. No hype. Just a honest 30-minute conversation where we look at what \
you've already built and ask: what's next, and how do we get there?

If that resonates at all, I'd love to connect.

Rooting for you,
Pastor Raymond Anderson
FaithVision — Gift Discovery & Purpose Activation
{PRIMARY_EMAIL}

— This is a DRAFT. Requires owner review and approval before any send. —
"""
    return EmailDraft(
        lead_id=lead.lead_id,
        template_type="individual_gift_dev",
        subject=subject,
        body=body,
        reason_relevant=(
            f"Individual gift/purpose development outreach. "
            f"Stated problem: {lead.stated_problem[:100] or 'Not specified'}. "
            f"Service: {lead.recommended_service}."
        ),
        suggested_sender=TIER_TO_SENDER.get(lead.tier, CATCHALL_EMAIL),
        approval_status="pending_owner_review",
    )


# ── Main draft function ───────────────────────────────────────────────────────

def draft_emails(lead: Lead) -> List[EmailDraft]:
    """
    Generate all applicable email draft templates for a lead.
    NEVER sends. All drafts carry approval_status='pending_owner_review'.
    Requires 'draft_email' to pass the policy gate.
    """
    gate(
        action="draft_email",
        lead_id=lead.lead_id,
        actor="email_drafter",
        payload_summary={"lead_type": lead.lead_type, "tier": lead.tier},
    )

    drafts: List[EmailDraft] = []

    # Always generate short first-touch and warm referral
    drafts.append(_short_first_touch(lead))
    drafts.append(_warm_referral(lead))

    # Type-specific drafts
    if lead.lead_type in ("nonprofit", "ministry"):
        drafts.append(_nonprofit_version(lead))

    if lead.lead_type == "for_profit":
        drafts.append(_for_profit_exec_version(lead))

    if lead.lead_type == "individual":
        drafts.append(_individual_gift_dev(lead))

    # All drafts confirmed pending_owner_review
    for draft in drafts:
        assert draft.approval_status == "pending_owner_review", (
            "INVARIANT VIOLATION: A draft was created without pending_owner_review status."
        )

    return drafts


def drafts_to_dict_list(drafts: List[EmailDraft]) -> List[Dict[str, Any]]:
    return [redact_dict(d.to_dict()) for d in drafts]
