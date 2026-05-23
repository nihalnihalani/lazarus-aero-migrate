// app.js — entry point.
//
// DEFAULT = LIVE: drop a COBOL module → POST to the FastAPI backend → real
// Gemini Managed Agent stream → live-trace UI → real download. (task #9)
//
// FALLBACK = ?mock=1: plays the bundled scripted run (mock/mock-run.json) with
// no backend. This is the demo Safety net (DEMO_SCRIPT.md de-risking) and the
// offline rehearsal path — OFF by default, never in the live path.

import { MockPlayer } from './player.js';
import { Renderer } from './renderer.js';
import { createLivePlayer, driveLiveRun } from './live.js';

const $ = (s) => document.querySelector(s);

const MOCK = new URLSearchParams(location.search).get('mock') === '1';
const LIVE_MODE = new URLSearchParams(location.search).get('raw') === '1' ? 'raw' : 'canonical';

const state = {
  run: null,        // raw mock-run.json (mock fallback only)
  player: null,
  renderer: new Renderer(document),
  loaded: false,    // a COBOL module has been dropped/preloaded
  cobol: null,      // the loaded source (for live re-runs)
  filename: 'payroll.cob',
  live: null,       // { player, runId, abort, downloadUrl } from startLiveRun
};

async function loadMock() {
  const res = await fetch('./mock/mock-run.json', { cache: 'no-store' });
  if (!res.ok) throw new Error(`mock-run.json: ${res.status}`);
  return res.json();
}

function bindPlayer(player) {
  state.renderer.attach(player);
  player.on('progress', ({ elapsed, total }) => {
    const pct = total ? Math.min(100, (elapsed / total) * 100) : 0;
    $('#scrub-fill').style.width = pct + '%';
    $('#clock').textContent = fmt(elapsed) + ' / ' + fmt(total);
  });
  player.on('state', ({ playing, speed }) => {
    if (playing != null) $('#play-btn').dataset.playing = String(playing);
    if (speed != null) {
      for (const b of document.querySelectorAll('.speed-btn')) {
        b.classList.toggle('active', Number(b.dataset.speed) === speed);
      }
    }
  });
}

function fmt(ms) {
  const s = Math.max(0, ms / 1000);
  return s.toFixed(1) + 's';
}

// --- mock fallback run -----------------------------------------------------
function startMockRun() {
  if (!state.run) return;
  if (state.player) state.player.pause();
  state.player = new MockPlayer(state.run);
  bindPlayer(state.player);
  state.renderer.reset(state.player.meta);
  $('#meta-module').textContent = state.player.meta.module || 'payroll.cob';
  $('#meta-agent').textContent = state.player.meta.base_agent || 'lazarus';
  state.player.play();
}

// --- live run --------------------------------------------------------------
async function startLive() {
  if (!state.cobol) return;
  if (state.live) state.live.abort();
  $('#meta-status').textContent = 'connecting to agent…';
  $('#meta-module').textContent = state.filename;
  $('#meta-agent').textContent = 'antigravity-preview-05-2026';
  $('#play-btn').dataset.playing = 'true';
  $('#clock').textContent = 'live';

  // Create + ATTACH + reset BEFORE driving the run, so the first pushed event
  // (including a backend-unreachable error) renders into a clean trace.
  state.player = createLivePlayer({ iteration_cap: 4, module: state.filename });
  bindPlayer(state.player);
  state.renderer.reset({ iteration_cap: 4, module: state.filename });

  state.live = await driveLiveRun(state.player, state.cobol, state.filename, { mode: LIVE_MODE });
  if (state.live.runId) {
    // Live download pulls the real artifact from the backend by run_id.
    state.renderer.setDownloadUrl(state.live.downloadUrl, state.filename.replace(/\.cob$/, '.py'));
    $('#meta-status').textContent = `live · run ${state.live.runId}`;
  } else {
    $('#meta-status').textContent = 'backend unreachable — see trace (or use ?mock=1)';
  }
}

function startRun() {
  if (MOCK) startMockRun();
  else startLive();
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
  startRun();
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
    }
  });
}

function wireControls() {
  $('#play-btn').addEventListener('click', () => {
    // In live mode there's no pause/resume of a stream; (re)start the run.
    if (MOCK && state.player) { state.player.toggle(); return; }
    if (state.loaded) startRun();
  });
  $('#restart-btn').addEventListener('click', () => state.loaded && startRun());
  $('#skip-btn').addEventListener('click', () => MOCK && state.player && state.player.finish());
  for (const b of document.querySelectorAll('.speed-btn')) {
    b.addEventListener('click', () => MOCK && state.player && state.player.setSpeed(Number(b.dataset.speed)));
  }
  $('#download-btn').addEventListener('click', () => state.renderer.triggerDownload());

  // Keyboard (rehearsal): space=play/restart, r=restart, f=finish (mock only).
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    if (e.code === 'Space') { e.preventDefault(); (MOCK && state.player) ? state.player.toggle() : (state.loaded && startRun()); }
    if (e.key === 'r') state.loaded && startRun();
    if (e.key === 'f') MOCK && state.player && state.player.finish();
  });
}

async function main() {
  wireDropzone();
  wireControls();
  state.renderer.reset({ iteration_cap: 4 });

  if (MOCK) {
    // Fallback path: preload the scripted run, no backend needed.
    document.body.classList.add('mode-mock');
    try {
      state.run = await loadMock();
      $('#meta-status').textContent = 'FALLBACK (mock) · drop a module to begin';
    } catch (err) {
      console.error(err);
      $('#meta-status').textContent = 'could not load mock-run.json (serve over http)';
    }
  } else {
    // Live default: no preload; transport timeline is hidden (stream has no fixed length).
    document.body.classList.add('mode-live');
    $('#meta-status').textContent = 'LIVE · drop a COBOL module to migrate';
    $('#clock').textContent = 'live';
  }
}

main();
