"""
FaithVision Lead Generation System
scoring.py — Multi-dimensional lead scoring engine.
Returns 0-100 total score, tier, explanation, and recommended action.
Local only. No external calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List

from leadgen.models import Lead, TIERS


# ── Dimension weights (must sum to 1.0) ──────────────────────────────────────

WEIGHTS: Dict[str, float] = {
    "gift_development_fit":      0.15,
    "solvency_restructuring":    0.15,
    "hidden_asset_potential":    0.15,
    "revenue_expansion":         0.15,
    "urgency":                   0.12,
    "ability_to_pay":            0.10,
    "mission_alignment":         0.10,
    "ethical_compliance_risk":   0.08,   # inverse — high risk lowers score
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-6, "Weights must sum to 1.0"


# ── Tier thresholds ───────────────────────────────────────────────────────────

TIER_THRESHOLDS = [
    (85, "executive"),
    (70, "priority"),
    (50, "qualified"),
    (30, "watch"),
    (0,  "low"),
]


@dataclass
class ScoreResult:
    total_score: float = 0.0
    tier: str = "low"
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    explanation: str = ""
    recommended_action: str = ""
    flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_score": round(self.total_score, 2),
            "tier": self.tier,
            "dimension_scores": {k: round(v, 2) for k, v in self.dimension_scores.items()},
            "explanation": self.explanation,
            "recommended_action": self.recommended_action,
            "flags": self.flags,
        }


# ── Individual dimension scorers ──────────────────────────────────────────────

def _score_gift_development_fit(lead: Lead) -> tuple[float, list[str]]:
    """How well does this person/org fit gift/purpose/calling development work?"""
    score = 0.0
    flags = []
    if lead.lead_type == "individual":
        score += 40.0
        flags.append("Individual — primary candidate for gift development.")
    if lead.lead_type == "ministry":
        score += 30.0
        flags.append("Ministry — strong fit for leadership and calling sessions.")
    keywords = ["purpose", "calling", "gift", "ministry", "passion", "vocation",
                "identity", "direction", "vision", "mission"]
    text = (lead.stated_problem + " " + lead.inferred_problem + " " + lead.notes).lower()
    hits = [kw for kw in keywords if kw in text]
    score += min(len(hits) * 6.0, 60.0)
    if hits:
        flags.append(f"Gift-fit keywords detected: {', '.join(hits[:5])}.")
    return min(score, 100.0), flags


def _score_solvency_restructuring(lead: Lead) -> tuple[float, list[str]]:
    """How urgently does this entity need solvency, restructuring, or financial repair?"""
    score = 0.0
    flags = []
    if lead.lead_type in ("nonprofit", "for_profit"):
        score += 20.0
    distress_keywords = ["insolvent", "debt", "deficit", "deficits", "bankruptcy", "shutdown",
                         "cash flow", "struggling", "behind", "owed", "restructure",
                         "survival", "closure", "underfunded", "negative", "reserves",
                         "runway", "payroll", "shortfall"]
    text = (" ".join(lead.distress_signals) + " " + lead.stated_problem + " " +
            lead.inferred_problem).lower()
    hits = [kw for kw in distress_keywords if kw in text]
    score += min(len(hits) * 8.0, 80.0)
    if hits:
        flags.append(f"Solvency/distress signals: {', '.join(hits[:5])}.")
    return min(score, 100.0), flags


def _score_hidden_asset_potential(lead: Lead) -> tuple[float, list[str]]:
    """Does this entity have discoverable hidden value, untapped assets?"""
    score = 0.0
    flags = []
    asset_keywords = ["real estate", "property", "ip", "intellectual property", "brand",
                      "database", "list", "inventory", "equipment", "license", "trademark",
                      "patent", "land", "building", "subscriber", "audience", "donor list"]
    text = (" ".join(lead.assets_detected) + " " + lead.stated_problem + " " +
            lead.inferred_problem).lower()
    hits = [kw for kw in asset_keywords if kw in text]
    score += min(len(hits) * 10.0, 70.0)
    if hits:
        flags.append(f"Potential hidden assets: {', '.join(hits[:5])}.")
    if lead.assets_detected:
        score += 20.0
        flags.append(f"{len(lead.assets_detected)} asset(s) explicitly listed.")
    return min(score, 100.0), flags


def _score_revenue_expansion(lead: Lead) -> tuple[float, list[str]]:
    """How much revenue expansion opportunity exists?"""
    score = 0.0
    flags = []
    if lead.lead_type in ("for_profit", "nonprofit"):
        score += 20.0
    rev_keywords = ["revenue", "sales", "income", "monetize", "expand", "scale",
                    "growth", "diversify", "new market", "product", "service line",
                    "pricing", "margin", "profit"]
    text = (" ".join(lead.revenue_streams_detected) + " " + lead.stated_problem + " " +
            " ".join(lead.opportunity_signals)).lower()
    hits = [kw for kw in rev_keywords if kw in text]
    score += min(len(hits) * 6.0, 60.0)
    if lead.revenue_streams_detected:
        score += 10.0
        flags.append(f"{len(lead.revenue_streams_detected)} revenue stream(s) detected.")
    if hits:
        flags.append(f"Revenue keywords: {', '.join(hits[:5])}.")
    return min(score, 100.0), flags


def _score_urgency(lead: Lead) -> tuple[float, list[str]]:
    """How urgent is the lead's situation?"""
    score = lead.urgency_score  # Caller-supplied urgency hint (0–100)
    flags = []
    urgency_words = ["urgent", "immediately", "critical", "now", "asap", "crisis",
                     "emergency", "failing", "imminent", "closing", "desperate"]
    text = (lead.stated_problem + " " + " ".join(lead.distress_signals)).lower()
    hits = [w for w in urgency_words if w in text]
    boost = min(len(hits) * 8.0, 40.0)
    score = min(score + boost, 100.0)
    if hits:
        flags.append(f"Urgency indicators: {', '.join(hits[:4])}.")
    return score, flags


def _score_ability_to_pay(lead: Lead) -> tuple[float, list[str]]:
    """Rough proxy for ability to engage paid advisory services."""
    score = 30.0  # base — unknown entities get a moderate starting point
    flags = []
    pay_positive = ["revenue", "funding", "grant", "endowment", "investment",
                    "profitable", "growth", "enterprise", "established", "assets"]
    pay_negative = ["bankrupt", "volunteer only", "no budget", "pro bono",
                    "insolvent", "no revenue", "startup"]
    text = (lead.stated_problem + " " + lead.inferred_problem + " " + lead.notes).lower()
    pos_hits = [kw for kw in pay_positive if kw in text]
    neg_hits = [kw for kw in pay_negative if kw in text]
    score += len(pos_hits) * 8.0
    score -= len(neg_hits) * 12.0
    score = max(0.0, min(score, 100.0))
    if pos_hits:
        flags.append(f"Pay-positive signals: {', '.join(pos_hits[:3])}.")
    if neg_hits:
        flags.append(f"Pay-risk signals: {', '.join(neg_hits[:3])}.")
    return score, flags


def _score_mission_alignment(lead: Lead) -> tuple[float, list[str]]:
    """How well does this lead align with FaithVision's faith-centered mission?"""
    score = 20.0  # baseline — everyone can benefit
    flags = []
    faith_keywords = ["faith", "church", "ministry", "christian", "pastor", "gospel",
                      "nonprofit", "community", "purpose", "kingdom", "spiritual",
                      "values", "mission", "serving", "underserved"]
    text = (lead.sector + " " + lead.stated_problem + " " + lead.notes +
            " " + lead.organization).lower()
    hits = [kw for kw in faith_keywords if kw in text]
    score += min(len(hits) * 8.0, 80.0)
    if hits:
        flags.append(f"Mission alignment terms: {', '.join(hits[:5])}.")
    return min(score, 100.0), flags


def _score_ethical_compliance_risk(lead: Lead) -> tuple[float, list[str]]:
    """
    Ethical/compliance risk dimension — HIGH risk LOWERS the composite score.
    Returns a risk score (0–100); will be inverted in weighting.
    """
    risk = 0.0
    flags = []
    risk_keywords = ["litigation", "lawsuit", "fraud", "scam", "predatory", "illegal",
                     "sanctioned", "debarred", "pyramid", "mlm", "ponzi",
                     "money laundering", "irs hold", "tax lien"]
    text = (lead.stated_problem + " " + lead.notes + " " + lead.inferred_problem).lower()
    hits = [kw for kw in risk_keywords if kw in text]
    risk += min(len(hits) * 15.0, 100.0)
    if hits:
        flags.append(f"⚠ Ethical/compliance risk flags: {', '.join(hits[:4])}.")
    return risk, flags


# ── Main scoring function ─────────────────────────────────────────────────────

def score_lead(lead: Lead) -> ScoreResult:
    """
    Score a lead across all dimensions. Returns a ScoreResult.
    Updates the lead in-place (scores, tier, explanation).
    """
    all_flags: list[str] = []
    dim_scores: Dict[str, float] = {}

    gift_score,   f1 = _score_gift_development_fit(lead)
    solvency,     f2 = _score_solvency_restructuring(lead)
    asset_score,  f3 = _score_hidden_asset_potential(lead)
    revenue,      f4 = _score_revenue_expansion(lead)
    urgency,      f5 = _score_urgency(lead)
    pay_ability,  f6 = _score_ability_to_pay(lead)
    mission,      f7 = _score_mission_alignment(lead)
    ethics_risk,  f8 = _score_ethical_compliance_risk(lead)

    all_flags.extend(f1 + f2 + f3 + f4 + f5 + f6 + f7 + f8)

    dim_scores = {
        "gift_development_fit":    gift_score,
        "solvency_restructuring":  solvency,
        "hidden_asset_potential":  asset_score,
        "revenue_expansion":       revenue,
        "urgency":                 urgency,
        "ability_to_pay":          pay_ability,
        "mission_alignment":       mission,
        "ethical_compliance_risk": ethics_risk,
    }

    # Compute weighted composite (ethics_risk is inverted)
    composite = (
        gift_score   * WEIGHTS["gift_development_fit"] +
        solvency     * WEIGHTS["solvency_restructuring"] +
        asset_score  * WEIGHTS["hidden_asset_potential"] +
        revenue      * WEIGHTS["revenue_expansion"] +
        urgency      * WEIGHTS["urgency"] +
        pay_ability  * WEIGHTS["ability_to_pay"] +
        mission      * WEIGHTS["mission_alignment"] +
        (100.0 - ethics_risk) * WEIGHTS["ethical_compliance_risk"]
    )

    total = round(min(max(composite, 0.0), 100.0), 2)

    # Determine tier
    tier = "low"
    for threshold, label in TIER_THRESHOLDS:
        if total >= threshold:
            tier = label
            break

    # Build explanation
    explanation = _build_explanation(lead, total, tier, dim_scores, all_flags)
    recommended_action = _recommend_action(tier, lead)

    # Update lead in-place
    lead.fit_score = dim_scores["gift_development_fit"]
    lead.urgency_score = dim_scores["urgency"]
    lead.value_creation_score = max(dim_scores["hidden_asset_potential"],
                                    dim_scores["revenue_expansion"])
    lead.total_score = total
    lead.tier = tier
    lead.score_explanation = explanation
    lead.touch()

    return ScoreResult(
        total_score=total,
        tier=tier,
        dimension_scores=dim_scores,
        explanation=explanation,
        recommended_action=recommended_action,
        flags=all_flags,
    )


def _build_explanation(lead: Lead, total: float, tier: str,
                        dim: Dict[str, float], flags: list[str]) -> str:
    lines = [
        f"FaithVision Scoring Report — {lead.name or lead.organization or lead.lead_id}",
        f"Lead Type: {lead.lead_type.upper()} | Total Score: {total:.1f}/100 | Tier: {tier.upper()}",
        "",
        "Dimension Breakdown:",
    ]
    for key, score in dim.items():
        label = key.replace("_", " ").title()
        lines.append(f"  {label}: {score:.1f}")
    lines.append("")
    if flags:
        lines.append("Key Observations:")
        for flag in flags[:10]:
            lines.append(f"  • {flag}")
    lines.append("")
    lines.append(
        "Positioning Note: Pastor Anderson / FaithVision specializes in uncovering hidden value, "
        "restoring financial health, and aligning organizational purpose with sustainable growth. "
        "This lead has been evaluated for fit across gift development, solvency, asset discovery, "
        "and revenue expansion dimensions."
    )
    return "\n".join(lines)


def _recommend_action(tier: str, lead: Lead) -> str:
    if tier == "executive":
        return ("Schedule an Executive Strategic Advisory call immediately. "
                "Prepare a personalized proposal. Prioritize direct outreach after owner approval.")
    if tier == "priority":
        return ("Draft a warm first-touch email within 48 hours (owner approval required). "
                "Prepare a Hidden Asset & Revenue Stream Audit proposal.")
    if tier == "qualified":
        return ("Add to watch queue. Draft a first-touch email for owner review. "
                "Recommend a Nonprofit Solvency Review or Gift Discovery Session as appropriate.")
    if tier == "watch":
        return ("Monitor. Gather more information. Draft a soft-touch intro for later owner review.")
    return ("Low priority. File for future reference. No immediate action recommended.")
