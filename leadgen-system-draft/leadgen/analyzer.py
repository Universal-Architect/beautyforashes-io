"""
FaithVision Lead Generation System
analyzer.py — Deep-analysis engine using Pastor Anderson / FaithVision positioning.
Returns inferred problems, detected assets, opportunity signals, and service routes.
Local only. No external calls.
"""

from __future__ import annotations

from typing import Dict, Any, List, Tuple

from leadgen.models import Lead, RECOMMENDED_SERVICES


# ── Service route decision tree ───────────────────────────────────────────────

SERVICE_ROUTES = {
    "Gift Discovery / Personal Calling Session": {
        "types": {"individual", "ministry"},
        "keywords": ["purpose", "calling", "gift", "lost", "direction", "identity",
                     "passion", "career", "pivot", "meaning", "vision", "clarity"],
    },
    "Nonprofit Solvency Review": {
        "types": {"nonprofit", "ministry"},
        "keywords": ["insolvent", "debt", "deficit", "funding", "cash flow", "grant",
                     "survival", "restructure", "board", "budget", "shortfall"],
    },
    "Hidden Asset & Revenue Stream Audit": {
        "types": {"nonprofit", "for_profit", "ministry", "individual"},
        "keywords": ["hidden", "asset", "real estate", "property", "ip", "brand",
                     "untapped", "underutilized", "inventory", "license", "dormant",
                     "revenue stream", "monetize", "latent"],
    },
    "Executive Strategic Advisory": {
        "types": {"for_profit", "nonprofit"},
        "keywords": ["strategy", "ceo", "executive", "board", "expansion", "pivot",
                     "repositioning", "leadership", "turnaround", "growth", "scale"],
    },
    "Enterprise Transformation Engagement": {
        "types": {"for_profit"},
        "keywords": ["transformation", "enterprise", "restructure", "culture",
                     "merger", "acquisition", "systemic", "rebuild", "overhaul"],
    },
    "Speaking / Workshop Inquiry": {
        "types": {"for_profit", "nonprofit", "ministry", "individual"},
        "keywords": ["speaker", "workshop", "training", "conference", "keynote",
                     "seminar", "event", "team", "retreat", "professional development"],
    },
    "Book / FaithVision Resource Path": {
        "types": {"individual", "ministry", "nonprofit"},
        "keywords": ["book", "resource", "read", "self-help", "learning", "guide",
                     "devotional", "faith", "spiritual", "development"],
    },
}


# ── Asset detection signals ───────────────────────────────────────────────────

ASSET_SIGNALS = {
    "Real Estate / Property": ["real estate", "property", "building", "land", "office",
                                "warehouse", "facility", "campus"],
    "Intellectual Property": ["ip", "intellectual property", "patent", "trademark",
                              "copyright", "brand name", "proprietary"],
    "Audience / Donor List": ["subscribers", "email list", "donor list", "mailing list",
                               "congregation", "followers", "membership"],
    "Equipment / Inventory": ["equipment", "machinery", "inventory", "fleet", "stock",
                              "tools", "technology", "hardware"],
    "Data / Database": ["database", "data", "records", "crm", "customer list", "contacts"],
    "Licensing / Certifications": ["license", "certification", "accreditation",
                                   "permit", "franchise", "contract"],
    "Digital Assets": ["website", "domain", "app", "software", "platform", "social media"],
}


# ── Distress signal detection ─────────────────────────────────────────────────

DISTRESS_SIGNALS = {
    "Cash Flow Crisis": ["cash flow", "no cash", "can't make payroll", "negative cash",
                         "out of money", "broke", "overdraft"],
    "Debt / Insolvency": ["debt", "owed", "insolvent", "bankruptcy", "behind on payments",
                          "creditors", "collections", "defaulted"],
    "Revenue Decline": ["revenue drop", "losing clients", "churn", "declining sales",
                        "shrinking", "fewer customers", "revenue down"],
    "Leadership Gap": ["no leader", "ceo left", "executive vacancy", "direction",
                       "no vision", "lost focus", "leadership crisis"],
    "Funding Shortfall": ["grant expired", "funding cut", "no funding", "donor loss",
                          "budget cut", "underfunded", "deficit"],
    "Mission Drift": ["lost mission", "off track", "identity crisis", "purpose lost",
                      "no alignment", "drifting"],
}


# ── Opportunity signal detection ──────────────────────────────────────────────

OPPORTUNITY_SIGNALS = {
    "Unexplored Revenue Streams": ["untapped", "not monetized", "could sell", "potential",
                                   "latent", "new product", "service line"],
    "Asset Underutilization": ["idle", "unused", "underutilized", "sitting on",
                               "dormant", "not using"],
    "Market Position Opportunity": ["first mover", "unique", "niche", "competitive advantage",
                                    "market gap", "underserved"],
    "Strategic Partnership Potential": ["partnership", "alliance", "joint venture",
                                        "collaboration", "network"],
    "Digital Transformation": ["go digital", "online", "e-commerce", "digital presence",
                               "automation", "tech upgrade"],
    "Leadership Development": ["new leader", "succession", "mentorship", "team building",
                               "culture", "coaching"],
}


# ── Inferred problem logic ────────────────────────────────────────────────────

def _infer_problem(lead: Lead) -> str:
    """Generate an inferred problem statement based on lead data."""
    text = (lead.stated_problem + " " + lead.notes + " " + lead.sector).lower()
    inferences = []

    if lead.lead_type == "individual":
        if any(kw in text for kw in ["stuck", "lost", "uncertain", "searching", "transition"]):
            inferences.append(
                "This individual appears to be at a crossroads — searching for direction, "
                "purpose clarity, or a new calling. A Gift Discovery / Calling Session "
                "could surface latent strengths and a monetizable vision."
            )
        else:
            inferences.append(
                "Individual lead with potential unrecognized gifts or income-generating capabilities "
                "tied to their unique calling and life experience."
            )

    if lead.lead_type in ("nonprofit", "ministry"):
        if any(kw in text for kw in ["funding", "debt", "budget", "cut", "deficit"]):
            inferences.append(
                "This organization shows signs of financial distress — likely relying on a single "
                "funding source or experiencing donor fatigue. A Solvency Review and hidden-asset "
                "audit may reveal dormant revenue streams or underutilized assets."
            )
        else:
            inferences.append(
                "Nonprofit/ministry entity that may benefit from strategic repositioning, "
                "donor diversification, or asset-to-cash conversion strategies."
            )

    if lead.lead_type == "for_profit":
        if any(kw in text for kw in ["revenue", "profit", "growth", "expand"]):
            inferences.append(
                "For-profit entity with stated growth ambitions but potentially blind to hidden "
                "value sitting in underutilized assets, underdeveloped revenue lines, or "
                "untapped market positions."
            )
        else:
            inferences.append(
                "For-profit company that may be experiencing margin compression, strategic drift, "
                "or cash-flow challenges addressable through executive advisory and revenue auditing."
            )

    return " | ".join(inferences) if inferences else (
        "Insufficient data for deep inference. Gather more context before outreach."
    )


def _detect_assets(lead: Lead) -> List[str]:
    text = (lead.stated_problem + " " + lead.notes + " " + lead.sector + " " +
            " ".join(lead.assets_detected)).lower()
    detected = []
    for asset_type, keywords in ASSET_SIGNALS.items():
        if any(kw in text for kw in keywords):
            detected.append(asset_type)
    return list(dict.fromkeys(detected))  # deduplicate, preserve order


def _detect_distress(lead: Lead) -> List[str]:
    text = (lead.stated_problem + " " + lead.notes + " " +
            " ".join(lead.distress_signals)).lower()
    detected = []
    for signal_type, keywords in DISTRESS_SIGNALS.items():
        if any(kw in text for kw in keywords):
            detected.append(signal_type)
    return list(dict.fromkeys(detected))


def _detect_opportunities(lead: Lead) -> List[str]:
    text = (lead.stated_problem + " " + lead.notes + " " + lead.inferred_problem + " " +
            " ".join(lead.opportunity_signals)).lower()
    detected = []
    for opp_type, keywords in OPPORTUNITY_SIGNALS.items():
        if any(kw in text for kw in keywords):
            detected.append(opp_type)
    return list(dict.fromkeys(detected))


def _select_service_route(lead: Lead) -> str:
    """Choose the best-fit service route for this lead."""
    text = (lead.stated_problem + " " + lead.inferred_problem + " " +
            lead.notes + " " + lead.sector).lower()

    if lead.lead_type in {"nonprofit", "ministry"}:
        solvency_keywords = SERVICE_ROUTES["Nonprofit Solvency Review"]["keywords"]
        if lead.distress_signals or any(kw in text for kw in solvency_keywords):
            return "Nonprofit Solvency Review"

    best_service = "None / Insufficient Data"
    best_hits = 0
    for service, config in SERVICE_ROUTES.items():
        if lead.lead_type not in config["types"] and "all" not in config["types"]:
            continue
        hits = sum(1 for kw in config["keywords"] if kw in text)
        if hits > best_hits:
            best_hits = hits
            best_service = service
    return best_service


def _suggest_next_step(lead: Lead, service: str) -> str:
    """Generate a concrete next-step recommendation."""
    steps = {
        "Gift Discovery / Personal Calling Session": (
            "Draft a personal intro email inviting this individual to a complimentary "
            "30-minute Gift Discovery call with Pastor Anderson. Highlight transformation stories. "
            "Require owner approval before sending."
        ),
        "Nonprofit Solvency Review": (
            "Prepare a Nonprofit Solvency Review proposal. Outline a 3-phase engagement: "
            "(1) Financial Health Audit, (2) Asset Discovery, (3) Revenue Diversification Plan. "
            "Present to owner for approval before outreach."
        ),
        "Hidden Asset & Revenue Stream Audit": (
            "Draft an audit proposal detailing how FaithVision identifies dormant assets and "
            "unexploited revenue channels. Include 2–3 relevant case analogies. "
            "Owner review required."
        ),
        "Executive Strategic Advisory": (
            "Prepare a confidential executive briefing document on strategic repositioning. "
            "Request a 45-minute strategy call. Draft intro email for owner approval."
        ),
        "Enterprise Transformation Engagement": (
            "Initiate a discovery call request. Frame as a confidential transformation assessment. "
            "Prepare a capability overview. All outreach requires owner sign-off."
        ),
        "Speaking / Workshop Inquiry": (
            "Draft a speaking engagement overview or workshop proposal. Send inquiry to "
            "event coordinator — after owner approval."
        ),
        "Book / FaithVision Resource Path": (
            "Draft a resource recommendation email with relevant FaithVision materials. "
            "Low-commitment entry point. Owner approval before any send."
        ),
    }
    return steps.get(service, "Gather additional information before determining next step.")


# ── Main analysis function ────────────────────────────────────────────────────

def analyze_lead(lead: Lead) -> Dict[str, Any]:
    """
    Run full FaithVision analysis on a lead.
    Updates lead fields in-place. Returns a summary dict.
    """
    # Infer problem
    if not lead.inferred_problem:
        lead.inferred_problem = _infer_problem(lead)

    # Detect signals
    new_assets = _detect_assets(lead)
    for a in new_assets:
        if a not in lead.assets_detected:
            lead.assets_detected.append(a)

    new_distress = _detect_distress(lead)
    for d in new_distress:
        if d not in lead.distress_signals:
            lead.distress_signals.append(d)

    new_opps = _detect_opportunities(lead)
    for o in new_opps:
        if o not in lead.opportunity_signals:
            lead.opportunity_signals.append(o)

    # Service route
    service = _select_service_route(lead)
    lead.recommended_service = service

    # Next step
    next_step = _suggest_next_step(lead, service)
    lead.recommended_next_step = next_step

    lead.touch()

    return {
        "lead_id": lead.lead_id,
        "lead_type": lead.lead_type,
        "name_org": lead.name or lead.organization,
        "inferred_problem": lead.inferred_problem,
        "assets_detected": lead.assets_detected,
        "distress_signals": lead.distress_signals,
        "opportunity_signals": lead.opportunity_signals,
        "recommended_service": service,
        "recommended_next_step": next_step,
    }
