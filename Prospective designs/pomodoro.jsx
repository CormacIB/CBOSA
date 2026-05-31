// pomodoro.jsx — CBOSA focus timer
// A theme-driven Pomodoro that lives in the permanent headbar:
//   • compact mini-readout (radial ring + MM:SS) docked in the menubar
//   • click to open a popover with a full radial gauge + ASCII segment bar + controls
// Fully functional: real ticking, phase state machine, persists to localStorage
// (start timestamp based, so a refresh resumes exactly where you were).
// All color comes from theme CSS vars (--accent / --fg / --rule …) so it adapts
// to every CBOSA theme automatically; a few body.theme-* rules add signature flair.

const { useState, useEffect, useRef, useCallback } = React;

// ── Config ────────────────────────────────────────────────
const POMO_DEFAULTS = {
  focus: 25 * 60,
  short: 5 * 60,
  long: 15 * 60,
  perSet: 4, // focus sessions before a long break
};
const PHASE = {
  focus: { label: "FOCUS",       glyph: "◉", arc: "var(--accent)" },
  short: { label: "SHORT BREAK", glyph: "○", arc: "var(--fg)" },
  long:  { label: "LONG BREAK",  glyph: "◍", arc: "var(--fg)" },
};
const LS_KEY = "cbosa-pomodoro-v1";

const fmt = (s) => {
  s = Math.max(0, Math.round(s));
  const m = Math.floor(s / 60);
  const ss = s % 60;
  return `${String(m).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
};

// ── CSS (injected once) ───────────────────────────────────
const POMO_CSS = `
.pomo-trigger {
  display: inline-flex; align-items: center; gap: 6px;
  cursor: default; user-select: none;
  color: var(--fg-dim); padding: 0 2px;
  font-variant-numeric: tabular-nums;
}
.pomo-trigger:hover { color: var(--fg); }
.pomo-trigger.running .pomo-mini-time { color: var(--accent); }
.pomo-mini-time { color: var(--fg); letter-spacing: 0.03em; }
.pomo-trigger .pomo-mini-tag {
  font-size: 9px; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--fg-mute);
}
.pomo-mini-ring { display: block; }
.pomo-mini-ring .pulse { transform-origin: center; }
.pomo-trigger.running .pomo-mini-ring .pulse { animation: pomoPulse 1s ease-in-out infinite; }
@keyframes pomoPulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }

/* Popover */
.pomo-pop {
  position: absolute; top: 30px; right: 0; z-index: 4000;
  width: 268px;
  background: var(--bg);
  border: 1px solid var(--rule);
  box-shadow: 0 0 0 1px var(--bg-1), 0 12px 34px rgba(0,0,0,0.5);
  padding: 0;
  font-variant-numeric: tabular-nums;
}
body.theme-paper .pomo-pop, body.theme-karpathy .pomo-pop, body.theme-swiss .pomo-pop {
  box-shadow: 0 12px 30px rgba(0,0,0,0.16);
}
.pomo-pop-head {
  display: flex; align-items: center; gap: 6px;
  height: 24px; padding: 0 8px;
  border-bottom: 1px solid var(--rule);
  background: var(--bg-1);
  font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--fg-dim);
}
.pomo-pop-head .glyph { color: var(--accent); }
.pomo-pop-head .x { margin-left: auto; cursor: default; padding: 0 4px; color: var(--fg-mute); }
.pomo-pop-head .x:hover { color: var(--fg); background: var(--sel); }
.pomo-pop-body { padding: 14px 14px 12px; }

/* Radial gauge */
.pomo-gauge { display: block; margin: 0 auto; }
.pomo-gauge .track { fill: none; stroke: var(--rule); }
.pomo-gauge .arc { fill: none; stroke-linecap: butt; transition: stroke-dashoffset 0.4s linear; }
body.theme-phosphor .pomo-gauge .arc,
body.theme-amber .pomo-gauge .arc,
body.theme-blue .pomo-gauge .arc { filter: drop-shadow(0 0 4px currentColor); }
.pomo-gauge .tick { stroke: var(--fg-mute); }
.pomo-gauge .tick.major { stroke: var(--fg-dim); }
.pomo-gauge .lead { fill: var(--bg); stroke-width: 2; transition: cx 0.4s linear, cy 0.4s linear; }
.pomo-center-phase { font-size: 9px; letter-spacing: 0.18em; fill: var(--fg-dim); text-transform: uppercase; }
.pomo-center-time  { font-weight: 600; letter-spacing: 0.02em; fill: var(--fg); }
.pomo-center-set   { font-size: 9px; letter-spacing: 0.14em; fill: var(--fg-mute); }

/* Session pips */
.pomo-pips { display: flex; align-items: center; justify-content: center; gap: 7px; margin: 10px 0 8px; }
.pomo-pips .pip { color: var(--fg-mute); font-size: 12px; }
.pomo-pips .pip.done { color: var(--accent); }
.pomo-pips .pip.current { color: var(--fg); }

/* ASCII segment bar */
.pomo-ascii {
  white-space: pre; font-family: inherit; font-size: 12px;
  letter-spacing: 1px; line-height: 1.2; text-align: center;
  margin: 2px 0 4px; color: var(--fg-mute);
}
.pomo-ascii .fill { color: var(--accent); }
.pomo-ascii-meta {
  display: flex; justify-content: space-between;
  font-size: 10px; letter-spacing: 0.06em; color: var(--fg-mute);
  text-transform: uppercase; margin-bottom: 12px;
}
.pomo-ascii-meta b { color: var(--fg-dim); font-weight: 500; }

/* Controls */
.pomo-ctrls { display: flex; gap: 6px; }
.pomo-btn {
  flex: 1; text-align: center; cursor: default; user-select: none;
  border: 1px solid var(--rule); background: var(--bg-1);
  color: var(--fg-dim); padding: 5px 0; font: inherit; font-size: 12px;
  letter-spacing: 0.06em; text-transform: uppercase;
}
.pomo-btn:hover { color: var(--fg); border-color: var(--fg-dim); }
.pomo-btn.primary { color: var(--accent); border-color: var(--accent); background: var(--sel); }
body.theme-obsidian .pomo-btn { border-radius: 6px; }
body.theme-swiss .pomo-btn { border-radius: 0; border-width: 1.5px; text-transform: uppercase; font-weight: 600; }

/* Presets row */
.pomo-presets { display: flex; gap: 5px; margin-top: 9px; }
.pomo-preset {
  flex: 1; text-align: center; cursor: default; user-select: none;
  border: 1px solid var(--rule); color: var(--fg-mute);
  padding: 3px 0; font-size: 10px; letter-spacing: 0.06em;
  background: transparent;
}
.pomo-preset:hover { color: var(--fg-dim); border-color: var(--fg-dim); }
.pomo-preset.active { color: var(--accent); border-color: var(--accent); }
body.theme-obsidian .pomo-preset { border-radius: 5px; }

.pomo-foot {
  margin-top: 11px; padding-top: 9px; border-top: 1px dashed var(--rule);
  display: flex; justify-content: space-between; align-items: center;
  font-size: 10px; letter-spacing: 0.06em; color: var(--fg-mute); text-transform: uppercase;
}
.pomo-foot b { color: var(--fg-dim); font-weight: 500; }
.pomo-foot .mute-tog { cursor: default; }
.pomo-foot .mute-tog:hover { color: var(--fg-dim); }
.pomo-foot .mute-tog.on { color: var(--accent); }
`;

function injectPomoCSS() {
  if (document.getElementById("pomo-css")) return;
  const el = document.createElement("style");
  el.id = "pomo-css";
  el.textContent = POMO_CSS;
  document.head.appendChild(el);
}

// ── Soft chime (WebAudio, no asset) ───────────────────────
function chime(kind) {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ac = new Ctx();
    const now = ac.currentTime;
    const notes = kind === "focus" ? [523.25, 659.25] : [659.25, 523.25];
    notes.forEach((f, i) => {
      const o = ac.createOscillator();
      const g = ac.createGain();
      o.type = "sine";
      o.frequency.value = f;
      const t0 = now + i * 0.16;
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.exponentialRampToValueAtTime(0.16, t0 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.34);
      o.connect(g).connect(ac.destination);
      o.start(t0);
      o.stop(t0 + 0.36);
    });
    setTimeout(() => ac.close(), 900);
  } catch (e) { /* no-op */ }
}

// ── State persistence ─────────────────────────────────────
function loadState() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return null;
}
function saveState(s) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(s)); } catch (e) {}
}

// ── Geometry helpers for the gauge ────────────────────────
const GAUGE = { size: 188, cx: 94, cy: 94, r: 70 };
const CIRC = 2 * Math.PI * GAUGE.r;
function polar(frac) {
  // angle from top (12 o'clock), clockwise
  const a = 2 * Math.PI * frac - Math.PI / 2;
  return { x: GAUGE.cx + GAUGE.r * Math.cos(a), y: GAUGE.cy + GAUGE.r * Math.sin(a) };
}

function Gauge({ phase, remaining, total }) {
  const frac = total > 0 ? remaining / total : 0;
  const ph = PHASE[phase];
  const lead = polar(frac);
  // tick marks every minute-ish: 60 ticks
  const ticks = [];
  for (let i = 0; i < 60; i++) {
    const a = (i / 60) * 2 * Math.PI - Math.PI / 2;
    const major = i % 5 === 0;
    const r1 = major ? 80 : 83;
    const r2 = 87;
    ticks.push(
      <line
        key={i}
        className={"tick" + (major ? " major" : "")}
        x1={GAUGE.cx + r1 * Math.cos(a)} y1={GAUGE.cy + r1 * Math.sin(a)}
        x2={GAUGE.cx + r2 * Math.cos(a)} y2={GAUGE.cy + r2 * Math.sin(a)}
        strokeWidth={major ? 1.5 : 1}
      />
    );
  }
  return (
    <svg className="pomo-gauge" width="188" height="188" viewBox="0 0 188 188">
      <g>{ticks}</g>
      <circle className="track" cx={GAUGE.cx} cy={GAUGE.cy} r={GAUGE.r} strokeWidth="7" />
      <circle
        className="arc"
        cx={GAUGE.cx} cy={GAUGE.cy} r={GAUGE.r}
        strokeWidth="7"
        stroke={ph.arc}
        strokeDasharray={CIRC}
        strokeDashoffset={CIRC * (1 - frac)}
        transform={`rotate(-90 ${GAUGE.cx} ${GAUGE.cy})`}
      />
      {frac > 0.001 && frac < 0.999 && (
        <circle className="lead" cx={lead.x} cy={lead.y} r="4.5" stroke={ph.arc} />
      )}
      <text className="pomo-center-phase" x={GAUGE.cx} y={GAUGE.cy - 22} textAnchor="middle">{ph.label}</text>
      <text className="pomo-center-time"  x={GAUGE.cx} y={GAUGE.cy + 9} textAnchor="middle" fontSize="34">{fmt(remaining)}</text>
    </svg>
  );
}

function AsciiBar({ remaining, total }) {
  const CELLS = 22;
  const elapsedFrac = total > 0 ? 1 - remaining / total : 0;
  const filled = Math.round(elapsedFrac * CELLS);
  const fillStr = "█".repeat(filled);
  const emptyStr = "░".repeat(CELLS - filled);
  const pct = Math.round(elapsedFrac * 100);
  return (
    <>
      <div className="pomo-ascii">
        <span className="dim">[</span>
        <span className="fill">{fillStr}</span>
        <span>{emptyStr}</span>
        <span className="dim">]</span>
      </div>
      <div className="pomo-ascii-meta">
        <span>elapsed <b>{pct}%</b></span>
        <span><b>{fmt(total - remaining)}</b> / {fmt(total)}</span>
      </div>
    </>
  );
}

function Pomodoro() {
  const init = loadState();
  const [settings] = useState(() => (init && init.settings) || POMO_DEFAULTS);
  const [preset, setPreset] = useState(() => (init && init.preset) || "classic");
  const [phase, setPhase] = useState(() => (init && init.phase) || "focus");
  const [completed, setCompleted] = useState(() => (init && init.completed) || 0);
  const [muted, setMuted] = useState(() => (init && init.muted) || false);
  const [open, setOpen] = useState(false);

  const durFor = useCallback((p) => settings[p], [settings]);
  const [total, setTotal] = useState(() => (init && init.total) || settings.focus);
  // remaining is derived from running anchor when running, else a held value
  const [running, setRunning] = useState(() => (init && init.running) || false);
  const [remaining, setRemaining] = useState(() => {
    if (init && init.running && init.endsAt) {
      return Math.max(0, (init.endsAt - Date.now()) / 1000);
    }
    return (init && typeof init.remaining === "number") ? init.remaining : settings.focus;
  });
  const endsAtRef = useRef(init && init.running ? init.endsAt : null);
  const rootRef = useRef(null);

  // advance to next phase in the cycle
  const advance = useCallback(() => {
    setRunning(false);
    endsAtRef.current = null;
    if (phase === "focus") {
      const nc = completed + 1;
      setCompleted(nc);
      const nextLong = nc % settings.perSet === 0;
      const np = nextLong ? "long" : "short";
      setPhase(np);
      setTotal(durFor(np));
      setRemaining(durFor(np));
      if (!muted) chime("break");
    } else {
      setPhase("focus");
      setTotal(durFor("focus"));
      setRemaining(durFor("focus"));
      if (!muted) chime("focus");
    }
  }, [phase, completed, settings, durFor, muted]);

  // ticking
  useEffect(() => {
    if (!running) return;
    if (endsAtRef.current == null) endsAtRef.current = Date.now() + remaining * 1000;
    const id = setInterval(() => {
      const rem = (endsAtRef.current - Date.now()) / 1000;
      if (rem <= 0) {
        setRemaining(0);
        advance();
      } else {
        setRemaining(rem);
      }
    }, 250);
    return () => clearInterval(id);
  }, [running, advance]); // eslint-disable-line

  // persist
  useEffect(() => {
    saveState({
      settings, preset, phase, completed, muted, total, running,
      remaining: running ? undefined : remaining,
      endsAt: running ? endsAtRef.current : null,
    });
  }, [settings, preset, phase, completed, muted, total, running, remaining]);

  // close popover on outside click / esc
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, [open]);

  const toggleRun = () => {
    if (running) {
      // pause: freeze remaining
      setRemaining(Math.max(0, (endsAtRef.current - Date.now()) / 1000));
      endsAtRef.current = null;
      setRunning(false);
    } else {
      endsAtRef.current = Date.now() + remaining * 1000;
      setRunning(true);
    }
  };
  const reset = () => {
    setRunning(false);
    endsAtRef.current = null;
    setRemaining(durFor(phase));
    setTotal(durFor(phase));
  };
  const skip = () => advance();

  const applyPreset = (key) => {
    setPreset(key);
    const map = {
      classic: { focus: 25 * 60, short: 5 * 60, long: 15 * 60 },
      short:   { focus: 15 * 60, short: 3 * 60, long: 10 * 60 },
      deep:    { focus: 50 * 60, short: 10 * 60, long: 25 * 60 },
    };
    const cfg = map[key];
    Object.assign(settings, cfg, { perSet: 4 });
    setRunning(false);
    endsAtRef.current = null;
    setTotal(cfg[phase] || cfg.focus);
    setRemaining(cfg[phase] || cfg.focus);
  };

  // mini ring for the headbar
  const miniFrac = total > 0 ? remaining / total : 0;
  const MR = 7, MC = 2 * Math.PI * MR;
  const ph = PHASE[phase];

  // session pips
  const pips = [];
  const doneInSet = completed % settings.perSet;
  for (let i = 0; i < settings.perSet; i++) {
    const isDone = i < doneInSet;
    const isCurrent = i === doneInSet && phase === "focus";
    pips.push(
      <span key={i} className={"pip" + (isDone ? " done" : "") + (isCurrent ? " current" : "")}>
        {isDone ? "◆" : isCurrent ? "◈" : "◇"}
      </span>
    );
  }

  return (
    <span ref={rootRef} style={{ position: "relative", display: "inline-flex" }}>
      <span
        className={"pomo-trigger" + (running ? " running" : "")}
        onClick={() => setOpen(o => !o)}
        title="Focus timer"
      >
        <svg className="pomo-mini-ring" width="16" height="16" viewBox="0 0 16 16">
          <circle cx="8" cy="8" r={MR} fill="none" stroke="var(--rule)" strokeWidth="2" />
          <circle
            className="pulse"
            cx="8" cy="8" r={MR} fill="none" stroke={ph.arc} strokeWidth="2"
            strokeDasharray={MC} strokeDashoffset={MC * (1 - miniFrac)}
            strokeLinecap="round" transform="rotate(-90 8 8)"
          />
        </svg>
        <span className="pomo-mini-time">{fmt(remaining)}</span>
        <span className="pomo-mini-tag">{phase === "focus" ? "focus" : "break"}</span>
      </span>

      {open && (
        <div className="pomo-pop" onClick={e => e.stopPropagation()}>
          <div className="pomo-pop-head">
            <span className="glyph">{ph.glyph}</span>
            <span>focus timer</span>
            <span className="x" onClick={() => setOpen(false)}>✕</span>
          </div>
          <div className="pomo-pop-body">
            <Gauge phase={phase} remaining={remaining} total={total} />
            <div className="pomo-pips">{pips}</div>
            <AsciiBar remaining={remaining} total={total} />
            <div className="pomo-ctrls">
              <span className="pomo-btn primary" onClick={toggleRun}>{running ? "❚❚ pause" : "▶ start"}</span>
              <span className="pomo-btn" onClick={reset}>↺ reset</span>
              <span className="pomo-btn" onClick={skip}>⤼ skip</span>
            </div>
            <div className="pomo-presets">
              {[["classic", "25 · 5"], ["short", "15 · 3"], ["deep", "50 · 10"]].map(([k, lbl]) => (
                <span key={k} className={"pomo-preset" + (preset === k ? " active" : "")} onClick={() => applyPreset(k)}>{lbl}</span>
              ))}
            </div>
            <div className="pomo-foot">
              <span>today: <b>{completed}</b> sessions</span>
              <span className={"mute-tog" + (muted ? "" : " on")} onClick={() => setMuted(m => !m)}>
                {muted ? "♪ muted" : "♪ chime"}
              </span>
            </div>
          </div>
        </div>
      )}
    </span>
  );
}

injectPomoCSS();
Object.assign(window, { Pomodoro });
