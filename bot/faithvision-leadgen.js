/**
 * FaithVision Leadership — Lead Generation Bot
 * BeautyForAshes.io · BeautyForAshes.pro
 *
 * Architecture:
 *   - Runs fully standalone (scripted mode) with zero dependencies
 *   - Set CONFIG.aiMode = true + CONFIG.apiEndpoint to enable LLM responses
 *   - Knowledge base loads from /bot/leadgen-kb.json at runtime;
 *     falls back to embedded KB below — update either without touching bot logic
 *   - Every conversation is scored, stored, and webhook-posted for downstream analysis
 *   - Perpetual improvement: tune KB.qualifyingQuestions[].score weights and
 *     KB.scoringTiers thresholds based on actual conversion data in the admin panel
 *
 * Embed on any page with a single tag (before </body>):
 *   <script src="/bot/faithvision-leadgen.js" defer></script>
 *
 * Override config before the script tag:
 *   <script>window.FVL_CONFIG = { webhookUrl: 'https://...', autoOpenDelay: 0 };</script>
 */

;(function (global) {
  'use strict';

  // ─────────────────────────────────────────────────────────
  // 1. CONFIGURATION  (override via window.FVL_CONFIG)
  // ─────────────────────────────────────────────────────────
  const CONFIG = Object.assign({
    botName:         'FaithVision Advisor',
    brandName:       'FaithVision Leadership',
    consultantName:  'Pastor Anderson',

    // Destination URLs
    bookingUrl:  'signup.html#contact',
    plannerUrl:  'https://beautyforashes.pro',
    storeUrl:    'https://beautyforashes.creator-spring.com',
    caseStudies: 'case-studies.html',
    pricing:     'pricing.html',

    // AI mode — set apiEndpoint to your server-side proxy for Claude/GPT
    // NEVER put a raw API key here; proxy server-side
    aiMode:      false,
    apiEndpoint: '',  // POST { context, message, history } → { response }

    // Lead capture
    webhookUrl:   '',  // POST full lead object here
    adminPassword: 'fvl2026',  // for admin panel auth (change this)

    // Behavior
    autoOpenDelay: 50000,   // ms before auto-opening (0 = disabled)
    rememberSession: true,  // don't restart if visitor already chatted

    // Remote KB — fetched at init; falls back to embedded KB on failure
    kbUrl: '/bot/leadgen-kb.json',
  }, global.FVL_CONFIG || {});


  // ─────────────────────────────────────────────────────────
  // 2. EMBEDDED KNOWLEDGE BASE  (canonical fallback)
  //    The remote /bot/leadgen-kb.json is merged on top of this at runtime.
  //    To update without redeploying the bot script, edit leadgen-kb.json.
  // ─────────────────────────────────────────────────────────
  let KB = {
    version: '1.0.0',
    lastUpdated: '2026-06-13',

    // ── Credentials injected into LLM context and open-chat responses
    credentials: [
      '$120M+ in bridge, mezzanine, and gap financing facilitated over 15 years',
      '3× nationally awarded Borders Book of the Month author',
      '2010 Pulitzer Prize contender — I Have Seen the Living God',
      'Washington Park Association: $0 → $5.5M reconstruction funds (Bridgeport, CT 1999)',
      'New England Housing Ministries: insolvency → $7.5M cash in 24 months',
      'PrePaid Legal: 500 → 10,000 monthly subscribers in 42 months',
      '800,000+ households reached by self-built Tri-State broadcast — signal amplified 7×',
      'Original art collection ages 9–13 (1979–1983): appraised $150K–$500K/piece today',
      '40+ years executive leadership across nonprofit, healthcare, real estate, broadcast, and business',
    ],

    // ── Service tiers — matched to lead score
    services: [
      { id: 'gift-intensive',    name: 'Gift Discovery Intensive',        price: '$2,500',              duration: '90 min',          ideal: 'individual' },
      { id: 'turnaround-sprint', name: '90-Day Turnaround Sprint',        price: '$35,000–$75,000',     duration: '90 days',         ideal: 'distressed-org' },
      { id: 'retainer',          name: 'Fractional Strategist Retainer',  price: '$10,000–$18,000/mo',  duration: '3+ months',       ideal: 'growth-org' },
      { id: 'enterprise',        name: 'Enterprise Transformation',       price: '$150,000+',           duration: '6–18 months',     ideal: 'large-org' },
      { id: 'mastermind',        name: 'Gifts Mastermind Group',          price: '$1,500/mo',           duration: '6-mo cohort',     ideal: 'community' },
    ],

    // ── Case studies — injected into responses and LLM context
    caseStudies: [
      { id: 'washington-park',    name: 'Washington Park Association',    result: '$5.5M raised from $0',                  type: 'nonprofit',   location: 'Bridgeport, CT' },
      { id: 'nehm',               name: 'New England Housing Ministries', result: '$7.5M in 24 mo → $120M loans/15 yr',    type: 'faith-org',   location: 'New England' },
      { id: 'prepaid-legal',      name: 'PrePaid Legal Services',         result: '20× subscriber growth in 42 months',    type: 'business',    location: 'Regional' },
      { id: 'broadcast',          name: 'Tri-State Broadcast',            result: '5K → 800K+ households, signal 7×',      type: 'media',       location: 'NY/MA/CT' },
      { id: 'art-origins',        name: 'Art Collection (age 9–13)',       result: '$250–$500/piece, now $150K–$500K each', type: 'origins',     location: '1979–1983' },
    ],

    // ── Objection handlers — matched by keyword in open chat
    objections: {
      'expensive':      'The investment scales to your situation. The Gift Discovery Intensive starts at $2,500 and delivers a written Blueprint within 48 hours. The Mastermind runs $1,500/month. Would either be a better starting point?',
      'afford':         'The investment scales to your situation. The Gift Discovery Intensive starts at $2,500 and delivers a written Blueprint within 48 hours. The Mastermind runs $1,500/month. Would either be a better starting point?',
      'not sure':       'That\'s exactly why the discovery call exists — 20 minutes, no cost, no obligation. Pastor Anderson will tell you honestly whether FaithVision is the right fit.',
      'think about':    'Of course. The free Executive Planner is a good first step — it contains the same Hidden Asset Audit and 90-Day Sprint frameworks used in paid engagements.',
      'tried consulting': 'Most clients who\'ve been through other consultants say the difference is the documented track record — $120M in actual institutional results, not projections. The discovery call is the right place to explore whether this is different.',
      'already have':   'That\'s great context. The discovery call takes 20 minutes and Pastor Anderson can tell you immediately whether there\'s meaningful overlap or gap to fill.',
      'too busy':       'That\'s usually a signal, not an obstacle. The discovery call is 20 minutes — it\'s designed precisely for leaders who are too busy to waste time on the wrong consultant.',
    },

    // ── Qualifying questions with per-answer scores
    //    Total possible: ~180 pts. Tune scores via leadgen-kb.json based on conversion data.
    qualifyingQuestions: [
      {
        id: 'situation',
        question: 'What best describes where you are right now?',
        options: [
          { value: 'crisis',    label: 'My organization is in financial distress or facing closure',  score: 90 },
          { value: 'stalled',   label: 'We\'re stable but stuck — growth has stalled',                score: 70 },
          { value: 'individual',label: 'I want to monetize my gifts and build something of my own',   score: 55 },
          { value: 'growth',    label: 'We\'re growing and need ongoing senior strategic counsel',    score: 75 },
          { value: 'speaking',  label: 'Looking for a keynote speaker or workshop',                  score: 50 },
          { value: 'curious',   label: 'Just exploring what FaithVision Leadership offers',          score: 25 },
        ],
      },
      {
        id: 'org_type',
        question: 'What type of organization?',
        options: [
          { value: 'nonprofit',  label: 'Nonprofit or community organization',  score: 18 },
          { value: 'ministry',   label: 'Church or faith-based ministry',        score: 18 },
          { value: 'business',   label: 'Business or startup',                  score: 15 },
          { value: 'corporate',  label: 'Corporate / enterprise',               score: 20 },
          { value: 'healthcare', label: 'Healthcare organization',               score: 18 },
          { value: 'individual', label: 'Individual / no organization yet',      score: 8  },
        ],
      },
      {
        id: 'budget',
        question: 'What investment range are you working with?',
        options: [
          { value: 'under5k',   label: 'Under $5,000',                       score: 10 },
          { value: '5k_25k',    label: '$5,000 – $25,000',                   score: 22 },
          { value: '25k_75k',   label: '$25,000 – $75,000',                  score: 35 },
          { value: '75k_plus',  label: '$75,000+',                           score: 45 },
          { value: 'flexible',  label: 'Flexible — depends on the ROI case', score: 28 },
          { value: 'unsure',    label: 'Not sure yet',                       score: 12 },
        ],
      },
      {
        id: 'urgency',
        question: 'How urgent is your timeline?',
        options: [
          { value: 'now',       label: 'Critical — we need help now',             score: 30 },
          { value: 'months',    label: 'In the next 1–3 months',                  score: 20 },
          { value: 'quarter',   label: 'Planning for the next quarter',           score: 14 },
          { value: 'exploring', label: 'No set timeline — still exploring',       score: 5  },
        ],
      },
    ],

    // ── Score thresholds → tier recommendation
    scoringTiers: {
      hot:     { min: 140, serviceId: 'turnaround-sprint', cta: 'book-call',  label: 'Hot',    color: '#e74c3c' },
      warm:    { min: 95,  serviceId: 'gift-intensive',    cta: 'book-call',  label: 'Warm',   color: '#e67e22' },
      nurture: { min: 55,  serviceId: 'mastermind',        cta: 'planner',    label: 'Nurture',color: '#f1c40f' },
      cold:    { min: 0,   serviceId: null,                cta: 'planner',    label: 'Cold',   color: '#95a5a6' },
    },

    // ── Open-chat pattern → response mapping (scripted mode)
    chatPatterns: [
      {
        patterns: ['price', 'cost', 'invest', 'how much', 'afford', 'rate', 'fee'],
        response: 'Engagements range from <strong>$1,500/month</strong> (Mastermind Group) to <strong>$150,000+</strong> (Enterprise Transformation). The 90-Day Turnaround Sprint — the most requested — runs $35,000–$75,000 scoped to organization size. All begin with a free 20-minute discovery call.',
      },
      {
        patterns: ['how long', 'timeline', 'when can', 'how soon', 'start date'],
        response: 'Discovery calls are available within 3–5 business days. Engagements begin within 1–2 weeks of confirming scope. The Gift Intensive delivers a written Blueprint within 48 hours of your session. The 90-Day Sprint produces a funded, actionable roadmap at day 90.',
      },
      {
        patterns: ['result', 'proof', 'evidence', 'track record', 'case stud', 'worked for'],
        response: 'Documented results: Washington Park Association — $5.5M raised from $0 insolvency. New England Housing Ministries — $7.5M rebuilt in 24 months, then $120M in loans over 15 years. PrePaid Legal — 20× growth in 42 months. Full detail in the <a href="case-studies.html" style="color:#C9A84C;">case studies →</a>',
      },
      {
        patterns: ['faith', 'christian', 'god', 'church', 'religion', 'believer', 'atheist'],
        response: 'Faith is the foundation of Pastor Anderson\'s practice — but it\'s not a requirement to work with FaithVision Leadership. The strategic frameworks produce results regardless of the client\'s faith background. The autobiography was read by believers and atheists alike for the same reason.',
      },
      {
        patterns: ['book', 'autobiography', 'pulitzer', 'living god', 'i have seen'],
        response: '<em>I Have Seen the Living God</em> — 3× Borders Book of the Month, 2010 Pulitzer Prize contender. Available at the store: <a href="' + 'https://beautyforashes.creator-spring.com' + '" target="_blank" style="color:#C9A84C;">beautyforashes.creator-spring.com →</a>',
      },
      {
        patterns: ['planner', 'free', 'download', 'executive planner'],
        response: 'The free Executive Planner contains the Hidden Asset Audit, 90-Day Solvency Sprint, Gift-to-Business Blueprint, and Funder Targeting Matrix — the same frameworks used in paid engagements. <a href="https://beautyforashes.pro" target="_blank" style="color:#C9A84C;">Get it at beautyforashes.pro →</a>',
      },
      {
        patterns: ['art', 'painting', 'collection', '1979', '1983', 'age 9', 'age 13'],
        response: 'Between 1979 and 1983, ages 9 to 13, Pastor Anderson created an entire original collection in acrylic, oil, and pencil — and sold every piece himself at $250–$500 each. Today that collection carries a secondary market appraisal of $150,000–$500,000 per piece, driven by 40+ years of provenance and the documented adversity narrative behind each canvas.',
      },
      {
        patterns: ['broadcast', 'television', 'tv', '800', 'tri-state', 'signal'],
        response: 'What began as a locally televised program reaching 5,000 weekly viewers in Bridgeport grew to 800,000+ households across NY, MA, and CT. Viewer demand was so strong that the station owners were compelled to push the signal 7× stronger. That\'s not a marketing outcome — that\'s a movement outcome.',
      },
    ],
  };


  // ─────────────────────────────────────────────────────────
  // 3. LEAD STORE  (localStorage + webhook)
  // ─────────────────────────────────────────────────────────
  const LeadStore = {
    LEADS_KEY:   'fvl_leads_v1',
    SESSION_KEY: 'fvl_session_v1',

    save(lead) {
      lead.id        = Date.now();
      lead.timestamp = new Date().toISOString();
      lead.page      = global.location.pathname;
      lead.referrer  = document.referrer || '';
      const all = this.getAll();
      all.push(lead);
      try { localStorage.setItem(this.LEADS_KEY, JSON.stringify(all)); } catch (e) {}
      this._webhook(lead);
      return lead;
    },

    getAll() {
      try { return JSON.parse(localStorage.getItem(this.LEADS_KEY) || '[]'); } catch (e) { return []; }
    },

    saveSession(data) {
      try { sessionStorage.setItem(this.SESSION_KEY, JSON.stringify(data)); } catch (e) {}
    },

    getSession() {
      try { return JSON.parse(sessionStorage.getItem(this.SESSION_KEY) || 'null'); } catch (e) { return null; }
    },

    clearSession() {
      try { sessionStorage.removeItem(this.SESSION_KEY); } catch (e) {}
    },

    exportCSV() {
      const leads = this.getAll();
      if (!leads.length) return '';
      const cols = ['id', 'timestamp', 'firstName', 'email', 'phone', 'score', 'tier', 'recommendedService', 'situation', 'org_type', 'budget', 'urgency', 'page'];
      const rows = [cols.join(',')];
      leads.forEach(l => {
        rows.push(cols.map(c => {
          const v = l[c] !== undefined ? l[c] : (l.answers && l.answers[c] ? l.answers[c].label : '');
          return '"' + String(v).replace(/"/g, '""') + '"';
        }).join(','));
      });
      return rows.join('\n');
    },

    _webhook(lead) {
      if (!CONFIG.webhookUrl) return;
      fetch(CONFIG.webhookUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(lead),
      }).catch(() => {});
    },
  };


  // ─────────────────────────────────────────────────────────
  // 4. SCORING ENGINE
  // ─────────────────────────────────────────────────────────
  const Scorer = {
    compute(answers) {
      return Object.values(answers).reduce((s, a) => s + (a.score || 0), 0);
    },

    getTier(score) {
      const tiers = KB.scoringTiers;
      for (const key of ['hot', 'warm', 'nurture', 'cold']) {
        if (score >= tiers[key].min) return { key, ...tiers[key], score };
      }
      return { key: 'cold', ...tiers.cold, score };
    },

    getService(tierId) {
      return KB.services.find(s => s.id === tierId) || null;
    },

    buildLLMContext(answers, score) {
      const answerStr = Object.entries(answers)
        .map(([k, v]) => `${k}: ${v.label}`)
        .join(' | ');
      const tier = Scorer.getTier(score);
      const svc  = Scorer.getService(tier.serviceId);
      return [
        'Brand: FaithVision Leadership / BeautyForAshes.io',
        'Consultant: Pastor Raymond O. Anderson',
        'Credentials: ' + KB.credentials.slice(0, 5).join(' ◆ '),
        'Visitor profile: ' + answerStr,
        'Lead score: ' + score + ' (' + tier.label + ')',
        'Recommended service: ' + (svc ? svc.name + ' at ' + svc.price : 'None yet'),
        'Keep answers concise (2–4 sentences), warm, and focused on moving toward a discovery call.',
      ].join('\n');
    },
  };


  // ─────────────────────────────────────────────────────────
  // 5. UI  (chat widget, injected into DOM)
  // ─────────────────────────────────────────────────────────
  const UI = {
    win: null,
    msgs: null,
    optsEl: null,
    inputRow: null,
    inputEl: null,

    CSS: `
      :root{--fg:#F5F0E8;--fg2:#DDD5C4;--muted:#9A9080;--gold:#C9A84C;--gold2:#E8C97A;--gold3:#8A6E32;--bg:#0D0C0A;--bg2:#1A1915;--bg3:#252420}
      #fvl-toggle{position:fixed;bottom:2rem;right:2rem;z-index:99999;width:56px;height:56px;border-radius:50%;background:var(--gold);border:none;cursor:pointer;box-shadow:0 4px 24px rgba(201,168,76,.45);display:flex;align-items:center;justify-content:center;transition:transform .2s,box-shadow .2s;font-size:1.35rem;color:var(--bg)}
      #fvl-toggle:hover{transform:scale(1.08);box-shadow:0 6px 32px rgba(201,168,76,.55)}
      .fvl-badge{position:absolute;top:-4px;right:-4px;width:18px;height:18px;border-radius:50%;background:#e74c3c;color:#fff;font-size:.62rem;font-weight:700;display:flex;align-items:center;justify-content:center;font-family:sans-serif;pointer-events:none}
      #fvl-win{position:fixed;bottom:5.5rem;right:2rem;z-index:99998;width:370px;max-height:560px;background:var(--bg2);border:.5px solid rgba(201,168,76,.35);box-shadow:0 12px 48px rgba(0,0,0,.65);display:flex;flex-direction:column;transform:translateY(20px) scale(.95);opacity:0;pointer-events:none;transition:transform .25s ease,opacity .25s ease;font-family:'Jost',-apple-system,sans-serif}
      #fvl-win.open{transform:none;opacity:1;pointer-events:all}
      .fvl-hdr{background:var(--bg);border-bottom:.5px solid rgba(201,168,76,.2);padding:.9rem 1.2rem;display:flex;align-items:center;gap:.75rem;flex-shrink:0}
      .fvl-av{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,var(--gold),var(--gold3));display:flex;align-items:center;justify-content:center;font-size:.95rem;flex-shrink:0}
      .fvl-hdr-name{font-size:.82rem;font-weight:500;color:var(--fg);letter-spacing:.04em}
      .fvl-hdr-status{font-size:.67rem;color:var(--gold);display:flex;align-items:center;gap:.3rem;margin-top:2px}
      .fvl-hdr-status::before{content:'';width:6px;height:6px;border-radius:50%;background:#2ecc71;display:inline-block}
      .fvl-x{margin-left:auto;background:none;border:none;cursor:pointer;color:var(--muted);font-size:1rem;padding:.25rem;transition:color .2s;line-height:1}
      .fvl-x:hover{color:var(--fg)}
      .fvl-msgs{flex:1;overflow-y:auto;padding:1rem;display:flex;flex-direction:column;gap:.65rem;scrollbar-width:thin;scrollbar-color:rgba(201,168,76,.2) transparent;min-height:160px;max-height:300px}
      .fvl-m{max-width:90%;padding:.65rem .9rem;font-size:.8rem;line-height:1.55;animation:fvlFade .22s ease}
      @keyframes fvlFade{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
      .fvl-bot{background:var(--bg3);color:var(--fg2);border:.5px solid rgba(201,168,76,.12);align-self:flex-start}
      .fvl-bot strong{color:var(--gold)}
      .fvl-bot a{color:var(--gold)}
      .fvl-bot em{color:var(--fg2);font-style:italic}
      .fvl-user{background:rgba(201,168,76,.13);color:var(--fg);border:.5px solid rgba(201,168,76,.22);align-self:flex-end}
      .fvl-typing{display:flex;gap:4px;padding:.65rem .9rem;align-items:center;align-self:flex-start}
      .fvl-typing span{width:5px;height:5px;border-radius:50%;background:var(--gold);animation:fvlDot 1.2s infinite}
      .fvl-typing span:nth-child(2){animation-delay:.2s}
      .fvl-typing span:nth-child(3){animation-delay:.4s}
      @keyframes fvlDot{0%,80%,100%{opacity:.2;transform:scale(.8)}40%{opacity:1;transform:scale(1)}}
      .fvl-opts{display:flex;flex-direction:column;gap:.35rem;padding:0 1rem .75rem;flex-shrink:0}
      .fvl-opt{background:transparent;border:.5px solid rgba(201,168,76,.28);color:var(--fg2);font-size:.77rem;padding:.55rem .85rem;cursor:pointer;text-align:left;transition:background .15s,color .15s,border-color .15s;font-family:inherit;letter-spacing:.02em}
      .fvl-opt:hover{background:rgba(201,168,76,.12);color:var(--fg);border-color:var(--gold)}
      .fvl-inp-row{border-top:.5px solid rgba(201,168,76,.15);padding:.7rem 1rem;display:flex;gap:.5rem;align-items:center;flex-shrink:0}
      .fvl-inp{flex:1;background:rgba(255,255,255,.04);border:.5px solid rgba(201,168,76,.2);color:var(--fg);font-family:inherit;font-size:.8rem;padding:.5rem .8rem;outline:none;transition:border-color .2s}
      .fvl-inp::placeholder{color:var(--muted)}
      .fvl-inp:focus{border-color:var(--gold)}
      .fvl-send{background:var(--gold);color:var(--bg);border:none;cursor:pointer;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-size:.85rem;transition:background .2s;flex-shrink:0}
      .fvl-send:hover{background:var(--gold2)}
      .fvl-cta-pri{display:inline-block;background:var(--gold);color:var(--bg);font-size:.7rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;padding:.55rem 1.1rem;text-decoration:none;transition:background .2s;border:none;cursor:pointer;font-family:inherit;margin-top:.4rem}
      .fvl-cta-pri:hover{background:var(--gold2)}
      .fvl-cta-sec{display:inline-block;background:transparent;color:var(--gold);border:.5px solid rgba(201,168,76,.45);font-size:.7rem;font-weight:400;letter-spacing:.07em;padding:.45rem .9rem;text-decoration:none;transition:background .2s;margin-top:.4rem;margin-left:.4rem;cursor:pointer;font-family:inherit}
      .fvl-cta-sec:hover{background:rgba(201,168,76,.1)}
      .fvl-foot{padding:.4rem 1rem;text-align:center;border-top:.5px solid rgba(201,168,76,.08);flex-shrink:0}
      .fvl-foot span{font-size:.58rem;color:var(--muted);letter-spacing:.05em}
      @media(max-width:420px){#fvl-win{width:calc(100vw - 1.5rem);right:.75rem;bottom:5rem}#fvl-toggle{right:.75rem;bottom:.75rem}}
    `,

    init() {
      const s = document.createElement('style');
      s.id = 'fvl-styles';
      s.textContent = this.CSS;
      document.head.appendChild(s);

      // Toggle button
      const btn = document.createElement('button');
      btn.id = 'fvl-toggle';
      btn.setAttribute('aria-label', 'Open FaithVision Advisor chat');
      btn.innerHTML = '✦<span class="fvl-badge" id="fvl-badge" aria-hidden="true">1</span>';
      btn.addEventListener('click', () => Bot.toggle());
      document.body.appendChild(btn);

      // Chat window
      const win = document.createElement('div');
      win.id = 'fvl-win';
      win.setAttribute('role', 'dialog');
      win.setAttribute('aria-label', 'FaithVision Advisor chat');
      win.innerHTML = `
        <div class="fvl-hdr">
          <div class="fvl-av" aria-hidden="true">✦</div>
          <div>
            <div class="fvl-hdr-name">${CONFIG.botName}</div>
            <div class="fvl-hdr-status">Available now</div>
          </div>
          <button class="fvl-x" aria-label="Close chat" onclick="window._FVLBot&&window._FVLBot.close()">✕</button>
        </div>
        <div class="fvl-msgs" id="fvl-msgs" aria-live="polite"></div>
        <div class="fvl-opts" id="fvl-opts"></div>
        <div class="fvl-inp-row" id="fvl-inp-row" style="display:none">
          <input class="fvl-inp" id="fvl-inp" type="text" autocomplete="off" />
          <button class="fvl-send" id="fvl-send" aria-label="Send">→</button>
        </div>
        <div class="fvl-foot"><span>${CONFIG.brandName} · beautyforashes.io</span></div>
      `;
      document.body.appendChild(win);

      this.win     = win;
      this.msgs    = win.querySelector('#fvl-msgs');
      this.optsEl  = win.querySelector('#fvl-opts');
      this.inputRow = win.querySelector('#fvl-inp-row');
      this.inputEl  = win.querySelector('#fvl-inp');

      const send = win.querySelector('#fvl-send');
      this.inputEl.addEventListener('keypress', e => { if (e.key === 'Enter') Bot.onTextInput(this.inputEl.value); });
      send.addEventListener('click', () => Bot.onTextInput(this.inputEl.value));
    },

    open() {
      this.win.classList.add('open');
      const b = document.getElementById('fvl-badge');
      if (b) b.remove();
    },
    close()  { this.win.classList.remove('open'); },
    isOpen() { return this.win.classList.contains('open'); },

    msg(html, who = 'bot') {
      const d = document.createElement('div');
      d.className = `fvl-m fvl-${who}`;
      d.innerHTML = html;
      this.msgs.appendChild(d);
      this.msgs.scrollTop = this.msgs.scrollHeight;
      return d;
    },

    typing() {
      const d = document.createElement('div');
      d.className = 'fvl-m fvl-typing';
      d.id = 'fvl-typ';
      d.innerHTML = '<span></span><span></span><span></span>';
      this.msgs.appendChild(d);
      this.msgs.scrollTop = this.msgs.scrollHeight;
    },
    stopTyping() { const t = document.getElementById('fvl-typ'); if (t) t.remove(); },

    options(list, cb) {
      this.optsEl.innerHTML = '';
      list.forEach(opt => {
        const b = document.createElement('button');
        b.className = 'fvl-opt';
        b.textContent = opt.label;
        b.addEventListener('click', () => { this.optsEl.innerHTML = ''; cb(opt); });
        this.optsEl.appendChild(b);
      });
    },
    clearOptions() { this.optsEl.innerHTML = ''; },

    showInput(ph = 'Type here…') {
      this.inputRow.style.display = 'flex';
      this.inputEl.placeholder = ph;
      this.inputEl.value = '';
      this.inputEl.focus();
    },
    hideInput() { this.inputRow.style.display = 'none'; this.inputEl.value = ''; },
  };


  // ─────────────────────────────────────────────────────────
  // 6. BOT CONVERSATION CONTROLLER
  // ─────────────────────────────────────────────────────────
  const Bot = {
    state: null,

    _resetState() {
      return {
        started:   false,
        step:      'greeting',
        qIndex:    0,
        answers:   {},
        rawScore:  0,
        lead:      {},
        history:   [],   // [{role,content}] for LLM
      };
    },

    async init() {
      // Load remote KB (merge on top of embedded)
      if (CONFIG.kbUrl) {
        try {
          const r = await fetch(CONFIG.kbUrl);
          if (r.ok) { const data = await r.json(); this._mergeKB(data); }
        } catch (e) { /* use embedded */ }
      }

      UI.init();

      // Resume session if visitor already chatted this session
      if (CONFIG.rememberSession) {
        const saved = LeadStore.getSession();
        if (saved) { this.state = saved; }
      }

      if (!this.state) this.state = this._resetState();

      window._FVLBot = { open: () => this.open(), close: () => this.close(), toggle: () => this.toggle() };

      if (CONFIG.autoOpenDelay > 0) {
        setTimeout(() => { if (!UI.isOpen()) { UI.open(); this._boot(); } }, CONFIG.autoOpenDelay);
      }
    },

    _mergeKB(remote) {
      // Deep merge: arrays replace; objects merge
      Object.keys(remote).forEach(k => {
        if (Array.isArray(remote[k])) { KB[k] = remote[k]; }
        else if (typeof remote[k] === 'object' && remote[k] !== null && !Array.isArray(KB[k])) {
          KB[k] = Object.assign({}, KB[k] || {}, remote[k]);
        } else { KB[k] = remote[k]; }
      });
    },

    open()   { UI.open(); this._boot(); },
    close()  { UI.close(); },
    toggle() { UI.isOpen() ? this.close() : this.open(); if (!UI.isOpen()) return; this._boot(); },

    _boot() {
      if (this.state.started) return;
      this.state.started = true;
      this._greet();
    },

    _wait(ms) { return new Promise(r => setTimeout(r, ms)); },

    async _say(html, delay = 650) {
      UI.typing();
      await this._wait(delay);
      UI.stopTyping();
      UI.msg(html, 'bot');
      this.state.history.push({ role: 'assistant', content: html.replace(/<[^>]+>/g, '') });
      LeadStore.saveSession(this.state);
    },

    async _greet() {
      await this._say('Hello — I\'m the <strong>FaithVision Advisor</strong>. I help visitors quickly find out whether Pastor Anderson\'s work is the right fit for their situation.', 900);
      await this._wait(300);
      await this._say('I\'ll ask four short questions — takes about 90 seconds. At the end I\'ll give you a specific recommendation based on where you are.', 900);
      await this._wait(200);
      this._nextQuestion();
    },

    _nextQuestion() {
      const q = KB.qualifyingQuestions[this.state.qIndex];
      if (!q) { this._captureContact(); return; }
      setTimeout(async () => {
        await this._say(q.question, 600);
        UI.options(q.options, opt => this._onAnswer(q.id, opt));
      }, 300);
    },

    async _onAnswer(qId, opt) {
      UI.msg(opt.label, 'user');
      this.state.answers[qId] = opt;
      this.state.rawScore    += opt.score || 0;
      this.state.history.push({ role: 'user', content: opt.label });
      LeadStore.saveSession(this.state);

      // If visitor is an individual (no org), skip org_type question
      if (qId === 'situation' && opt.value === 'individual') {
        this.state.qIndex = 2; // jump to budget
      } else {
        this.state.qIndex++;
      }
      await this._wait(200);
      this._nextQuestion();
    },

    async _captureContact() {
      await this._say('I have a specific recommendation for you — just need your first name to personalize it.', 800);
      UI.showInput('Your first name…');
      this.state.step = 'name';
    },

    async onTextInput(val) {
      val = (val || '').trim();
      if (!val) return;
      UI.hideInput();
      UI.msg(val, 'user');
      this.state.history.push({ role: 'user', content: val });

      const step = this.state.step;

      if (step === 'name') {
        this.state.lead.firstName = val;
        await this._say(`Got it, ${val}. Your email address — so I can send a written copy of your recommendation?`, 600);
        UI.showInput('your@email.com');
        this.state.step = 'email';

      } else if (step === 'email') {
        this.state.lead.email = val;
        this.state.step = 'recommend';
        await this._deliver();

      } else if (step === 'phone') {
        this.state.lead.phone = val;
        await this._say('Perfect — I\'ve passed everything along. Is there anything else I can answer?', 600);
        UI.showInput('Ask me anything…');
        this.state.step = 'chat';

      } else if (step === 'chat') {
        await this._chat(val);
      }

      LeadStore.saveSession(this.state);
    },

    async _deliver() {
      const tier = Scorer.getTier(this.state.rawScore);
      const svc  = Scorer.getService(tier.serviceId);
      const name = this.state.lead.firstName;

      // Persist lead
      const saved = LeadStore.save({
        ...this.state.lead,
        answers:             this.state.answers,
        score:               this.state.rawScore,
        tier:                tier.label,
        recommendedService:  tier.serviceId,
      });
      this.state.lead.id = saved.id;

      await this._say(`${name}, here is my read based on everything you've shared:`, 600);

      if (tier.key === 'hot') {
        await this._say(
          `Your situation calls for the <strong>90-Day Turnaround Sprint</strong> — the same engagement that took Washington Park Association from $0 to $5.5M and New England Housing Ministries from complete insolvency to $7.5M cash on hand.<br><br>` +
          `Investment: <strong>$35,000–$75,000</strong>, scoped to your organization's size. Starts within 1–2 weeks of a discovery conversation.`,
          1200
        );
        await this._wait(300);
        UI.msg(
          `The right next step is a <strong>complimentary 20-minute discovery call.</strong> No pressure — just an honest conversation about whether this is the right fit.<br><br>` +
          `<a class="fvl-cta-pri" href="${CONFIG.bookingUrl}">Book Discovery Call →</a>` +
          `<a class="fvl-cta-sec" href="${CONFIG.plannerUrl}" target="_blank">Free Planner First</a>`,
          'bot'
        );

      } else if (tier.key === 'warm') {
        await this._say(
          `The <strong>Gift Discovery Intensive</strong> is the right first move — a 90-minute deep-dive with Pastor Anderson, delivered as a written Gift-to-Business Blueprint within 48 hours.<br><br>` +
          `Investment: <strong>$2,500</strong>. Typically scheduled within 1–2 weeks.`,
          1100
        );
        await this._wait(300);
        UI.msg(
          `<a class="fvl-cta-pri" href="${CONFIG.bookingUrl}">Book the Intensive →</a>` +
          `<a class="fvl-cta-sec" href="${CONFIG.plannerUrl}" target="_blank">Free Planner First</a>`,
          'bot'
        );

      } else if (tier.key === 'nurture') {
        await this._say(
          `The <strong>Gifts Mastermind Group</strong> gives you monthly access to Pastor Anderson's frameworks alongside 8–12 peers — at <strong>$1,500/month</strong>. New cohorts open quarterly.`,
          1000
        );
        await this._wait(300);
        UI.msg(
          `Or start with the free Executive Planner — it contains the complete Hidden Asset Audit and Gift-to-Business Blueprint.<br><br>` +
          `<a class="fvl-cta-pri" href="${CONFIG.plannerUrl}" target="_blank">Get Free Planner →</a>` +
          `<a class="fvl-cta-sec" href="${CONFIG.bookingUrl}">Talk to Someone →</a>`,
          'bot'
        );

      } else {
        await this._say(
          `The <strong>free Executive Planner</strong> is exactly the right place to start — it contains the Hidden Asset Audit, 90-Day Solvency Sprint framework, Gift-to-Business Blueprint, and Funder Targeting Matrix. No cost, instant access.`,
          1000
        );
        UI.msg(
          `<a class="fvl-cta-pri" href="${CONFIG.plannerUrl}" target="_blank">Get the Free Planner →</a>`,
          'bot'
        );
      }

      await this._wait(700);
      await this._say('Is there anything specific you\'d like to know before taking a next step? I can answer questions about pricing, the process, or what working with Pastor Anderson looks like.', 1000);
      UI.showInput('Ask me anything…');
      this.state.step = 'chat';
    },

    async _chat(input) {
      const lower = input.toLowerCase();

      // Check objections
      for (const [key, resp] of Object.entries(KB.objections)) {
        if (lower.includes(key)) { await this._say(resp, 800); return; }
      }

      // Check patterns
      for (const entry of KB.chatPatterns) {
        if (entry.patterns.some(p => lower.includes(p))) {
          await this._say(entry.response, 900);
          UI.showInput('Anything else?');
          return;
        }
      }

      // LLM fallback
      if (CONFIG.aiMode && CONFIG.apiEndpoint) {
        await this._llm(input);
      } else {
        await this._say(
          `That\'s a good question for a direct conversation. The free 20-minute discovery call is the fastest way to get a straight answer from Pastor Anderson himself.<br><br>` +
          `<a class="fvl-cta-pri" href="${CONFIG.bookingUrl}">Book a Free Call →</a>`,
          800
        );
      }
      UI.showInput('Anything else?');
    },

    async _llm(userMsg) {
      UI.typing();
      try {
        const res = await fetch(CONFIG.apiEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            context: Scorer.buildLLMContext(this.state.answers, this.state.rawScore),
            history: this.state.history.slice(-10),
            message: userMsg,
          }),
        });
        const data = await res.json();
        UI.stopTyping();
        const reply = data.response || data.message || 'I\'ll have Pastor Anderson follow up on that directly.';
        UI.msg(reply, 'bot');
        this.state.history.push({ role: 'assistant', content: reply });
      } catch (e) {
        UI.stopTyping();
        await this._say(`I want to make sure you get an accurate answer on that. The discovery call is the right place — <a href="${CONFIG.bookingUrl}" style="color:var(--gold)">book it here →</a>`, 400);
      }
    },
  };


  // ─────────────────────────────────────────────────────────
  // 7. BOOT
  // ─────────────────────────────────────────────────────────
  function boot() {
    // Don't double-init
    if (document.getElementById('fvl-win')) return;
    Bot.init();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // Public surface
  global.FVLLeadGen = { Bot, KB, LeadStore, Scorer, CONFIG };

})(window);
