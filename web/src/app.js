// app.js — entry point. Loads the bundled mock run, wires the drop-zone,
// playback controls, and the download button. Standalone: needs no API.

import { MockPlayer } from './player.js';
import { Renderer } from './renderer.js';

const $ = (s) => document.querySelector(s);

const state = {
  run: null,        // raw mock-run.json
  player: null,
  renderer: new Renderer(document),
  loaded: false,    // a COBOL module has been dropped/preloaded
};

async function loadMock() {
  const res = await fetch('./mock/mock-run.json', { cache: 'no-store' });
  if (!res.ok) throw new Error(`mock-run.json: ${res.status}`);
  return res.json();
}

function bindPlayer(player) {
  // Tear down a previous player's UI bindings by rebuilding the renderer attach.
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

function startRun() {
  if (!state.run) return;
  if (state.player) state.player.pause();
  state.player = new MockPlayer(state.run);
  bindPlayer(state.player);
  state.renderer.reset(state.player.meta);
  $('#meta-module').textContent = state.player.meta.module || 'payroll.cob';
  $('#meta-agent').textContent = state.player.meta.base_agent || 'lazarus';
  state.player.play();
}

function showCobolPreview(text) {
  const box = $('#drop-preview');
  box.textContent = text;
  box.classList.add('show');
}

function onCobolLoaded(text, name) {
  state.loaded = true;
  showCobolPreview(text);
  $('#drop-name').textContent = name;
  $('#stage').classList.add('armed');
  // Auto-start the scripted migration — this is the demo beat.
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
    if (!state.player) { startRun(); return; }
    state.player.toggle();
  });
  $('#restart-btn').addEventListener('click', () => {
    if (state.loaded) startRun();
  });
  $('#skip-btn').addEventListener('click', () => state.player && state.player.finish());
  for (const b of document.querySelectorAll('.speed-btn')) {
    b.addEventListener('click', () => state.player && state.player.setSpeed(Number(b.dataset.speed)));
  }
  $('#download-btn').addEventListener('click', () => state.renderer.triggerDownload());

  // Keyboard: space=play/pause, r=restart, f=finish (rehearsal-friendly).
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    if (e.code === 'Space') { e.preventDefault(); state.player ? state.player.toggle() : startRun(); }
    if (e.key === 'r') state.loaded && startRun();
    if (e.key === 'f') state.player && state.player.finish();
  });
}

async function main() {
  wireDropzone();
  wireControls();
  state.renderer.reset({ iteration_cap: 4 });
  try {
    state.run = await loadMock();
    $('#meta-status').textContent = 'mock run loaded · drop a module to begin';
  } catch (err) {
    console.error(err);
    $('#meta-status').textContent = 'could not load mock-run.json (serve over http)';
  }
}

main();
