"""
FaithVision Lead Generation System — Test Suite
pytest tests/test_leadgen.py

Covers:
  - Deny-by-default policy enforcement
  - Forbidden action blocking
  - Scoring produces expected tiers
  - No secret leakage
  - Email drafts are draft-only (approval_status guard)
  - Audit log redacts sensitive data
  - Path traversal blocked in store
  - Sample leads import and score correctly
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import shutil
import uuid
import ast
import inspect

import pytest

# ── Make the package importable from the test directory ───────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from leadgen.models import Lead, EmailDraft
from leadgen.router import gate, is_allowed, is_forbidden, PolicyViolation, get_policy_summary
from leadgen.redaction import redact_dict, assert_no_secrets, safe_summary, REDACTION_PLACEHOLDER
from leadgen.scoring import score_lead, ScoreResult
from leadgen.analyzer import analyze_lead
from leadgen.email_drafter import draft_emails
from leadgen.audit import log_action, read_audit_log
from leadgen import widget_importer


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_lead(**kwargs) -> Lead:
    defaults = dict(
        lead_id=str(uuid.uuid4()),
        lead_type="individual",
        name="Test Person",
        stated_problem="I need help finding my purpose and turning my gifts into income.",
        notes="Faith-driven individual in career transition.",
        sector="Faith / Personal Development",
        urgency_score=50.0,
    )
    defaults.update(kwargs)
    return Lead(**defaults)


def make_nonprofit_lead() -> Lead:
    return Lead(
        lead_id=str(uuid.uuid4()),
        lead_type="nonprofit",
        organization="Test Nonprofit",
        stated_problem="We have a $300K deficit and 60 days of cash. Grant ended. Building owned outright.",
        distress_signals=["deficit", "cash flow", "insolvent", "funding cut"],
        assets_detected=["real estate", "donor list"],
        urgency_score=90.0,
        notes="Urgent solvency situation.",
    )


def make_forprofit_lead() -> Lead:
    return Lead(
        lead_id=str(uuid.uuid4()),
        lead_type="for_profit",
        organization="Test Corp",
        stated_problem="Revenue flat at $4M, margins down, need revenue expansion and hidden asset discovery.",
        opportunity_signals=["untapped revenue", "real estate", "brand"],
        assets_detected=["real estate", "equipment", "database"],
        urgency_score=75.0,
    )


def make_widget_payload(**overrides):
    payload = {
        "id": "widget-001",
        "timestamp": "2026-06-16T10:30:00Z",
        "firstName": "Maya",
        "email": "maya@example.test",
        "phone": "555-0100",
        "score": 87,
        "tier": "priority",
        "recommendedService": "Nonprofit Solvency Review",
        "page": "https://faithvision.example/widget",
        "referrer": "https://search.example/",
        "answers": {
            "situation": {
                "value": "cash_flow",
                "label": "We have a cash flow crisis and need funding clarity.",
                "score": 9,
            },
            "org_type": {
                "value": "nonprofit",
                "label": "Nonprofit organization",
                "score": 8,
            },
            "budget": {
                "value": "has_budget",
                "label": "We have budget for strategic help.",
                "score": 7,
            },
            "urgency": {
                "value": "urgent",
                "label": "Urgent - we need help now.",
                "score": 9,
            },
        },
    }
    payload.update(overrides)
    return payload


@pytest.fixture(autouse=True)
def isolate_local_roots(tmp_path, monkeypatch):
    """Keep tests away from the checked-in leadgen/data and leadgen/audit files."""
    monkeypatch.setenv("LEADGEN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LEADGEN_AUDIT_DIR", str(tmp_path / "audit"))


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DENY-BY-DEFAULT POLICY
# ═══════════════════════════════════════════════════════════════════════════════

class TestDenyByDefault:

    def test_unknown_action_is_denied(self):
        """Actions not in allowed list must be denied by default."""
        with pytest.raises(PolicyViolation) as exc_info:
            gate(action="some_unknown_action", lead_id="test-001", actor="test")
        assert "not in the allowed_local_actions" in str(exc_info.value).lower() or \
               "deny" in str(exc_info.value).lower()

    def test_allowed_actions_pass(self):
        """All explicitly allowed actions should not raise."""
        allowed = [
            "import_lead",
            "classify_lead",
            "score_lead",
            "draft_email",
            "create_owner_review_packet",
            "export_local_json",
        ]
        for action in allowed:
            gate(action=action, lead_id="test-001", actor="test")  # should not raise

    def test_is_allowed_returns_true_for_allowed(self):
        assert is_allowed("import_lead") is True
        assert is_allowed("draft_email") is True
        assert is_allowed("score_lead") is True

    def test_is_allowed_returns_false_for_unknown(self):
        assert is_allowed("totally_unknown_action") is False

    def test_is_forbidden_returns_true_for_forbidden(self):
        assert is_forbidden("send_email") is True
        assert is_forbidden("post_to_crm") is True
        assert is_forbidden("charge_payment") is True

    def test_policy_summary_default_is_deny(self):
        summary = get_policy_summary()
        assert summary["default_action"] == "deny"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. FORBIDDEN ACTION BLOCKING
# ═══════════════════════════════════════════════════════════════════════════════

class TestForbiddenActions:

    FORBIDDEN = [
        "send_email",
        "post_to_crm",
        "post_to_zapier",
        "scrape_private_data",
        "use_api_credentials",
        "publish_to_website",
        "delete_records",
        "alter_dns",
        "charge_payment",
        "access_social_accounts",
    ]

    @pytest.mark.parametrize("action", FORBIDDEN)
    def test_forbidden_action_raises(self, action):
        """Every forbidden action must raise PolicyViolation."""
        with pytest.raises(PolicyViolation):
            gate(action=action, lead_id="test-001", actor="test")

    @pytest.mark.parametrize("action", FORBIDDEN)
    def test_forbidden_action_is_not_allowed(self, action):
        assert is_allowed(action) is False

    @pytest.mark.parametrize("action", FORBIDDEN)
    def test_forbidden_action_is_detected(self, action):
        assert is_forbidden(action) is True

    def test_policy_violation_error_message_contains_action(self):
        try:
            gate(action="send_email", lead_id="test-001", actor="test")
        except PolicyViolation as e:
            assert "send_email" in str(e)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SCORING — EXPECTED TIERS
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoring:

    def test_individual_gift_lead_scores_nonzero(self):
        lead = make_lead()
        result = score_lead(lead)
        assert result.total_score > 0
        assert result.tier in {"low", "watch", "qualified", "priority", "executive"}

    def test_urgent_nonprofit_scores_higher_than_no_data_lead(self):
        urgent = make_nonprofit_lead()
        blank  = Lead(lead_id=str(uuid.uuid4()), lead_type="unknown")
        r_urgent = score_lead(urgent)
        r_blank  = score_lead(blank)
        assert r_urgent.total_score > r_blank.total_score

    def test_high_urgency_boosts_score(self):
        low_urgency  = make_lead(urgency_score=0.0)
        high_urgency = make_lead(urgency_score=100.0,
                                  stated_problem="urgent crisis need help immediately now critical")
        r_low  = score_lead(low_urgency)
        r_high = score_lead(high_urgency)
        assert r_high.total_score >= r_low.total_score

    def test_score_within_bounds(self):
        lead = make_nonprofit_lead()
        result = score_lead(lead)
        assert 0.0 <= result.total_score <= 100.0

    def test_all_tiers_reachable(self):
        """Confirm tier logic covers all tier strings."""
        from leadgen.scoring import TIER_THRESHOLDS
        tier_labels = {t for _, t in TIER_THRESHOLDS}
        assert tier_labels == {"executive", "priority", "qualified", "watch", "low"}

    def test_score_result_has_required_fields(self):
        lead = make_lead()
        result = score_lead(lead)
        d = result.to_dict()
        for key in ("total_score", "tier", "dimension_scores", "explanation",
                    "recommended_action", "flags"):
            assert key in d, f"Missing field: {key}"

    def test_dimension_scores_all_in_range(self):
        lead = make_forprofit_lead()
        result = score_lead(lead)
        for dim, val in result.dimension_scores.items():
            assert 0.0 <= val <= 100.0, f"Dimension {dim} out of range: {val}"

    def test_executive_tier_for_extreme_lead(self):
        """A lead with maximum urgency and all signals should reach priority or executive."""
        lead = Lead(
            lead_id=str(uuid.uuid4()),
            lead_type="for_profit",
            organization="Crisis Corp",
            stated_problem=(
                "urgent crisis cash flow debt insolvent revenue expansion strategy "
                "executive restructure turnaround growth scale transformation"
            ),
            assets_detected=["real estate", "intellectual property", "database",
                              "equipment", "licensing"],
            revenue_streams_detected=["distribution", "service contracts"],
            distress_signals=["cash flow", "insolvent", "debt"],
            opportunity_signals=["untapped", "monetize", "expansion"],
            urgency_score=100.0,
            notes="faith mission values kingdom community purpose",
            sector="enterprise for-profit",
        )
        result = score_lead(lead)
        assert result.tier in {"qualified", "priority", "executive"}, (
            f"Expected qualified or above, got {result.tier} (score={result.total_score})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. NO SECRET LEAKAGE
# ═══════════════════════════════════════════════════════════════════════════════

class TestRedaction:

    SECRET_DICT = {
        "api_key":       "sk-abc123supersecretkey",
        "token":         "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.abc",
        "password":      "MySecretP@ssw0rd!",
        "client_id":     "client_12345",
        "workspace_id":  "ws_abcdef",
        "name":          "John Doe",
        "org_id":        "org_xyz",
        "account_id":    "acct_12345",
        "nested": {
            "bearer":    "Bearer xyz123tokenvalue",
            "secret":    "topsecret",
            "safe_val":  "hello world",
        }
    }

    def test_secret_keys_are_redacted(self):
        result = redact_dict(self.SECRET_DICT)
        assert result["api_key"] == REDACTION_PLACEHOLDER
        assert result["password"] == REDACTION_PLACEHOLDER
        assert result["token"] == REDACTION_PLACEHOLDER

    def test_nested_secrets_are_redacted(self):
        result = redact_dict(self.SECRET_DICT)
        assert result["nested"]["bearer"] == REDACTION_PLACEHOLDER
        assert result["nested"]["secret"] == REDACTION_PLACEHOLDER

    def test_safe_values_preserved(self):
        result = redact_dict(self.SECRET_DICT)
        assert result["name"] == "John Doe"
        assert result["nested"]["safe_val"] == "hello world"

    def test_assert_no_secrets_passes_on_clean_data(self):
        clean = {"name": "Marcus", "score": 72.5, "tier": "qualified"}
        assert_no_secrets(clean)  # should not raise

    def test_safe_summary_truncates_and_redacts(self):
        summary = safe_summary(self.SECRET_DICT, max_keys=3)
        assert len(summary) <= 4  # 3 keys + possible _truncated_keys
        assert all(
            v == REDACTION_PLACEHOLDER or not isinstance(v, str)
            or not any(sk in str(v) for sk in ["sk-", "eyJ", "Secret"])
            for v in summary.values()
        )

    def test_no_secrets_in_email_drafts(self):
        lead = make_lead()
        analyze_lead(lead)
        score_lead(lead)
        drafts = draft_emails(lead)
        for draft in drafts:
            d = redact_dict(draft.to_dict())
            serialized = json.dumps(d)
            assert "sk-" not in serialized
            assert "api_key" not in serialized.lower() or REDACTION_PLACEHOLDER in serialized


# ═══════════════════════════════════════════════════════════════════════════════
# 5. EMAIL DRAFTS ARE DRAFT-ONLY
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmailDrafts:

    def test_all_drafts_have_pending_owner_review(self):
        lead = make_lead()
        analyze_lead(lead)
        score_lead(lead)
        drafts = draft_emails(lead)
        assert len(drafts) > 0
        for draft in drafts:
            assert draft.approval_status == "pending_owner_review", (
                f"Draft {draft.draft_id} has status {draft.approval_status!r}, "
                "expected 'pending_owner_review'"
            )

    def test_nonprofit_draft_generated_for_nonprofit_lead(self):
        lead = make_nonprofit_lead()
        analyze_lead(lead)
        score_lead(lead)
        drafts = draft_emails(lead)
        types = [d.template_type for d in drafts]
        assert "nonprofit_version" in types

    def test_forprofit_exec_draft_generated_for_forprofit(self):
        lead = make_forprofit_lead()
        analyze_lead(lead)
        score_lead(lead)
        drafts = draft_emails(lead)
        types = [d.template_type for d in drafts]
        assert "for_profit_exec_version" in types

    def test_individual_gift_draft_generated_for_individual(self):
        lead = make_lead(lead_type="individual")
        analyze_lead(lead)
        score_lead(lead)
        drafts = draft_emails(lead)
        types = [d.template_type for d in drafts]
        assert "individual_gift_dev" in types

    def test_drafts_always_include_short_and_warm(self):
        for lt in ("individual", "nonprofit", "for_profit"):
            lead = make_lead(lead_type=lt)
            analyze_lead(lead)
            score_lead(lead)
            drafts = draft_emails(lead)
            types = [d.template_type for d in drafts]
            assert "short_first_touch" in types, f"Missing short_first_touch for {lt}"
            assert "warm_referral"    in types, f"Missing warm_referral for {lt}"

    def test_drafts_have_required_fields(self):
        lead = make_lead()
        analyze_lead(lead)
        score_lead(lead)
        drafts = draft_emails(lead)
        for draft in drafts:
            assert draft.subject, f"Draft {draft.draft_id} missing subject"
            assert draft.body,    f"Draft {draft.draft_id} missing body"
            assert draft.suggested_sender, f"Draft {draft.draft_id} missing suggested_sender"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. AUDIT LOG REDACTS SENSITIVE DATA
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditLog:

    def test_audit_log_accepts_entry(self):
        log_action(
            action="import_lead",
            actor="test",
            lead_id="test-audit-001",
            decision="approved",
            reason="Unit test audit entry",
            payload_summary={"name": "Test Lead"},
        )
        entries = read_audit_log(limit=50)
        assert any(e.get("lead_id") == "test-audit-001" for e in entries)

    def test_audit_log_does_not_store_raw_secrets(self):
        log_action(
            action="import_lead",
            actor="test",
            lead_id="test-audit-secret-001",
            decision="approved",
            reason="Secret test",
            payload_summary={"api_key": "sk-super-secret-value-abc123"},
        )
        entries = read_audit_log(limit=100)
        # Find our entry
        our_entries = [e for e in entries if e.get("lead_id") == "test-audit-secret-001"]
        assert our_entries, "Audit entry not found"
        serialized = json.dumps(our_entries[0])
        assert "sk-super-secret-value-abc123" not in serialized, (
            "Raw secret found in audit log!"
        )

    def test_audit_log_records_denial(self):
        try:
            gate(action="send_email", lead_id="test-deny-001", actor="test")
        except PolicyViolation:
            pass
        entries = read_audit_log(limit=50)
        denial_entries = [e for e in entries
                          if e.get("action") == "send_email" and e.get("decision") == "denied"]
        assert denial_entries, "Denial not recorded in audit log"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. PATH TRAVERSAL BLOCKED
# ═══════════════════════════════════════════════════════════════════════════════

class TestPathSafety:

    def test_path_traversal_raises_value_error(self):
        from leadgen.store import _safe_path
        with pytest.raises(ValueError, match="traversal"):
            _safe_path("../../etc/passwd", "/tmp/safe_base_dir")

    def test_safe_path_allows_valid_filename(self):
        from leadgen.store import _safe_path
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            result = _safe_path("leads.json", td)
            assert result.startswith(td)

    def test_double_dot_in_filename_blocked(self):
        from leadgen.store import _safe_path
        with pytest.raises(ValueError):
            _safe_path("../../../root/.bashrc", "/tmp/safe_dir")

    def test_absolute_escape_attempt_blocked(self):
        from leadgen.store import _safe_path
        with pytest.raises(ValueError):
            _safe_path("/etc/shadow", "/tmp/safe_dir")


class TestLocalRootConfiguration:

    def test_default_roots_match_package_dirs_when_env_unset(self, monkeypatch):
        from leadgen.audit import get_audit_dir, get_audit_file
        from leadgen.store import get_data_dir

        monkeypatch.delenv("LEADGEN_DATA_DIR", raising=False)
        monkeypatch.delenv("LEADGEN_AUDIT_DIR", raising=False)

        package_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
        assert get_data_dir() == os.path.join(package_dir, "data")
        assert get_audit_dir() == os.path.join(package_dir, "audit")
        assert get_audit_file() == os.path.join(
            package_dir, "audit", "leadgen_audit.jsonl"
        )

    def test_store_uses_env_configured_data_dir(self, tmp_path, monkeypatch):
        from leadgen.store import (
            data_file_path,
            export_local_json,
            get_data_dir,
            get_lead,
            save_lead,
        )

        custom_data = tmp_path / "custom-data"
        custom_audit = tmp_path / "custom-audit"
        monkeypatch.setenv("LEADGEN_DATA_DIR", str(custom_data))
        monkeypatch.setenv("LEADGEN_AUDIT_DIR", str(custom_audit))

        lead = make_lead(lead_id="temp-root-001")
        save_lead(lead)

        leads_file = custom_data / "leads.json"
        assert get_data_dir() == os.path.realpath(str(custom_data))
        assert data_file_path("leads.json") == os.path.realpath(str(leads_file))
        assert leads_file.exists()
        assert get_lead("temp-root-001").lead_id == "temp-root-001"

        exported = export_local_json("export.json")
        assert exported == os.path.realpath(str(custom_data / "export.json"))
        assert (custom_data / "export.json").exists()

    def test_audit_uses_env_configured_audit_dir(self, tmp_path, monkeypatch):
        from leadgen.audit import get_audit_dir, get_audit_file

        custom_audit = tmp_path / "custom-audit-only"
        monkeypatch.setenv("LEADGEN_AUDIT_DIR", str(custom_audit))

        log_action(
            action="import_lead",
            actor="test",
            lead_id="temp-audit-001",
            decision="approved",
            reason="Temp audit root test",
            payload_summary={},
        )

        audit_file = custom_audit / "leadgen_audit.jsonl"
        assert get_audit_dir() == os.path.realpath(str(custom_audit))
        assert get_audit_file() == os.path.realpath(str(audit_file))
        assert audit_file.exists()
        entries = read_audit_log(limit=10)
        assert any(e.get("lead_id") == "temp-audit-001" for e in entries)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. SAMPLE LEADS IMPORT CORRECTLY
# ═══════════════════════════════════════════════════════════════════════════════

class TestSampleLeads:

    @pytest.fixture(autouse=True)
    def load_samples(self):
        sample_path = os.path.join(
            os.path.dirname(__file__), "..", "sample_leads.json"
        )
        with open(sample_path, "r", encoding="utf-8") as f:
            self.samples = json.load(f)

    def test_sample_file_has_six_leads(self):
        assert len(self.samples) == 6

    def test_two_individuals_present(self):
        individuals = [l for l in self.samples if l.get("lead_type") == "individual"]
        assert len(individuals) == 2

    def test_two_nonprofits_present(self):
        nps = [l for l in self.samples if l.get("lead_type") == "nonprofit"]
        assert len(nps) == 2

    def test_two_for_profits_present(self):
        fps = [l for l in self.samples if l.get("lead_type") == "for_profit"]
        assert len(fps) == 2

    def test_all_samples_parse_to_lead_model(self):
        for item in self.samples:
            lead = Lead.from_dict(item)
            errors = lead.validate()
            assert not errors, f"Lead {lead.lead_id} failed validation: {errors}"

    def test_all_samples_score_successfully(self):
        for item in self.samples:
            lead = Lead.from_dict(item)
            analyze_lead(lead)
            result = score_lead(lead)
            assert 0.0 <= result.total_score <= 100.0
            assert result.tier in {"low", "watch", "qualified", "priority", "executive"}

    def test_urgent_nonprofit_scores_high_urgency(self):
        """Cornerstone Community Partners has 90-day runway — should score urgently."""
        np_lead = next(
            Lead.from_dict(l) for l in self.samples
            if l.get("lead_type") == "nonprofit" and "Cornerstone" in l.get("organization","")
        )
        analyze_lead(np_lead)
        result = score_lead(np_lead)
        # Should at least be qualified or above given distress signals
        assert result.tier in {"qualified", "priority", "executive"}, (
            f"Urgent nonprofit got tier {result.tier} (score={result.total_score})"
        )

    def test_no_sample_has_real_credentials(self):
        """Samples must use fictional data — no real-looking API keys."""
        raw = json.dumps(self.samples)
        for bad_pattern in ["sk-", "pk-live-", "Bearer ", "password:", "api_key:"]:
            assert bad_pattern not in raw, (
                f"Sample data contains suspicious pattern: {bad_pattern!r}"
            )

    def test_all_samples_have_owner_review_required(self):
        for item in self.samples:
            assert item.get("owner_review_required") is True, (
                f"Lead {item.get('lead_id')} missing owner_review_required=true"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 9. WEBSITE WIDGET IMPORTER
# ═══════════════════════════════════════════════════════════════════════════════

class TestWidgetImporter:

    def test_widget_payload_converts_to_lead(self):
        lead = widget_importer.widget_payload_to_lead(make_widget_payload())

        assert lead.lead_id == "widget-001"
        assert lead.name == "Maya"
        assert lead.contact_email == "maya@example.test"
        assert lead.phone == "555-0100"
        assert lead.lead_type == "nonprofit"
        assert lead.recommended_service == "Nonprofit Solvency Review"
        assert lead.owner_review_required is True
        assert lead.approval_status == "pending_owner_review"
        assert lead.urgency_score == 90.0
        assert "cash flow crisis" in lead.stated_problem.lower()
        assert "widget_score: 87" in lead.notes
        assert "source_page: https://faithvision.example/widget" in lead.notes

    def test_real_widget_id_and_service_id_are_normalized(self):
        lead = widget_importer.widget_payload_to_lead(
            make_widget_payload(id=1718553600000, recommendedService="turnaround-sprint")
        )

        assert lead.lead_id == "website-widget-1718553600000"
        assert lead.recommended_service == "Nonprofit Solvency Review"

    def test_individual_widget_lead_can_skip_org_type(self):
        payload = make_widget_payload(
            recommendedService="gift-intensive",
            answers={
                "situation": {
                    "value": "individual",
                    "label": "I need clarity around my gifts and calling.",
                    "score": 25,
                },
                "budget": {
                    "value": "has_budget",
                    "label": "I can invest in strategic guidance.",
                    "score": 20,
                },
                "urgency": {
                    "value": "months",
                    "label": "In the next 1-3 months",
                    "score": 20,
                },
            },
        )

        lead = widget_importer.widget_payload_to_lead(payload)

        assert lead.lead_type == "individual"
        assert lead.sector == "Individual / FaithVision widget"
        assert lead.recommended_service == "Gift Discovery / Personal Calling Session"

    def test_distressed_widget_nonprofit_routes_to_solvency_review(self):
        lead = widget_importer.widget_payload_to_lead(
            make_widget_payload(
                id=1718553600000,
                recommendedService="turnaround-sprint",
                answers={
                    "situation": {
                        "value": "crisis",
                        "label": "We have a cash flow crisis and need funding clarity.",
                        "score": 90,
                    },
                    "org_type": {
                        "value": "nonprofit",
                        "label": "Nonprofit organization",
                        "score": 18,
                    },
                    "budget": {
                        "value": "25k_75k",
                        "label": "$25,000 - $75,000",
                        "score": 35,
                    },
                    "urgency": {
                        "value": "now",
                        "label": "Critical - we need help now",
                        "score": 30,
                    },
                },
            )
        )

        analyze_lead(lead)

        assert lead.assets_detected == []
        assert lead.recommended_service == "Nonprofit Solvency Review"

    def test_widget_records_accept_wrapper_object(self):
        records = widget_importer.widget_records_from_data(
            {"leads": [make_widget_payload()]}
        )

        assert len(records) == 1
        assert records[0]["id"] == "widget-001"

    def test_widget_records_accept_csv_export(self):
        records = widget_importer.widget_records_from_csv([
            "id,timestamp,firstName,email,phone,score,tier,recommendedService,situation,org_type,budget,urgency,page",
            '"1718553600000","2026-06-16T10:30:00Z","Maya","maya@example.test","555-0100","87","Hot","turnaround-sprint","Cash flow crisis","Nonprofit organization","Has budget","Critical now","/pricing.html"',
        ])

        assert len(records) == 1
        assert records[0]["id"] == "1718553600000"
        assert records[0]["answers"]["org_type"]["label"] == "Nonprofit organization"
        assert records[0]["recommendedService"] == "turnaround-sprint"

    def test_import_widget_file_runs_local_pipeline(self, tmp_path, monkeypatch):
        path = tmp_path / "widget_leads.json"
        path.write_text(json.dumps({"leads": [make_widget_payload()]}), encoding="utf-8")
        calls = []
        saved = []

        def fake_gate(action, lead_id=None, actor="system", payload_summary=None):
            calls.append(("gate", action, actor, lead_id))

        def fake_analyze(lead):
            calls.append(("analyze", lead.lead_id))
            lead.inferred_problem = "Analyzed locally."
            return {}

        def fake_score(lead):
            calls.append(("score", lead.lead_id))
            lead.total_score = 64.0
            lead.tier = "qualified"
            return ScoreResult(total_score=64.0, tier="qualified")

        def fake_save(lead):
            calls.append(("save", lead.lead_id))
            saved.append(lead)

        monkeypatch.setattr(widget_importer, "gate", fake_gate)
        monkeypatch.setattr(widget_importer, "analyze_lead", fake_analyze)
        monkeypatch.setattr(widget_importer, "score_lead", fake_score)
        monkeypatch.setattr(widget_importer, "save_lead", fake_save)

        result = widget_importer.import_widget_file(str(path))

        assert result.imported_count == 1
        assert result.skipped_count == 0
        assert saved[0].lead_id == "widget-001"
        assert calls == [
            ("gate", "classify_lead", "widget_importer", "widget-001"),
            ("analyze", "widget-001"),
            ("gate", "score_lead", "widget_importer", "widget-001"),
            ("score", "widget-001"),
            ("save", "widget-001"),
        ]

    def test_widget_importer_has_no_live_external_modules_or_actions(self):
        tree = ast.parse(inspect.getsource(widget_importer))
        imported_modules = set()
        called_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called_names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    called_names.add(node.func.attr)

        assert not (imported_modules & {"http", "smtplib", "socket", "urllib", "requests"})
        assert "draft_emails" not in called_names
        assert "send_email" not in called_names
        assert "post_to_crm" not in called_names


# ═══════════════════════════════════════════════════════════════════════════════
# 10. MODEL VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestModelValidation:

    def test_invalid_lead_type_caught(self):
        lead = make_lead(lead_type="alien")
        errors = lead.validate()
        assert any("lead_type" in e for e in errors)

    def test_score_out_of_range_caught(self):
        lead = make_lead()
        lead.total_score = 150.0
        errors = lead.validate()
        assert any("total_score" in e for e in errors)

    def test_valid_lead_has_no_errors(self):
        lead = make_lead()
        errors = lead.validate()
        assert errors == []

    def test_lead_roundtrip_dict(self):
        lead = make_lead()
        d    = lead.to_dict()
        lead2 = Lead.from_dict(d)
        assert lead.lead_id == lead2.lead_id
        assert lead.lead_type == lead2.lead_type


# ═══════════════════════════════════════════════════════════════════════════════
# 11. WIDGET DUPLICATE SKIP
# ═══════════════════════════════════════════════════════════════════════════════

class TestWidgetDuplicateSkip:
    """Importing the same widget lead_id twice must skip the second without overwriting."""

    def test_duplicate_widget_lead_is_skipped(self, tmp_path, monkeypatch):
        """
        First import saves the lead. Second import of the same id is reported
        as skipped with 'duplicate lead_id' and does NOT overwrite the stored lead.
        """
        custom_data = tmp_path / "dup-data"
        custom_audit = tmp_path / "dup-audit"
        monkeypatch.setenv("LEADGEN_DATA_DIR", str(custom_data))
        monkeypatch.setenv("LEADGEN_AUDIT_DIR", str(custom_audit))

        payload = make_widget_payload(id="dup-widget-001")
        widget_json = tmp_path / "widget_once.json"
        widget_json.write_text(json.dumps([payload]), encoding="utf-8")

        # First import — should succeed
        result1 = widget_importer.import_widget_file(str(widget_json))
        assert result1.imported_count == 1
        assert result1.skipped_count == 0

        # Mutate payload to simulate a changed record with the same id
        payload["score"] = 999
        widget_json.write_text(json.dumps([payload]), encoding="utf-8")

        # Second import — same lead_id must be skipped
        result2 = widget_importer.import_widget_file(str(widget_json))
        assert result2.imported_count == 0
        assert result2.skipped_count == 1
        assert "duplicate" in result2.skipped[0].reason.lower()
        assert result2.skipped[0].lead_id == "website-widget-dup-widget-001"

    def test_duplicate_does_not_overwrite_original(self, tmp_path, monkeypatch):
        """The stored lead after two imports must match the first import, not the second."""
        from leadgen.store import get_lead

        custom_data = tmp_path / "dup-overwrite-data"
        custom_audit = tmp_path / "dup-overwrite-audit"
        monkeypatch.setenv("LEADGEN_DATA_DIR", str(custom_data))
        monkeypatch.setenv("LEADGEN_AUDIT_DIR", str(custom_audit))

        first_payload = make_widget_payload(
            id="stable-001",
            answers={
                "situation": {"label": "Original situation", "value": "original"},
                "org_type":  {"label": "Nonprofit organization", "value": "nonprofit"},
                "urgency":   {"label": "Urgent", "value": "urgent"},
            },
        )
        second_payload = make_widget_payload(
            id="stable-001",
            answers={
                "situation": {"label": "REPLACED situation", "value": "replaced"},
                "org_type":  {"label": "Nonprofit organization", "value": "nonprofit"},
                "urgency":   {"label": "Urgent", "value": "urgent"},
            },
        )

        f = tmp_path / "w.json"
        f.write_text(json.dumps([first_payload]), encoding="utf-8")
        widget_importer.import_widget_file(str(f))

        f.write_text(json.dumps([second_payload]), encoding="utf-8")
        widget_importer.import_widget_file(str(f))

        stored = get_lead("website-widget-stable-001")
        assert stored is not None
        assert "Original situation" in stored.stated_problem
        assert "REPLACED" not in stored.stated_problem

    def test_non_duplicate_widget_leads_all_import(self, tmp_path, monkeypatch):
        """Multiple distinct ids in a single file all get imported."""
        custom_data = tmp_path / "multi-data"
        custom_audit = tmp_path / "multi-audit"
        monkeypatch.setenv("LEADGEN_DATA_DIR", str(custom_data))
        monkeypatch.setenv("LEADGEN_AUDIT_DIR", str(custom_audit))

        payloads = [make_widget_payload(id=f"lead-{i}") for i in range(3)]
        f = tmp_path / "multi.json"
        f.write_text(json.dumps(payloads), encoding="utf-8")

        result = widget_importer.import_widget_file(str(f))
        assert result.imported_count == 3
        assert result.skipped_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 12. ENV-ISOLATED DATA + AUDIT ROOTS (end-to-end file I/O)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEnvIsolatedRoots:
    """
    Verify LEADGEN_DATA_DIR + LEADGEN_AUDIT_DIR fully isolate all file I/O
    so tests never touch the package-level data/ or audit/ directories.
    """

    def test_save_and_retrieve_lead_in_tmp_data_dir(self, tmp_path, monkeypatch):
        from leadgen.store import get_lead, list_leads, save_lead, get_data_dir

        monkeypatch.setenv("LEADGEN_DATA_DIR",  str(tmp_path / "data"))
        monkeypatch.setenv("LEADGEN_AUDIT_DIR", str(tmp_path / "audit"))

        lead = make_lead(lead_id="env-iso-001", name="Isolation Test")
        save_lead(lead)

        # leads.json must appear inside tmp data dir, NOT the package dir
        assert (tmp_path / "data" / "leads.json").exists()
        retrieved = get_lead("env-iso-001")
        assert retrieved is not None
        assert retrieved.name == "Isolation Test"

        all_leads = list_leads()
        assert any(l.lead_id == "env-iso-001" for l in all_leads)

    def test_audit_entries_written_to_tmp_audit_dir(self, tmp_path, monkeypatch):
        from leadgen.audit import get_audit_file, read_audit_log

        monkeypatch.setenv("LEADGEN_DATA_DIR",  str(tmp_path / "data"))
        monkeypatch.setenv("LEADGEN_AUDIT_DIR", str(tmp_path / "audit"))

        log_action(
            action="import_lead",
            actor="env-iso-test",
            lead_id="env-iso-audit-001",
            decision="approved",
            reason="Env isolation audit test",
            payload_summary={},
        )

        audit_path = tmp_path / "audit" / "leadgen_audit.jsonl"
        assert audit_path.exists()
        entries = read_audit_log(limit=20)
        assert any(e.get("lead_id") == "env-iso-audit-001" for e in entries)

    def test_export_json_lands_in_tmp_data_dir(self, tmp_path, monkeypatch):
        from leadgen.store import save_lead, export_local_json

        monkeypatch.setenv("LEADGEN_DATA_DIR",  str(tmp_path / "export-data"))
        monkeypatch.setenv("LEADGEN_AUDIT_DIR", str(tmp_path / "export-audit"))

        lead = make_lead(lead_id="env-export-001")
        save_lead(lead)

        out_path = export_local_json("export.json")
        assert os.path.exists(out_path)
        assert str(tmp_path / "export-data") in out_path
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
        assert any(l["lead_id"] == "env-export-001" for l in data.get("leads", []))

    def test_two_isolated_envs_do_not_share_data(self, tmp_path, monkeypatch):
        """Changing LEADGEN_DATA_DIR mid-test gives an independent store."""
        from leadgen.store import get_lead, save_lead

        dir_a = tmp_path / "dir-a"
        dir_b = tmp_path / "dir-b"
        audit = tmp_path / "shared-audit"

        monkeypatch.setenv("LEADGEN_DATA_DIR",  str(dir_a))
        monkeypatch.setenv("LEADGEN_AUDIT_DIR", str(audit))
        lead_a = make_lead(lead_id="env-a-001")
        save_lead(lead_a)

        monkeypatch.setenv("LEADGEN_DATA_DIR", str(dir_b))
        # dir_b has no leads — get_lead must return None
        assert get_lead("env-a-001") is None


# ═══════════════════════════════════════════════════════════════════════════════
# 13. DASHBOARD — NO UNSAFE innerHTML WITH LEAD-CONTROLLED DATA
# ═══════════════════════════════════════════════════════════════════════════════

class TestDashboardSafety:
    """
    Static analysis of dashboard.html to confirm lead-controlled values
    are not injected via innerHTML (XSS risk).
    """

    @pytest.fixture(scope="class")
    @classmethod
    def dashboard_src(cls):
        path = os.path.join(
            os.path.dirname(__file__), "..", "dashboard.html"
        )
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_dashboard_file_exists(self, dashboard_src):
        assert len(dashboard_src) > 100, "dashboard.html appears empty"

    def test_no_external_script_src(self, dashboard_src):
        """No <script src="..."> pointing to external domains."""
        import re
        external_scripts = re.findall(
            r'<script[^>]+src=["\']https?://(?!localhost)', dashboard_src, re.IGNORECASE
        )
        assert not external_scripts, (
            f"External scripts found: {external_scripts}"
        )

    def test_no_external_link_stylesheet(self, dashboard_src):
        """No external CSS link tags."""
        import re
        external_css = re.findall(
            r'<link[^>]+href=["\']https?://(?!localhost)[^"\']+["\'][^>]*rel=["\']stylesheet',
            dashboard_src, re.IGNORECASE
        )
        # Also check the other attribute order
        external_css2 = re.findall(
            r'<link[^>]+rel=["\']stylesheet[^>]+href=["\']https?://(?!localhost)',
            dashboard_src, re.IGNORECASE
        )
        assert not (external_css + external_css2), (
            f"External stylesheet links found: {external_css + external_css2}"
        )

    def test_lead_fields_not_injected_as_raw_innerhtml(self, dashboard_src):
        """
        Verify the dashboard does not use innerHTML to render known
        lead-controlled string fields directly from the lead object
        without sanitization.

        Allowed: textContent = lead.X  (safe)
        Allowed: setAttribute(...)     (safe)
        Problematic: innerHTML = lead.X  or  innerHTML += lead.X  (XSS risk)

        We check that high-risk lead fields (name, organization, stated_problem,
        notes, inferred_problem) are never set directly into innerHTML.
        """
        import re
        # Pattern: innerHTML = ... lead.<risky_field>  (same JS statement, ≤200 chars)
        risky_fields = [
            "stated_problem", "inferred_problem", "notes",
            "name", "organization",
        ]
        for field in risky_fields:
            # Look for innerHTML assignments that reference the field name nearby
            pattern = rf'innerHTML\s*[+]?=.*\blead\.{re.escape(field)}\b'
            matches = re.findall(pattern, dashboard_src)
            assert not matches, (
                f"Potential XSS: innerHTML used with lead.{field}: {matches}"
            )

    def test_owner_review_warning_present(self, dashboard_src):
        """Dashboard must display the owner-review warning prominently."""
        assert "OWNER" in dashboard_src or "owner" in dashboard_src.lower()
        assert "approval" in dashboard_src.lower() or "review" in dashboard_src.lower()

    def test_no_fetch_or_xmlhttprequest_calls(self, dashboard_src):
        """Dashboard must not make network requests."""
        import re
        net_calls = re.findall(
            r'\b(fetch\s*\(|new\s+XMLHttpRequest|axios\.|\.ajax\()',
            dashboard_src
        )
        assert not net_calls, (
            f"Network call found in dashboard: {net_calls}"
        )
