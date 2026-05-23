// app.js — entry point. LIVE ONLY (task #9): the UI runs completely end-to-end
// against the real FastAPI backend (src/server.py) → real Gemini Managed Agent.
// There is NO scripted/mock playback. Drop a COBOL module → real SSE stream →
// live-trace UI → real download. On any failure, a clear ERROR state — never
// fake data, never a fallback animation.

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
};

function bindPlayer(player) {
  state.renderer.attach(player);
  // LivePlayer doesn't emit progress/state (a real stream has no fixed length);
  // those bindings are intentionally omitted.
}

async function startLive() {
  if (!state.cobol) return;
  if (state.live) state.live.abort();
  $('#meta-status').textContent = 'connecting to agent…';
  $('#meta-module').textContent = state.filename;
  $('#meta-agent').textContent = 'antigravity-preview-05-2026';
  $('#play-btn').dataset.playing = 'true';
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
  document.body.classList.add('mode-live');
  wireDropzone();
  wireControls();
  state.renderer.reset({ iteration_cap: 4 });
  $('#clock').textContent = 'live';

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
