// app.jsx — top-level CBOSA window

const { useState, useMemo, useEffect } = React;

// ──────────────────────────────────────────────────────────
// ASCII header art — six thematic presets, switchable via Tweaks
// ──────────────────────────────────────────────────────────
const ASCII_ARTS = {
  // 1. ORBIT — satellite passing over a horizon, packet drop to subsystems
  orbital: `      ·       ✦         .             ·            ✦         .
                       ╭──╮                                       .
   ✦   · ─ · ─ · ─ · ─ │◉◉│ ─ · ─ · ─ · ─ · ─ · ─ · ─ · ─ · ─ ↘
                       ╰──╯╲                              apogee
       .                    ╲── pkt 0x4A → notes·fin·mail·lms
   ━━ C ━━━━ B ━━━━ O ━━━━ S ━━━━ A ━━━ cbosa · sat-07 · v0.1 ━━`,

  // 2. CIRCUIT — schematic with discrete components, ground rail
  circuit: `   +5V ●━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
              │        │        │        │        │
            ▰▰R₁      ╪C₂     ▼▽D₃     ⏛L₄      ⬡Q₅
              │        │        │        │        │
              C        B        O        S        A
              │        │        │        │        │
   GND ●━━━━┻━━━━━━━━┻━━━━━━━━┻━━━━━━━━┻━━━━━━━━┛
        ── cbosa · personal operating system · rev 0.1 ──`,

  // 3. TOPO — nested contour rings with peak elevations, compass rose
  topo: `    ╱⌒⌒⌒⌒⌒╲     ╱⌒⌒⌒⌒⌒╲     ╱⌒⌒⌒⌒⌒╲     ╱⌒⌒⌒⌒⌒╲     ╱⌒⌒⌒⌒⌒╲
   │ ╱⌒⌒⌒╲ │   │ ╱⌒⌒⌒╲ │   │ ╱⌒⌒⌒╲ │   │ ╱⌒⌒⌒╲ │   │ ╱⌒⌒⌒╲ │     ▲ N
   ││  C  ││   ││  B  ││   ││  O  ││   ││  S  ││   ││  A  ││    ◯─╫─◯
    ╲ ╲___╱ ╱   ╲ ╲___╱ ╱   ╲ ╲___╱ ╱   ╲ ╲___╱ ╱   ╲ ╲___╱ ╱     ▼ S
     ╲_____╱     ╲_____╱     ╲_____╱     ╲_____╱     ╲_____╱
      1247m       920m        705m        480m        1102m
       ── cbosa · vault topology · 38.5°N −77.0°W ──`,

  // 4. WAVEFORM — oscilloscope trace with axis, phase markers
  waveform: `   +V ┤      ╭───╮               ╭───╮             ╭───╮
        │     ╱     ╲             ╱     ╲           ╱     ╲
      0 ┼────╱───────╲───────────╱───────╲─────────╱───────╲────→ t
        │             ╲         ╱         ╲       ╱         ╲___
   −V   ┤              ╲_______╱           ╲_____╱
            C          B            O           S       A
        ── cbosa · personal os · ψ₀ = 432 Hz · phase φ ──`,

  // 5. CONSTELLATION — star chart with named nodes
  constellation: `         ·    ✦         .              ✦            ·
                 ✦C                  · O                ·
                   ╲                 ╱╲
                    ╲               ╱  ╲
        ·            ·B─ ─ ─ ─ ─ ─ ╱ ─ ─·S            ✦
                       ╲          ╱       ╲
         .              ╲        ╱          ╲
                          ──── ✦ ────         ✦A           ·
       ─── cbosa · constellation C·B·OS·A · mag −0.7 ───`,

  // 6. BANNER — figlet "ANSI Shadow" block letters
  banner: `    ██████╗██████╗  ██████╗ ███████╗ █████╗
   ██╔════╝██╔══██╗██╔═══██╗██╔════╝██╔══██╗
   ██║     ██████╔╝██║   ██║███████╗███████║
   ██║     ██╔══██╗██║   ██║╚════██║██╔══██║
   ╚██████╗██████╔╝╚██████╔╝███████║██║  ██║
    ╚═════╝╚═════╝  ╚═════╝ ╚══════╝╚═╝  ╚═╝
         cbosa · personal operating system · v0.1`,
};
const ASCII_ART_KEYS = ["orbital", "circuit", "topo", "waveform", "constellation", "banner"];

function App() {
  // Allow URL hash to override default theme so explorations canvas can pin a variant
  const hashTheme = (typeof window !== "undefined" && window.location.hash.match(/theme=([a-z]+)/) || [])[1];
  const defaults = hashTheme
    ? { ...window.__TWEAK_DEFAULTS__, theme: hashTheme,
        scanlines: hashTheme === "phosphor" || hashTheme === "amber" || hashTheme === "blue" || hashTheme === "paper",
        crtGlow:   hashTheme === "phosphor" || hashTheme === "amber" || hashTheme === "blue",
        asciiHeader: hashTheme !== "swiss" ? window.__TWEAK_DEFAULTS__.asciiHeader : true }
    : window.__TWEAK_DEFAULTS__;
  const [t, setTweak] = useTweaks(defaults);

  const [currentNote, setCurrentNote] = useState("2026-05-11");
  const [tagFilter, setTagFilter] = useState(null);
  const [query, setQuery] = useState("");
  const [tasks, setTasks] = useState(window.TASKS);
  const [activeMenu, setActiveMenu] = useState(null);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [cmdQuery, setCmdQuery] = useState("");
  const [cmdIdx, setCmdIdx] = useState(0);

  const backlinks = useMemo(() => deriveBacklinks(NOTES), []);
  const note = useMemo(() => NOTES.find(n => n.name === currentNote), [currentNote]);

  // Apply theme & art settings to body
  useEffect(() => {
    document.body.className = [
      "theme-" + t.theme,
      t.crtGlow ? "crt-glow" : "",
      t.scanlines ? "scanlines" : "",
      t.dither ? "dither" : "",
      "density-" + t.density,
    ].filter(Boolean).join(" ");
  }, [t.theme, t.crtGlow, t.scanlines, t.dither, t.density]);

  useEffect(() => {
    document.documentElement.style.setProperty("--app-font", `"${t.fontFamily}", "JetBrains Mono", ui-monospace, monospace`);
    document.body.style.fontFamily = `"${t.fontFamily}", "JetBrains Mono", ui-monospace, monospace`;
    document.body.style.fontSize = t.fontSize + "px";
  }, [t.fontFamily, t.fontSize]);

  // Command palette keybind
  useEffect(() => {
    const h = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") {
        e.preventDefault();
        setCmdOpen(true);
      } else if (e.key === "Escape") {
        setCmdOpen(false);
        setActiveMenu(null);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  const toggleTask = (id) =>
    setTasks(xs => xs.map(x => x.id === id ? { ...x, done: !x.done } : x));

  const openNote = (name) => {
    const hit = NOTES.find(n => n.name === name || n.title === name);
    if (hit) {
      setCurrentNote(hit.name);
      setCmdOpen(false);
    }
  };

  // Cmd palette items: notes + panels + commands
  const cmdItems = useMemo(() => {
    const q = cmdQuery.toLowerCase();
    const noteItems = NOTES.map(n => ({ kind: "note", label: n.title, sub: n.folder + "/", action: () => openNote(n.name) }));
    const cmds = [
      { kind: "command", label: "today's daily note", action: () => openNote("2026-05-11") },
      { kind: "command", label: "switch theme: phosphor", action: () => setTweak("theme", "phosphor") },
      { kind: "command", label: "switch theme: amber", action: () => setTweak("theme", "amber") },
      { kind: "command", label: "switch theme: blue (3270)", action: () => setTweak("theme", "blue") },
      { kind: "command", label: "switch theme: paper", action: () => setTweak("theme", "paper") },
      { kind: "command", label: "toggle scanlines", action: () => setTweak("scanlines", !t.scanlines) },
      { kind: "command", label: "toggle crt glow", action: () => setTweak("crtGlow", !t.crtGlow) },
      { kind: "panel", label: "add panel: graph view" },
      { kind: "panel", label: "add panel: backlinks" },
      { kind: "panel", label: "add panel: capture" },
    ];
    const all = [...cmds, ...noteItems];
    if (!q) return all;
    return all.filter(c => c.label.toLowerCase().includes(q) || (c.sub || "").toLowerCase().includes(q));
  }, [cmdQuery, t.scanlines, t.crtGlow]);

  useEffect(() => { setCmdIdx(0); }, [cmdQuery, cmdOpen]);

  const runCmd = (item) => { if (item && item.action) item.action(); setCmdOpen(false); };

  // Apply right-column composition based on density
  const wsCols = t.density === "compact" ? "240px 1fr 300px" : t.density === "comfy" ? "300px 1fr 360px" : "280px 1fr 340px";

  return (
    <>
      {/* App window chrome */}
      <div className="winchrome">
        <div className="winbtns">
          <span className="winbtn x" />
          <span className="winbtn" />
          <span className="winbtn" />
        </div>
        <div className="wintitle">
          <b>CBOSA</b> · <span>~/cbosa/vault</span> · <span style={{ color: "var(--accent)" }}>● local</span>
        </div>
        <div style={{ marginLeft: "auto", color: "var(--fg-mute)", fontSize: 11, letterSpacing: "0.06em" }}>
          {t.theme.toUpperCase()} · {t.fontFamily.replace(/^\w/, c => c.toUpperCase())} · {t.fontSize}px
        </div>
      </div>

      {/* Menu bar */}
      <div className="menubar">
        {["File", "Edit", "View", "Workspace", "Panels", "Theme", "Help"].map(m => (
          <span
            key={m}
            className={"menu" + (activeMenu === m ? " active" : "")}
            onClick={() => setActiveMenu(activeMenu === m ? null : m)}
          >
            {m}
          </span>
        ))}
        <div className="right">
          <Pomodoro />
          <span>tue · <b>10:14</b></span>
          <span>cpu <b>4%</b></span>
          <span>ai: <b>null</b></span>
        </div>
      </div>

      {/* Optional ASCII header */}
      {t.asciiHeader && (
        <div style={{ padding: "8px 16px 2px", borderBottom: "1px solid var(--rule)", background: "var(--bg-1)" }}>
          <pre className="ascii-header">{ASCII_ARTS[t.asciiArt] || ASCII_ARTS.orbital}</pre>
        </div>
      )}

      {/* Workspace */}
      <div className="workspace" style={{ gridTemplateColumns: wsCols }}>
        {/* LEFT: Note Browser */}
        <Panel glyph="[N]" tabs={["NOTE BROWSER", "GRAPH"]} activeTab={0} onTabChange={() => {}}>
          <NoteBrowser
            notes={NOTES}
            currentNote={currentNote}
            onSelect={setCurrentNote}
            tagFilter={tagFilter}
            onTagFilter={setTagFilter}
            query={query}
            onQuery={setQuery}
          />
          {t.artSlots && (
            <div className="artslot" style={{ marginTop: 8 }}>
              [ vault icon slot ]
            </div>
          )}
        </Panel>

        {/* CENTER: Note Editor */}
        <div className="panel" style={{ borderRight: "1px solid var(--rule)" }}>
          <div className="editor-bar">
            <span className="crumb">
              <span style={{ color: "var(--accent)" }}>~/cbosa/vault/</span>
              <b>{note ? note.folder + "/" + note.name + ".md" : "—"}</b>
            </span>
            <div className="right">
              <span className="tog on">[edit]</span>
              <span className="tog">[preview]</span>
              <span className="tog">[split]</span>
              <span className="mute">·</span>
              <span className="tog">⟲ saved 12s ago</span>
            </div>
          </div>
          <div className="panel-body" style={{ padding: 0 }}>
            <NoteEditor
              note={note}
              allNotes={NOTES}
              backlinks={backlinks}
              onOpenNote={openNote}
              artSlots={t.artSlots}
            />
          </div>
        </div>

        {/* RIGHT: stack of three small panels */}
        <div className="stack">
          <Panel glyph="[T]" tabs={["TASKS"]} activeTab={0} style={{ flex: "0 0 38%", minHeight: 200, borderRight: "none", borderBottom: "1px solid var(--rule)" }}>
            <Tasks tasks={tasks} onToggle={toggleTask} />
          </Panel>
          <Panel glyph="[$]" tabs={["FINANCE", "CANVAS"]} activeTab={0} style={{ flex: "0 0 34%", minHeight: 180, borderRight: "none", borderBottom: "1px solid var(--rule)" }}>
            <Finance data={FINANCE} artSlots={t.artSlots} />
            <div className="rule-h">{"┄".repeat(40)}</div>
            <CanvasList items={CANVAS} />
          </Panel>
          <Panel glyph="[@]" tabs={["EMAIL"]} activeTab={0} style={{ flex: 1, minHeight: 180, borderRight: "none" }}>
            <Email emails={EMAILS} />
          </Panel>
        </div>
      </div>

      {/* Status bar */}
      <div className="statusbar">
        <span>● <b>connected</b></span>
        <span className="sep">│</span>
        <span>vault: <b>{NOTES.length}</b> notes</span>
        <span className="sep">│</span>
        <span>tasks: <b className="acc">{tasks.filter(x => !x.done).length}</b> open</span>
        <span className="sep">│</span>
        <span>theme: <b>{t.theme}</b></span>
        <div className="right">
          <span><span className="kbd">Ctrl+P</span> palette</span>
          <span><span className="kbd">Ctrl+S</span> save</span>
          <span><span className="kbd">⌘,</span> theme.toml</span>
        </div>
      </div>

      {/* Command palette */}
      {cmdOpen && (
        <div className="cmdpal-backdrop" onClick={() => setCmdOpen(false)}>
          <div className="cmdpal" onClick={e => e.stopPropagation()}>
            <div className="cmdpal-head">
              <span style={{ color: "var(--accent)" }}>{">"}</span>
              <input
                autoFocus
                value={cmdQuery}
                onChange={e => setCmdQuery(e.target.value)}
                onKeyDown={e => {
                  if (e.key === "ArrowDown") { e.preventDefault(); setCmdIdx(i => Math.min(cmdItems.length - 1, i + 1)); }
                  else if (e.key === "ArrowUp") { e.preventDefault(); setCmdIdx(i => Math.max(0, i - 1)); }
                  else if (e.key === "Enter") { e.preventDefault(); runCmd(cmdItems[cmdIdx]); }
                }}
                placeholder="search notes, panels, commands…"
              />
              <span style={{ color: "var(--fg-mute)", fontSize: 11 }}>{cmdItems.length} hits</span>
            </div>
            <div className="cmdpal-list">
              {cmdItems.slice(0, 60).map((it, i) => (
                <div
                  key={i}
                  className={"cmdpal-row" + (i === cmdIdx ? " active" : "")}
                  onMouseEnter={() => setCmdIdx(i)}
                  onClick={() => runCmd(it)}
                >
                  <span className="kind">{it.kind}</span>
                  <span style={{ flex: 1 }}>{it.label}</span>
                  {it.sub && <span style={{ color: "var(--fg-mute)" }}>{it.sub}</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tweaks panel */}
      <TweaksPanel title="Tweaks">
        <TweakSection label="Aesthetic" />
        <TweakSelect
          label="Theme"
          value={t.theme}
          options={["phosphor", "amber", "blue", "paper", "karpathy", "obsidian", "swiss"]}
          onChange={v => setTweak("theme", v)}
        />

        <TweakSection label="Typography" />
        <TweakSelect
          label="Font"
          value={t.fontFamily}
          options={["JetBrains Mono", "IBM Plex Mono", "VT323"]}
          onChange={v => setTweak("fontFamily", v)}
        />
        <TweakSlider
          label="Size"
          value={t.fontSize}
          min={11}
          max={18}
          step={1}
          unit="px"
          onChange={v => setTweak("fontSize", v)}
        />
        <TweakRadio
          label="Density"
          value={t.density}
          options={["compact", "regular", "comfy"]}
          onChange={v => setTweak("density", v)}
        />

        <TweakSection label="CRT / Art" />
        <TweakToggle label="Scanlines"     value={t.scanlines}    onChange={v => setTweak("scanlines", v)} />
        <TweakToggle label="Phosphor glow" value={t.crtGlow}      onChange={v => setTweak("crtGlow", v)} />
        <TweakToggle label="ASCII header"  value={t.asciiHeader}  onChange={v => setTweak("asciiHeader", v)} />
        <TweakSelect
          label="Header art"
          value={t.asciiArt || "orbital"}
          options={ASCII_ART_KEYS}
          onChange={v => setTweak("asciiArt", v)}
        />
        <TweakToggle label="Dither bg"     value={t.dither}       onChange={v => setTweak("dither", v)} />
        <TweakToggle label="Art slots"     value={t.artSlots}     onChange={v => setTweak("artSlots", v)} />
      </TweaksPanel>
    </>
  );
}

ReactDOM.createRoot(document.getElementById("app")).render(<App />);
