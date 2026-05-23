// player.js — schedules canonical events to the renderer.
//
// Two sources, one interface:
//   • MockPlayer  — plays a scripted run on the events' `t` timeline (rehearsal).
//   • LivePlayer  — forwards events as they arrive from the SSE/adapter (real).
// Both emit the same callbacks so the renderer never knows which is driving it.

import { normalizeRun } from './adapter.js';

/** Tiny event bus: on(type, cb) / emit(type, payload). '*' subscribes to all. */
function makeBus() {
  const handlers = new Map();
  return {
    on(type, cb) {
      if (!handlers.has(type)) handlers.set(type, new Set());
      handlers.get(type).add(cb);
      return () => handlers.get(type).delete(cb);
    },
    emit(type, payload) {
      (handlers.get(type) || []).forEach((cb) => cb(payload));
      (handlers.get('*') || []).forEach((cb) => cb(type, payload));
    },
  };
}

export class MockPlayer {
  /** @param {{meta:object, events:object[]}} run normalized canonical run */
  constructor(run) {
    const norm = normalizeRun(run);
    this.meta = norm.meta;
    this.events = norm.events.slice().sort((a, b) => (a.t || 0) - (b.t || 0));
    this.bus = makeBus();
    this.speed = 1;
    this.idx = 0;
    this.elapsed = 0;          // virtual ms consumed
    this.timer = null;
    this.playing = false;
    this.startWall = 0;
    this.baseElapsed = 0;
  }

  on(type, cb) { return this.bus.on(type, cb); }

  get total() {
    const last = this.events[this.events.length - 1];
    return last ? (last.t || 0) : 0;
  }

  play() {
    if (this.playing || this.idx >= this.events.length) return;
    this.playing = true;
    this.startWall = performance.now();
    this.baseElapsed = this.elapsed;
    this.bus.emit('state', { playing: true });
    this._schedule();
  }

  pause() {
    if (!this.playing) return;
    this.playing = false;
    clearTimeout(this.timer);
    this.elapsed = this.baseElapsed + (performance.now() - this.startWall) * this.speed;
    this.bus.emit('state', { playing: false });
  }

  toggle() { this.playing ? this.pause() : this.play(); }

  setSpeed(mult) {
    // Re-anchor so the change applies from now, not retroactively.
    if (this.playing) {
      this.elapsed = this.baseElapsed + (performance.now() - this.startWall) * this.speed;
      this.baseElapsed = this.elapsed;
      this.startWall = performance.now();
    }
    this.speed = mult;
    this.bus.emit('state', { speed: mult });
    if (this.playing) { clearTimeout(this.timer); this._schedule(); }
  }

  restart() {
    clearTimeout(this.timer);
    this.playing = false;
    this.idx = 0;
    this.elapsed = 0;
    this.baseElapsed = 0;
    this.bus.emit('reset', { meta: this.meta });
    this.bus.emit('state', { playing: false });
  }

  /** Skip to the end instantly (all events fire in order). Useful in rehearsal. */
  finish() {
    clearTimeout(this.timer);
    this.playing = false;
    while (this.idx < this.events.length) this.bus.emit('event', this.events[this.idx++]);
    this.elapsed = this.total;
    this.bus.emit('state', { playing: false });
    this.bus.emit('progress', { elapsed: this.total, total: this.total });
  }

  _now() {
    return this.baseElapsed + (performance.now() - this.startWall) * this.speed;
  }

  _schedule() {
    if (!this.playing) return;
    if (this.idx >= this.events.length) {
      this.playing = false;
      this.bus.emit('state', { playing: false });
      return;
    }
    const ev = this.events[this.idx];
    const target = ev.t || 0;
    const waitVirtual = Math.max(0, target - this._now());
    const waitReal = waitVirtual / this.speed;

    this.timer = setTimeout(() => {
      if (!this.playing) return;
      this.bus.emit('event', ev);
      this.bus.emit('progress', { elapsed: target, total: this.total });
      this.idx += 1;
      this._schedule();
    }, waitReal);

    // Smooth progress between events for the scrubber.
    this.bus.emit('progress', { elapsed: this._now(), total: this.total });
  }
}

export class LivePlayer {
  /** Construct from a normalized run skeleton (meta only); events get pushed. */
  constructor(meta = {}) {
    this.meta = meta;
    this.bus = makeBus();
  }
  on(type, cb) { return this.bus.on(type, cb); }
  /** Feed one canonical Event (already adapted) into the renderer. */
  push(ev) { this.bus.emit('event', ev); }
  reset() { this.bus.emit('reset', { meta: this.meta }); }
  // No-op playback controls so the same UI buttons work in live mode.
  play() {} pause() {} toggle() {} restart() { this.reset(); } finish() {} setSpeed() {}
}
