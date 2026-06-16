# FaithVision Lead Generation System
**Owner:** Pastor Raymond Anderson / Jesus.AiBot  
**Version:** 1.0.0  
**Status:** LOCAL DRAFT — Deny-by-Default — No Live Outreach

---

## CORE RULE

> **No automatic outreach. Ever.**  
> This system drafts, classifies, and scores leads locally.  
> Every send / publish / export-to-live-system action requires explicit owner approval.  
> The default policy action is **DENY**.

---

## What This System Does

The FaithVision Lead Generation System helps Pastor Anderson / Jesus.AiBot:

1. **Identify and classify** leads across three categories:
   - Individuals seeking gift/purpose/business development
   - Nonprofits needing solvency, restructuring, or funding
   - For-profit companies needing revenue expansion or hidden-value analysis

2. **Score** each lead across 8 dimensions (0–100, tiered: low / watch / qualified / priority / executive)

3. **Analyze** using FaithVision positioning — hidden asset discovery, revenue stream identification, solvency preservation, purpose activation

4. **Draft outreach emails** (5 templates) for owner review — nothing is sent automatically

5. **Package** leads into owner review packets for structured decision-making

6. **Audit** every action in an append-only JSONL log with no raw secrets

---

## Directory Structure

```
leadgen-system-draft/
└── leadgen/
    ├── __init__.py
    ├── __main__.py
    ├── policy.json              ← Deny-by-default policy config
    ├── models.py                ← Lead, EmailDraft, ReviewPacket data models
    ├── redaction.py             ← Secret leak prevention
    ├── scoring.py               ← 8-dimension scoring engine
    ├── analyzer.py              ← FaithVision analysis logic
    ├── router.py                ← Policy gate (deny-by-default enforcer)
    ├── email_drafter.py         ← Draft-only email composer
    ├── widget_importer.py       ← Local website widget export importer
    ├── audit.py                 ← Append-only audit log
    ├── store.py                 ← Local JSON file store (atomic writes)
    ├── cli.py                   ← Command-line interface
    ├── sample_leads.json        ← 6 fictional sample leads
    ├── dashboard.html           ← Local-only owner review dashboard
    ├── data/
    │   ├── leads.json           ← Lead store
    │   └── review_packets.json  ← Review packet store
    ├── audit/
    │   └── leadgen_audit.jsonl  ← Append-only audit log
    └── tests/
        └── test_leadgen.py      ← Full pytest test suite
```

---

## Quickstart

### Prerequisites
- Python 3.9+ (standard library only — no external dependencies required)
- `pytest` for tests: `pip install pytest`

### 1. Run Tests
```bash
cd /path/to/leadgen-system-draft
python3 -m pytest leadgen/tests/test_leadgen.py -v
```

Tests set isolated temp data and audit roots automatically. For manual CLI runs, you can
also redirect local files with:

```bash
export LEADGEN_DATA_DIR=/tmp/faithvision-leadgen-data
export LEADGEN_AUDIT_DIR=/tmp/faithvision-leadgen-audit
```

When unset, the defaults remain `leadgen/data/` and `leadgen/audit/`.

### 2. Import Sample Leads
```bash
cd leadgen-system-draft
python3 -m leadgen.cli import leadgen/sample_leads.json
```

### 3. List All Leads
```bash
python3 -m leadgen.cli list
```

### Import Website Widget Leads
```bash
python3 -m leadgen.cli import-widget widget_leads.json
python3 -m leadgen.cli import-widget widget_leads.csv
```

Accepts a JSON array, `{ "leads": [...] }`, or CSV from the website widget lead store. The importer converts each widget record to a local `Lead`, normalizes widget service IDs, skips duplicate `lead_id` values without overwriting existing leads, then runs analysis, scoring, and local save through policy gates. It does not draft, send, post to webhooks, or call external services.

### 4. Score a Specific Lead
```bash
python3 -m leadgen.cli score ind-001-faithvision
```

### 5. View a Lead Detail
```bash
python3 -m leadgen.cli show ind-001-faithvision
```

### 6. Generate Email Drafts (for owner review)
```bash
python3 -m leadgen.cli draft ind-001-faithvision
```

### 7. Create Owner Review Packet
```bash
python3 -m leadgen.cli packet np-001-faithvision
```

### 8. View Audit Log
```bash
python3 -m leadgen.cli audit
```

### 9. Export to JSON (for dashboard)
```bash
python3 -m leadgen.cli export export.json
```

### 10. Open Dashboard
Open `leadgen/dashboard.html` in any browser, then load `leadgen/data/export.json` manually.

### 11. View Policy
```bash
python3 -m leadgen.cli policy
```

---

## CLI Reference

| Command | Description |
|---|---|
| `import <file.json>` | Import leads from JSON file (runs analysis + scoring) |
| `import-widget <file.json|file.csv>` | Import website widget exports locally (JSON array, `{ "leads": [...] }`, or CSV) |
| `list` | List all leads sorted by score |
| `show <LEAD_ID>` | Full lead detail |
| `score <LEAD_ID>` | Re-score a lead and display breakdown |
| `draft <LEAD_ID>` | Generate email drafts (owner review required) |
| `packet <LEAD_ID>` | Create full owner review packet (lead + scores + drafts) |
| `audit` | View audit log statistics and recent entries |
| `export [output.json]` | Export all leads and packets to local JSON inside `leadgen/data/` |
| `policy` | Display the active deny-by-default policy |

---

## Scoring Dimensions

| Dimension | Weight |
|---|---|
| Gift Development Fit | 15% |
| Solvency / Restructuring Need | 15% |
| Hidden Asset Potential | 15% |
| Revenue Expansion Potential | 15% |
| Urgency | 12% |
| Ability to Pay | 10% |
| Mission Alignment | 10% |
| Ethical / Compliance Risk (inverse) | 8% |

**Tiers:**
- 85–100: **EXECUTIVE**
- 70–84: **PRIORITY**
- 50–69: **QUALIFIED**
- 30–49: **WATCH**
- 0–29: **LOW**

---

## Email Draft Templates

| Template | Audience |
|---|---|
| `short_first_touch` | All lead types |
| `warm_referral` | All lead types |
| `nonprofit_version` | Nonprofits and ministries |
| `for_profit_exec_version` | For-profit companies |
| `individual_gift_dev` | Individuals |

**Sender routing:**
- Executive / Priority / Qualified → `andersonraymond7@icloud.com`
- Watch / Low → `pastorpaol@gmail.com`

**All drafts carry `approval_status: pending_owner_review`.  
Nothing is sent without explicit owner action.**

---

## Service Routes

1. Gift Discovery / Personal Calling Session
2. Nonprofit Solvency Review
3. Hidden Asset & Revenue Stream Audit
4. Executive Strategic Advisory
5. Enterprise Transformation Engagement
6. Speaking / Workshop Inquiry
7. Book / FaithVision Resource Path

---

## Policy — Allowed vs. Forbidden

**Allowed (local only):**
- import_lead, classify_lead, score_lead, draft_email
- create_owner_review_packet, export_local_json

**Forbidden (blocked by policy gate — require future explicit approval):**
- send_email, post_to_crm, post_to_zapier, scrape_private_data
- use_api_credentials, publish_to_website, delete_records
- alter_dns, charge_payment, access_social_accounts

---

## Security Constraints

- No live email sending
- No API calls or credentials
- No real scraping
- No hardcoded passwords
- No destructive file operations
- No publishing
- No external dependencies (standard library only)
- Atomic file writes (temp file + rename)
- Path traversal protection on all store operations
- Append-only audit log with redaction
- All secret-like values redacted before any output or log

---

## Risk List

1. **Data at rest is not encrypted.** JSON files in `data/` are plaintext. Encrypt the folder or use FileVault if real leads are stored.
2. **No authentication.** The CLI runs as the local user. Anyone with filesystem access can read leads.
3. **Email addresses in drafts are real.** Owner email addresses appear in draft bodies — protect the files accordingly.
4. **Limited deduplication.** Website widget imports skip existing `lead_id` values, but broader identity matching across emails, organizations, and hand-entered leads still requires owner review.
5. **Scoring is heuristic.** Keyword-based signals are approximate — owner judgment required before any outreach.
6. **Dashboard loads from local file only.** No live sync. Must re-export and reload after changes.
7. **Audit log is append-only but not tamper-proof.** It is a flat file — not a cryptographic audit trail.

---

## What Commander AI Bot Must Review Before Integration

1. **Policy gate is the single enforcement point** — any integration must route through `router.gate()`. Do not bypass.
2. **`send_email` is permanently forbidden** in this codebase. Any future email capability requires a new, separate module with owner-controlled activation.
3. **All email bodies reference real owner emails** (`andersonraymond7@icloud.com`, `pastorpaol@gmail.com`). These must be verified and protected.
4. **Scoring weights** in `scoring.py → WEIGHTS` should be tuned based on real conversion data before production use.
5. **Sample leads use fictional data** — verify that no real PII is introduced when importing real leads.
6. **No CRM, API, or webhook integration is wired** — any connection must be built as a separate approved module.
7. **Audit log must be reviewed** before any live deployment to confirm no secret leakage has occurred.
8. **Dashboard is static HTML** — loading it in a browser with an internet connection is safe (no external scripts), but keep export files off shared drives.

---

*FaithVision Lead Generation System — Local Draft Only — Pastor Raymond Anderson / Jesus.AiBot*
