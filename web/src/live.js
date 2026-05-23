// live.js — real end-to-end SSE client. Bridges the FastAPI backend
// (src/server.py) to a LivePlayer: POST the COBOL, subscribe to the
// text/event-stream, push canonical Events into the renderer as they arrive.
//
// Handles BOTH backend contract options (configurable, default 'canonical'):
//   • 'canonical' — server already emits canonical Event JSON per SSE line.
//                   The UI does zero transform. (recommended; least UI risk)
//   • 'raw'       — server forwards raw Gemini step.* events; we adapt in the
//                   browser via StreamAdapter (handles the start/delta/stop
//                   lifecycle + the 7 derived events still come pre-canonical).
//
// Endpoint contract (proposed to backend-eng; reconcile in ENDPOINTS below):
//   POST {base}/api/migrate   { cobol, filename } -> { run_id }
//   GET  {base}/api/stream/{run_id}               -> text/event-stream
//   GET  {base}/api/download/{run_id}             -> migrated module bytes

import { LivePlayer } from './player.js';
import { StreamAdapter } from './adapter.js';

export const ENDPOINTS = {
  base: '',                                   // same-origin by default
  migrate: (b) => `${b}/api/migrate`,
  stream: (b, id) => `${b}/api/stream/${id}`,
  download: (b, id) => `${b}/api/download/${id}`,
};

/**
 * Create a LivePlayer for a run. Caller MUST attach the renderer to it AND
 * reset the renderer before calling driveLiveRun(), so the very first pushed
 * event (incl. a backend-unreachable error) renders into the trace.
 * @param {object} meta
 * @returns {LivePlayer}
 */
export function createLivePlayer(meta = {}) {
  return new LivePlayer(meta);
}

/**
 * Drive a live migration on an ALREADY-ATTACHED player.
 * @param {LivePlayer} player - from createLivePlayer(), renderer already attached
 * @param {string} cobol   - the COBOL source to migrate
 * @param {string} filename
 * @param {object} opts    - { base, mode:'canonical'|'raw' }
 * @returns {Promise<{ runId, abort, downloadUrl }>}
 */
export async function driveLiveRun(player, cobol, filename, opts = {}) {
  const base = opts.base ?? ENDPOINTS.base;
  const mode = opts.mode ?? 'canonical';

  // 1. Kick off the migration; get a run_id to subscribe to.
  let runId;
  try {
    const res = await fetch(ENDPOINTS.migrate(base), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cobol, filename }),
    });
    if (!res.ok) throw new Error(`migrate ${res.status}`);
    const data = await res.json().catch(() => ({}));
    runId = data.run_id || data.runId || data.id;
  } catch (err) {
    player.push({ type: 'step', kind: 'status', status: 'error',
                  title: 'backend unreachable',
                  text: `Could not start live run: ${err.message}. ` +
                        `Is src/server.py running? Fallback: append ?mock=1.` });
    return { runId: null, abort: () => {}, downloadUrl: null };
  }

  // 2. Subscribe to the SSE stream.
  const adapter = mode === 'raw' ? new StreamAdapter() : null;
  const es = new EventSource(ENDPOINTS.stream(base, runId));

  const handle = (raw) => {
    let payload;
    try { payload = JSON.parse(raw); } catch { return; }
    if (mode === 'raw') {
      // Raw mode: events tagged event_type are Gemini steps → adapt;
      // anything already in canonical shape (the 7 derived events) passes through.
      if (payload.event_type) {
        for (const ev of adapter.ingest(payload)) player.push(ev);
      } else if (payload.type) {
        player.push(payload);
      }
    } else {
      // Canonical mode: push as-is.
      if (payload.type) player.push(payload);
    }
    if (payload.type === 'done' || payload.event_type === 'interaction.completed') {
      es.close();
    }
  };

  es.onmessage = (e) => handle(e.data);
  es.onerror = () => {
    // EventSource auto-reconnects; surface a soft warning, don't spam.
    if (es.readyState === EventSource.CLOSED) {
      player.push({ type: 'step', kind: 'status', status: 'error',
                    title: 'stream closed', text: 'SSE connection closed.' });
    }
  };

  return {
    runId,
    abort: () => es.close(),
    downloadUrl: ENDPOINTS.download(base, runId),
  };
}
