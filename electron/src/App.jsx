import { useState, useEffect, useCallback, useRef } from 'react'
import NoteBrowser from './components/NoteBrowser.jsx'
import NoteEditor from './components/NoteEditor.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import PomodoroPanel from './components/PomodoroPanel.jsx'
import StatusBar from './components/StatusBar.jsx'
import CaptureOverlay from './components/CaptureOverlay.jsx'
import { getDaily } from './api.js'

const THEMES = [
  { id: 'phosphor', label: 'P', bg: '#000',     fg: '#33ff66', font: 'JetBrains Mono' },
  { id: 'amber',    label: 'A', bg: '#0a0500',  fg: '#ffb000', font: 'JetBrains Mono' },
  { id: 'blue',     label: 'B', bg: '#00131f',  fg: '#6bc1ff', font: 'JetBrains Mono' },
  { id: 'paper',    label: 'W', bg: '#f5f1e8',  fg: '#1a1a1a', font: 'IBM Plex Mono'  },
  { id: 'karpathy', label: 'K', bg: '#fdfaf0',  fg: '#0033cc', font: 'IBM Plex Mono'  },
  { id: 'obsidian', label: 'O', bg: '#1e1e2e',  fg: '#cba6f7', font: 'Inter'          },
  { id: 'swiss',    label: 'S', bg: '#fff',      fg: '#ff0033', font: 'Inter'          },
]

function loadPrefs() {
  try {
    return JSON.parse(localStorage.getItem('cbosa-prefs') || '{}')
  } catch { return {} }
}

function savePrefs(prefs) {
  localStorage.setItem('cbosa-prefs', JSON.stringify(prefs))
}

export default function App() {
  const prefs = loadPrefs()
  const [theme,    setThemeRaw] = useState(prefs.theme    ?? 'phosphor')
  const [crtGlow,  setCrtGlow]  = useState(prefs.crtGlow  ?? true)
  const [scanlines,setScanlines] = useState(prefs.scanlines ?? true)
  const [density,  setDensity]  = useState(prefs.density  ?? 'default')
  const [toast,    setToast]    = useState(null)  // { text, id }
  const toastTimer = useRef(null)

  const [activeNote, setActiveNote] = useState(null)
  const [pomoState, setPomoState] = useState({ mode: 'work', secondsLeft: 25 * 60, isRunning: false, sessions: 0 })

  const isCaptureMode = new URLSearchParams(window.location.search).get('mode') === 'capture'

  const setTheme = useCallback((id) => {
    setThemeRaw(id)
    savePrefs({ ...loadPrefs(), theme: id })
  }, [])

  const showToast = useCallback((text) => {
    clearTimeout(toastTimer.current)
    setToast({ text, id: Date.now() })
    toastTimer.current = setTimeout(() => setToast(null), 1500)
  }, [])

  // Sync body classes + font to theme/effects
  useEffect(() => {
    const t = THEMES.find(t => t.id === theme)
    const classes = [`theme-${theme}`]
    if (crtGlow)               classes.push('crt-glow')
    if (scanlines)             classes.push('scanlines')
    if (density !== 'default') classes.push(`density-${density}`)
    document.body.className = classes.join(' ')
    if (t) document.body.style.fontFamily = `"${t.font}", ui-monospace, monospace`
    savePrefs({ ...loadPrefs(), crtGlow, scanlines, density })
  }, [theme, crtGlow, scanlines, density])

  // Global theme keybinds — Ctrl/Cmd + 1-7, only when not typing
  useEffect(() => {
    const handler = (e) => {
      if (!e.ctrlKey && !e.metaKey) return
      const tag = document.activeElement?.tagName
      if (tag === 'TEXTAREA' || tag === 'INPUT') return
      const idx = parseInt(e.key, 10) - 1
      if (idx >= 0 && idx < THEMES.length) {
        e.preventDefault()
        const t = THEMES[idx]
        setTheme(t.id)
        showToast(`theme: ${t.id}  (${t.font})`)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [setTheme, showToast])

  // Open today's daily note on launch
  useEffect(() => {
    if (isCaptureMode) return
    getDaily()
      .then(note => setActiveNote({ ...note, isDaily: true }))
      .catch(() => {})
  }, [])

  const handleOpenNote = useCallback((note) => {
    setActiveNote({ ...note, isDaily: false })
  }, [])

  const handleNewNote = useCallback(() => {
    const name = prompt('Note name:')
    if (!name?.trim()) return
    setActiveNote({ name: name.trim(), content: '', frontmatter: {}, isDaily: false, isNew: true })
  }, [])

  if (isCaptureMode) {
    return <CaptureOverlay />
  }

  return (
    <div id="app">
      {/* Toast notification */}
      {toast && (
        <div key={toast.id} style={{
          position: 'fixed', bottom: 36, left: '50%', transform: 'translateX(-50%)',
          zIndex: 9999, background: 'var(--bg-2)', border: '1px solid var(--accent)',
          color: 'var(--accent)', padding: '4px 16px', fontSize: 11,
          letterSpacing: '0.08em', pointerEvents: 'none',
          animation: 'fadeToast 1.5s ease forwards',
        }}>
          {toast.text}
        </div>
      )}

      {/* Window chrome — draggable titlebar */}
      <div className="winchrome">
        <span className="wintitle">
          <b>CBOSA</b>
          {activeNote && <> <span style={{ color: 'var(--fg-mute)' }}>·</span> {activeNote.name}</>}
        </span>
        <div className="right">
          <span className="mute" style={{ fontSize: 10, letterSpacing: '0.05em' }}>
            ⌃1-7 theme
          </span>
          <ThemePicker theme={theme} onTheme={(id) => { setTheme(id); showToast(`theme: ${id}`) }} />
          <span
            title="Toggle CRT glow (⌃G)"
            onClick={() => setCrtGlow(v => !v)}
            style={{ cursor: 'default', fontSize: 11, color: crtGlow ? 'var(--accent)' : 'var(--fg-mute)' }}
          >◉</span>
          <span
            title="Toggle scanlines (⌃L)"
            onClick={() => setScanlines(v => !v)}
            style={{ cursor: 'default', fontSize: 11, color: scanlines ? 'var(--accent)' : 'var(--fg-mute)' }}
          >≡</span>
        </div>
      </div>

      {/* Menu bar */}
      <div className="menubar">
        <span className="menu">File</span>
        <span className="menu" onClick={handleNewNote}>New Note</span>
        <span className="menu">View</span>
        <div className="right">
          <span>
            <b>{pomoState.mode === 'work' ? '🍅' : '☕'}</b>{' '}
            {String(Math.floor(pomoState.secondsLeft / 60)).padStart(2, '0')}:
            {String(pomoState.secondsLeft % 60).padStart(2, '0')}
          </span>
        </div>
      </div>

      {/* Three-column workspace */}
      <div className="workspace">
        <NoteBrowser
          activeNote={activeNote}
          onOpenNote={handleOpenNote}
          onNewNote={handleNewNote}
        />
        <NoteEditor
          note={activeNote}
          onNoteChange={setActiveNote}
        />
        <div className="panel stack">
          <PomodoroPanel
            pomoState={pomoState}
            onPomoStateChange={setPomoState}
          />
          <ChatPanel activeNote={activeNote} />
        </div>
      </div>

      <StatusBar activeNote={activeNote} pomoState={pomoState} theme={theme} />
    </div>
  )
}

function ThemePicker({ theme, onTheme }) {
  return (
    <div style={{ display: 'flex', gap: 3 }}>
      {THEMES.map((t, i) => (
        <div
          key={t.id}
          className={`theme-swatch${theme === t.id ? ' active' : ''}`}
          style={{ background: t.bg, color: t.fg, borderColor: theme === t.id ? t.fg : undefined }}
          title={`${t.id}  —  ${t.font}  (⌃${i + 1})`}
          onClick={() => onTheme(t.id)}
        >
          {t.label}
        </div>
      ))}
    </div>
  )
}
