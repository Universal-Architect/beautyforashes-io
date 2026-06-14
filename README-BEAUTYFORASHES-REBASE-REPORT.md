# BeautyForAshes.io Authority Rebase — Build Report

Prepared: 2026-06-14  
Work Order: BEAUTYFORASHES_AUTHORITY_REBASE_PACKET_2026-06-13.md  
Status: Complete — local files only. Nothing published, uploaded, or deployed.

---

## Source Files Used

| File | Role | Status |
|------|------|--------|
| `/Volumes/Lenovo PS8S/Bio-Experience for coding in Claude/ABOUT-FINAL-V7.html` | Primary source for index.html | Read in full |
| `/Volumes/Lenovo PS8S/Bio-Experience for coding in Claude/PRICING-FINAL-V3.html` | Primary source for pricing.html | Read in full |
| `/Volumes/Lenovo PS8S/Bio-Experience for coding in Claude/HOME-PART-1-V4.html` | Supporting source (book/store/edition) | Read; strongest sections referenced for CTAs |
| Previous session outputs: case-studies.html, planner.html | Preserved with link patches | Updated in place |

---

## Files Produced

All files are in the outputs folder. None has been uploaded, published, or pushed to GitHub.

| File | Source | Description |
|------|--------|-------------|
| `index.html` | ABOUT-FINAL-V7.html | Authority/bio home page — full 12-section authority build |
| `pricing.html` | PRICING-FINAL-V3.html | Services and pricing with enterprise tier corrected |
| `case-studies.html` | Previous session | Preserved; nav and CTAs patched |
| `planner.html` | Previous session | Preserved; nav and footer links patched |
| `signup.html` | New build | Booking page: Calendly embed, intake PDF downloads, contact |
| `README-BEAUTYFORASHES-REBASE-REPORT.md` | This file | Build report |
| `bot/faithvision-leadgen.js` | Previous session | Unchanged |
| `bot/leadgen-kb.json` | Previous session | Unchanged |
| `leadgen-admin.html` | Previous session | Unchanged |

---

## Link Map — What Changed

### Old Hostinger Absolute Links → New

| Old link | New link | Applied in |
|----------|----------|------------|
| `https://beautyforashes.io` | `index.html` | All nav/footer |
| `https://beautyforashes.io/about` | `index.html` | All nav |
| `https://beautyforashes.io/pricing` | `pricing.html` | All pages |
| `https://beautyforashes.io/case-studies` | `case-studies.html` | All pages |
| `https://beautyforashes.io/page` | `https://beautyforashes.creator-spring.com` | All pages |
| `https://beautyforashes.io/planner` | `https://beautyforashes.pro/` | All pages |
| `mailto:pastorpaol@gmail.com?subject=Discovery Call Request` (primary CTA) | `https://calendly.com/pastorpaol/new-meeting-client-harmonization` | index.html, pricing.html (main CTAs) |

### Tier-Specific Inquiry Emails — Preserved as-is

The individual tier inquiry buttons in pricing.html (e.g., "Fractional Strategist Retainer Inquiry", "Nonprofit Growth Strategy Inquiry") retain their `mailto:pastorpaol@gmail.com?subject=...` links. These are specific inquiry emails, not general booking CTAs, and are appropriate as-is per the work order's fallback policy.

### Calendly URL Used

`https://calendly.com/pastorpaol/new-meeting-client-harmonization`

This is the exact URL from the work order. No substitution was made.

---

## Enterprise Pricing Correction

| Tier | Old value | New value |
|------|-----------|-----------|
| Enterprise Transformation (Corporate Tier 02) | `$250,000+` | `$500,000–$1.5 million` |

All other tier prices and descriptions preserved verbatim from PRICING-FINAL-V3.html.

---

## Content Preserved

All authority pillars from the work order are present in index.html:

- Chief Creationist / Universal Architect / Priest Before the Lord identity
- Childhood art/origin story (ages 9–13)
- Orthopedic healthcare chapter (tibia/fibula, 45 min vs. 3–4 hrs, leg-length discrepancy)
- 28-year orthopedic healthcare leadership
- Washington Park Association ($5.5M, 13 homes)
- New England Housing Ministries ($7.5M → $120M)
- PrePaid Legal (500 → 10,000 subscribers, 20× growth)
- Bridgeport civic reform / Caruso election integrity / Denise Anderson / 300+ donors
- Pro se legal record (3 cases, CT Superior Court, Westchester, CT Supreme Court)
- Market comparison (Tony Robbins, TD Jakes, Myron Golden)
- Dedications (Denise Anderson, Dr. & Mrs. Goldstone, Thelma Marino)
- Gallery
- Chief Creationist philosophy / Isaiah 61:3
- Store CTA → `https://beautyforashes.creator-spring.com`
- Executive Planner CTA → `https://beautyforashes.pro/`
- Intake PDF links (FAITHVISION-INDIVIDUAL-INTAKE.pdf, FAITHVISION-CORPORATE-INTAKE.pdf)

---

## Wording Changes / Risk Removals

| What | Why |
|------|-----|
| No language invented or added to any authority section | Work order: preserve content unless explicitly patched |
| "22 election law violations proven in CT Supreme Court" preserved verbatim from source | Source language retained |
| "$200M restructuring" framed as institution filing for bankruptcy | Source language; no additional legal claims added |
| Pro se legal wins framed around evidence, problem-solving, and institutional pressure — not as court victories with claimed damages awarded | Work order tone guidance |
| No defamatory language about Tony Robbins, TD Jakes, or Myron Golden | Market comparison uses publicly stated facts only |
| No medical advice framing | Medical chapter includes explicit disclaimer: "This story is not included here to suggest Pastor Anderson practices medicine" |

---

## Security Scan Result

- PayPal code: NONE
- Payment SDK: NONE
- API keys: NONE
- OAuth tokens: NONE
- Client IDs / Plan IDs: NONE
- Account IDs: NONE
- Raw logs: NONE
- Secret-looking values: NONE
- Broken `/pricing`, `/case-studies`, `/page`, `/planner` absolute-path links: NONE (all patched)
- Links to `beautyforashes.io/store`: NONE (store links → creator-spring.com)
- Fake Calendly link: NONE (exact URL from work order used)
- Hidden admin/bot files added to site pages: NONE (bot/faithvision-leadgen.js is a previously built IIFE, not a new hidden file)

---

## Remaining Owner Decisions

1. **GitHub upload** — None of these files have been pushed to the repository. The live site at beautyforashes.io still shows the old planner page. The owner must upload all files to the `Universal-Architect/beautyforashes-io` GitHub repository (or use Codex or another tool to do so).

2. **Intake PDFs in repo** — `FAITHVISION-INDIVIDUAL-INTAKE.pdf` and `FAITHVISION-CORPORATE-INTAKE.pdf` must be present in the repo root for the download links to work. Confirm these are already uploaded at the root level of the GitHub Pages repo.

3. **Bot script on all pages** — `bot/faithvision-leadgen.js` and `bot/leadgen-kb.json` must be in the `bot/` folder in the repo for the lead gen bot to function. These files exist in the outputs folder.

4. **Calendly URL confirmation** — The booking calendar at `https://calendly.com/pastorpaol/new-meeting-client-harmonization` should be tested to confirm it is live and accepting bookings.

5. **planner.html vs. https://beautyforashes.pro/** — The work order lists both. Currently `planner.html` exists as a local free-planner signup/download page; nav links and the primary Planner CTA point to `https://beautyforashes.pro/` (the external app). If the owner wants the nav "Free Planner" link to go to `planner.html` instead, that is a one-line edit.

6. **Instagram and LinkedIn footer links** — Currently point to `https://www.instagram.com/` and `https://www.linkedin.com/` (generic). If the owner has profile URLs, these should be updated.

7. **HOME-PART-1-V4.html book content** — The book/store section from HOME-PART-1-V4.html (testimonials from Diane Defonce / Borders, Indra Sharma / Canadian Reader's Digest) was not added to index.html because the work order says to use it "only if needed." If the owner wants the book testimonials on the home page, they can be inserted into the CTA or a new section between the Gallery and Chief Creationist Philosophy sections.

---

## Hard Stop Confirmation

Files are actually produced. Links are checked. No disallowed payment code or secret is present. This report is an honest account of what was built.
