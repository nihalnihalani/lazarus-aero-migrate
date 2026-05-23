// app.js — entry point. LIVE BY DEFAULT (task #9): the UI runs completely
// end-to-end against the real FastAPI backend (src/server.py) → real Gemini
// Managed Agent. Drop a COBOL module → real SSE stream → live-trace UI → real
// download. On any failure, a clear ERROR state — never fake data.
//
// BREAK-GLASS only: open with `?mock=1` to replay the cached scripted run
// (mock/mock-run.json — derived from REAL GnuCOBOL golden output). This is the
// Safety-operator fallback for the live demo (45% of score, beta API, day-of
// key); it is OFF by default and never in the live path.

import { Renderer } from './renderer.js';
import { createLivePlayer, driveLiveRun, checkHealth } from './live.js';

const $ = (s) => document.querySelector(s);

const state = {
  renderer: new Renderer(document),
  player: null,
  live: null,        // { runId, abort } from driveLiveRun
  cobol: null,       // loaded source
  filename: 'payroll.cob',
  loaded: false,
  mock: new URLSearchParams(window.location.search).get('mock') === '1',
  mockTimers: [],    // scheduled setTimeout ids for the break-glass replay
};

function bindPlayer(player) {
  state.renderer.attach(player);
  // LivePlayer doesn't emit progress/state (a real stream has no fixed length);
  // those bindings are intentionally omitted.
}

// BREAK-GLASS (?mock=1): replay the cached scripted run through a LivePlayer on
// its own timeline. The Safety-operator fallback if the live demo stalls — NOT
// the default. The cached COBOL outputs are real GnuCOBOL bytes (golden_io.json).
async function startMock() {
  state.mockTimers.forEach(clearTimeout);
  state.mockTimers = [];
  $('#meta-status').textContent = 'BREAK-GLASS · cached run (?mock=1)';
  $('#meta-module').textContent = state.filename;
  $('#meta-agent').textContent = 'antigravity-preview-05-2026';
  $('#clock').textContent = 'cached';

  state.player = createLivePlayer({ iteration_cap: 4, module: state.filename });
  bindPlayer(state.player);
  state.renderer.reset({ iteration_cap: 4, module: state.filename });
  try {
    const res = await fetch('./mock/mock-run.json', { cache: 'no-store' });
    const run = await res.json();
    for (const ev of (run.events || [])) {
      state.mockTimers.push(setTimeout(() => state.player.push(ev), ev.t ?? 0));
    }
  } catch (err) {
    state.player.push({ type: 'step', kind: 'status', status: 'error',
      title: 'cached run unavailable',
      text: `Could not load mock/mock-run.json: ${err.message} (serve over http).` });
  }
}

async function startLive() {
  if (!state.cobol) return;
  if (state.mock) return startMock();   // break-glass replay instead of the live call
  if (state.live) state.live.abort();
  $('#meta-status').textContent = 'connecting to agent…';
  $('#meta-module').textContent = state.filename;
  $('#meta-agent').textContent = 'antigravity-preview-05-2026';
  $('#clock').textContent = 'live';

  // Attach + reset BEFORE driving so the first event (incl. a fatal error) renders.
  state.player = createLivePlayer({ iteration_cap: 4, module: state.filename });
  bindPlayer(state.player);
  state.renderer.reset({ iteration_cap: 4, module: state.filename });

  state.live = await driveLiveRun(state.player, state.cobol, state.filename);
  $('#meta-status').textContent = state.live.runId
    ? `live · run ${state.live.runId}`
    : 'live';
}

function showCobolPreview(text) {
  const box = $('#drop-preview');
  box.textContent = text;
  box.classList.add('show');
}

function onCobolLoaded(text, name) {
  state.loaded = true;
  state.cobol = text;
  state.filename = name;
  showCobolPreview(text);
  $('#drop-name').textContent = name;
  $('#stage').classList.add('armed');
  startLive();
}

function wireDropzone() {
  const dz = $('#dropzone');
  const fileInput = $('#file-input');

  const readFile = (file) => {
    const reader = new FileReader();
    reader.onload = () => onCobolLoaded(String(reader.result), file.name);
    reader.readAsText(file);
  };

  dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.classList.add('over'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('over'));
  dz.addEventListener('drop', (e) => {
    e.preventDefault();
    dz.classList.remove('over');
    const file = e.dataTransfer.files[0];
    if (file) readFile(file);
  });
  dz.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) readFile(fileInput.files[0]);
  });

  // Preload the golden sample so the demo can start with one click.
  $('#preload-btn').addEventListener('click', async (e) => {
    e.stopPropagation();
    try {
      const res = await fetch('./assets/payroll.cob', { cache: 'no-store' });
      const text = await res.text();
      onCobolLoaded(text, 'payroll.cob');
    } catch (err) {
      console.error(err);
      $('#meta-status').textContent = 'could not load sample (serve over http)';
    }
  });
}

function wireControls() {
  // Live stream: ▶ / restart (re)run the migration. There is no pause/scrub of
  // a live stream — those timeline controls are hidden in CSS.
  $('#play-btn').addEventListener('click', () => state.loaded && startLive());
  $('#restart-btn').addEventListener('click', () => state.loaded && startLive());
  $('#download-btn').addEventListener('click', () => state.renderer.triggerDownload());

  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    if (e.code === 'Space') { e.preventDefault(); state.loaded && startLive(); }
    if (e.key === 'r') state.loaded && startLive();
  });
}

async function main() {
  document.body.classList.add(state.mock ? 'mode-mock' : 'mode-live');
  wireDropzone();
  wireControls();
  state.renderer.reset({ iteration_cap: 4 });
  $('#clock').textContent = state.mock ? 'cached' : 'live';

  // BREAK-GLASS mode skips the live backend probe — it replays the cached run.
  if (state.mock) {
    $('#meta-status').textContent =
      'BREAK-GLASS (?mock=1) · drop a module or preload to replay the cached run';
    return;
  }

  // Probe the backend so the operator sees the real state before dropping a file.
  const h = await checkHealth();
  if (!h.ok) {
    $('#meta-status').textContent = 'backend offline — start: uvicorn server:app --app-dir src';
    document.body.classList.add('backend-down');
  } else if (!h.keyPresent) {
    $('#meta-status').textContent = 'LIVE · no GEMINI_API_KEY — set it to run the agent';
    document.body.classList.add('no-key');
  } else {
    $('#meta-status').textContent = 'LIVE · drop a COBOL module to migrate';
  }
}

main();
