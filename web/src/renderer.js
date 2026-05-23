// renderer.js — turns canonical Events into DOM updates across all panels.
// Subscribes to a player's bus; knows nothing about mock vs live.

import { highlight } from './highlight.js';

const PHASES = [
  ['ingest', 'INGEST'],
  ['recover', 'RECOVER'],
  ['translate', 'TRANSLATE'],
  ['oracle', 'ORACLE'],
  ['test', 'TEST'],
  ['diagnose', 'DIAGNOSE'],
  ['forge', 'FORGE'],
  ['reload', 'RELOAD'],
  ['verify', 'VERIFY'],
  ['done', 'DONE'],
];

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};
const escapeText = (s) => (s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

export class Renderer {
  constructor(root = document) {
    this.root = root;
    this.refs = {
      rail: $('#phase-rail', root),
      trace: $('#trace-stream', root),
      rules: $('#rules-list', root),
      ruleCount: $('#rules-count', root),
      diffLeft: $('#diff-left', root),
      diffRight: $('#diff-right', root),
      diffLeftName: $('#diff-left-name', root),
      diffRightName: $('#diff-right-name', root),
      term: $('#pytest-body', root),
      termVerdict: $('#pytest-verdict', root),
      forge: $('#forge-body', root),
      forgeReason: $('#forge-reason', root),
      iterCounter: $('#iter-counter', root),
      iterCap: $('#iter-cap', root),
      downloadBtn: $('#download-btn', root),
      oracleBanner: $('#oracle-banner', root),
      verdictBadge: $('#verdict-badge', root),
      stage: $('#stage', root),
    };
    this.artifact = null;
  }

  /** Wire to a player; returns an unsubscribe fn. */
  attach(player) {
    const offs = [
      player.on('reset', (p) => this.reset(p.meta)),
      player.on('event', (ev) => this.handle(ev)),
    ];
    return () => offs.forEach((f) => f());
  }

  reset(meta = {}) {
    const r = this.refs;
    r.trace.innerHTML = '';
    r.rules.innerHTML = '';
    r.ruleCount.textContent = '0';
    r.diffLeft.innerHTML = '';
    r.diffRight.innerHTML = '';
    r.diffLeftName.textContent = '—';
    r.diffRightName.textContent = '—';
    r.term.innerHTML = '<div class="term-idle">$ awaiting equivalence run…</div>';
    r.termVerdict.textContent = '';
    r.termVerdict.className = 'term-verdict';
    r.forge.innerHTML = '<div class="forge-idle">no skill forged yet — agent uses only its seed skills</div>';
    r.forgeReason.textContent = '';
    r.iterCounter.textContent = '0';
    r.iterCap.textContent = meta.iteration_cap ?? '4';
    r.downloadBtn.setAttribute('disabled', '');
    r.downloadBtn.classList.remove('ready');
    r.oracleBanner.classList.remove('show');
    r.verdictBadge.classList.remove('show', 'good');
    r.verdictBadge.textContent = '';
    r.stage.dataset.phase = '';
    this.artifact = null;
    this._buildRail();
  }

  _buildRail() {
    const r = this.refs;
    r.rail.innerHTML = '';
    for (const [key, label] of PHASES) {
      const node = el('div', 'rail-step', `<span class="rail-dot"></span><span class="rail-label">${label}</span>`);
      node.dataset.phase = key;
      r.rail.appendChild(node);
    }
  }

  handle(ev) {
    const fn = this['on_' + ev.type];
    if (fn) fn.call(this, ev);
  }

  // --- phase rail ----------------------------------------------------------
  on_phase(ev) {
    const r = this.refs;
    r.stage.dataset.phase = ev.phase;
    let active = false;
    for (const node of r.rail.children) {
      if (node.dataset.phase === ev.phase) {
        node.classList.add('active');
        node.classList.remove('past');
        active = true;
      } else if (!active) {
        node.classList.add('past');
        node.classList.remove('active');
      } else {
        node.classList.remove('active', 'past');
      }
    }
    if (ev.iteration != null) r.iterCounter.textContent = ev.iteration;
  }

  // --- (b) agent-working trace --------------------------------------------
  on_step(ev) {
    const r = this.refs;
    const card = el('div', `trace-card kind-${ev.kind}`);
    const head = el('div', 'trace-head');
    head.appendChild(el('span', 'trace-kind', ev.kind.replace('_', ' ')));
    if (ev.tool) head.appendChild(el('span', 'trace-tool', escapeText(ev.tool)));
    if (ev.title) head.appendChild(el('span', 'trace-title', escapeText(ev.title)));
    if (ev.status) head.appendChild(el('span', `trace-status st-${ev.status}`, ev.status));
    if (ev.duration_ms != null) head.appendChild(el('span', 'trace-dur', `${ev.duration_ms}ms`));
    card.appendChild(head);

    if (ev.text) {
      if (ev.kind === 'code' || ev.kind === 'output' || ev.kind === 'tool_call') {
        const lang = ev.lang || (ev.kind === 'output' ? 'bash' : '');
        const pre = el('pre', 'trace-code');
        pre.innerHTML = highlight(ev.text, lang);
        card.appendChild(pre);
      } else {
        card.appendChild(el('div', 'trace-text', escapeText(ev.text)));
      }
    }
    r.trace.appendChild(card);
    requestAnimationFrame(() => card.classList.add('in'));
    r.trace.scrollTop = r.trace.scrollHeight;
  }

  // --- (c) business rules --------------------------------------------------
  on_business_rule(ev) {
    const r = this.refs;
    const card = el('div', `rule-card sev-${ev.severity || 'rule'}`);
    card.innerHTML = `
      <div class="rule-head">
        <span class="rule-sev">${(ev.severity || 'rule').replace('_', ' ')}</span>
        <span class="rule-title">${escapeText(ev.title)}</span>
      </div>
      <div class="rule-plain">${escapeText(ev.plain)}</div>
      <code class="rule-ref">${escapeText(ev.cobol_ref)}</code>`;
    r.rules.appendChild(card);
    requestAnimationFrame(() => card.classList.add('in'));
    r.ruleCount.textContent = r.rules.children.length;
  }

  // --- (d) diff viewer -----------------------------------------------------
  on_diff(ev) {
    const r = this.refs;
    this._renderSide(r.diffLeft, r.diffLeftName, ev.left, ev.links, 'left');
    this._renderSide(r.diffRight, r.diffRightName, ev.right, ev.links, 'right');
    // flash to signal an update (re-translation after forge)
    r.diffRight.parentElement.classList.remove('flash');
    void r.diffRight.parentElement.offsetWidth;
    r.diffRight.parentElement.classList.add('flash');
  }

  _renderSide(container, nameEl, side, links, which) {
    if (!side) return;
    nameEl.textContent = side.name || '';
    const lines = (side.code || '').split('\n');
    const hi = new Map();
    for (const link of links || []) {
      const range = link[which];
      if (!range) continue;
      for (let i = range[0]; i <= range[1]; i++) hi.set(i, link.kind || 'rule');
    }
    container.innerHTML = '';
    lines.forEach((line, i) => {
      const ln = i + 1;
      const row = el('div', 'code-line');
      if (hi.has(ln)) row.classList.add('hl', `hl-${hi.get(ln)}`);
      row.innerHTML =
        `<span class="gutter">${ln}</span>` +
        `<span class="src">${highlight(line, side.lang) || '&nbsp;'}</span>`;
      container.appendChild(row);
    });
  }

  // --- (e) pytest terminal -------------------------------------------------
  on_pytest(ev) {
    const r = this.refs;
    if (ev.result === 'running') {
      r.term.innerHTML =
        `<div class="term-line">$ pytest -q test_equivalence.py  <span class="term-iter">[iter ${ev.iteration}]</span></div>` +
        `<div class="term-line dim">collecting ▍</div>`;
      r.termVerdict.textContent = 'RUNNING';
      r.termVerdict.className = 'term-verdict running';
      return;
    }

    const isGreen = ev.result === 'green';
    const frag = document.createDocumentFragment();
    frag.appendChild(el('div', 'term-line', `$ pytest -q test_equivalence.py  <span class="term-iter">[iter ${ev.iteration}]</span>`));

    for (const c of ev.cases || []) {
      const pass = c.status === 'pass';
      const row = el('div', `term-case ${pass ? 'pass' : 'fail'}`);
      row.innerHTML =
        `<span class="case-mark">${pass ? 'PASS' : 'FAIL'}</span>` +
        `<span class="case-name">${escapeText(c.name)}</span>`;
      frag.appendChild(row);
      if (!pass && (c.cobol != null || c.python != null)) {
        const diff = el('div', 'case-diff');
        diff.innerHTML =
          `<div class="case-oracle"><span class="lbl">cobol oracle</span><code>${escapeText(c.cobol)}</code></div>` +
          `<div class="case-py"><span class="lbl">python out</span><code>${escapeText(c.python)}</code></div>` +
          (c.message ? `<div class="case-msg">${escapeText(c.message)}</div>` : '');
        frag.appendChild(diff);
      }
    }
    frag.appendChild(el('div', `term-summary ${isGreen ? 'green' : 'red'}`, escapeText(ev.summary || '')));

    r.term.innerHTML = '';
    r.term.appendChild(frag);
    r.term.scrollTop = r.term.scrollHeight;

    r.termVerdict.textContent = isGreen ? 'GREEN' : 'RED';
    r.termVerdict.className = `term-verdict ${isGreen ? 'green' : 'red'}`;
    // dramatic full-panel pulse on RED→GREEN transitions
    r.term.closest('.panel').classList.remove('pulse-red', 'pulse-green');
    void r.term.offsetWidth;
    r.term.closest('.panel').classList.add(isGreen ? 'pulse-green' : 'pulse-red');
  }

  // --- (the oracle money-shot banner) -------------------------------------
  on_oracle(ev) {
    const r = this.refs;
    r.oracleBanner.innerHTML =
      `<span class="oracle-tag">DIFFERENTIAL ORACLE</span>` +
      `<span class="oracle-text">Ground truth = <strong>${escapeText(ev.compiler)}</strong> running the original COBOL · ` +
      `${(ev.inputs || []).length} canonical inputs</span>`;
    r.oracleBanner.classList.add('show');
  }

  // --- (f) forge / git-diff -----------------------------------------------
  on_step_status() {} // placeholder; status steps already handled by on_step

  on_forge(ev) {
    const r = this.refs;
    r.forgeReason.textContent = ev.reason || '';
    r.forge.innerHTML = '';

    const header = el('div', 'forge-file');
    header.innerHTML =
      `<span class="git-stat git-${ev.git.status}">${ev.git.status}</span>` +
      `<span class="forge-path">${escapeText(ev.skill)}</span>`;
    r.forge.appendChild(header);

    const diff = el('div', 'forge-diff');
    r.forge.appendChild(diff);

    // Type the additions in line-by-line for the "writing itself" effect.
    const lines = ev.git.additions || [];
    let i = 0;
    const step = () => {
      if (i >= lines.length) {
        const commit = el('div', 'forge-commit', `✓ ${escapeText(ev.git.commit)}`);
        r.forge.appendChild(commit);
        requestAnimationFrame(() => commit.classList.add('in'));
        return;
      }
      const row = el('div', 'diff-add', `<span class="diff-sign">+</span><span>${escapeText(lines[i]) || '&nbsp;'}</span>`);
      diff.appendChild(row);
      requestAnimationFrame(() => row.classList.add('in'));
      diff.scrollTop = diff.scrollHeight;
      i++;
      this._forgeTimer = setTimeout(step, 70);
    };
    step();
    r.forge.closest('.panel').classList.add('forging');
  }

  on_reload(ev) {
    const r = this.refs;
    r.forge.closest('.panel').classList.remove('forging');
    r.forge.closest('.panel').classList.add('reloaded');
    const note = el('div', 'forge-reload', `↻ ${escapeText(ev.label)}`);
    r.forge.appendChild(note);
    requestAnimationFrame(() => note.classList.add('in'));
  }

  // --- (g) download --------------------------------------------------------
  on_download(ev) {
    const r = this.refs;
    this.artifact = ev;
    r.downloadBtn.removeAttribute('disabled');
    r.downloadBtn.classList.add('ready');
  }

  on_done(ev) {
    const r = this.refs;
    r.verdictBadge.textContent = ev.verdict || 'EQUIVALENT';
    r.verdictBadge.classList.add('show', 'good');
    r.stage.dataset.phase = 'done';
    // mark whole rail complete
    for (const node of r.rail.children) {
      node.classList.add('past');
      node.classList.remove('active');
    }
  }

  /** Trigger a browser download of the migrated artifact. */
  triggerDownload() {
    if (!this.artifact) return;
    const blob = new Blob([this.artifact.content], { type: this.artifact.mime || 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = this.artifact.name || 'payroll.py';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
