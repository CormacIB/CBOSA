export default function StatusBar({ activeNote, pomoState, theme }) {
  const { mode, secondsLeft, isRunning, sessions } = pomoState
  const mins = String(Math.floor(secondsLeft / 60)).padStart(2, '0')
  const secs = String(secondsLeft % 60).padStart(2, '0')

  return (
    <div className="statusbar">
      <span>
        {isRunning
          ? <span className="acc">{mode === 'work' ? '▸' : '☕'} {mins}:{secs}</span>
          : <span className="mute">{mode === 'work' ? '○ focus' : '○ break'} {mins}:{secs}</span>
        }
      </span>
      {sessions > 0 && <span className="mute">🍅 ×{sessions}</span>}
      <span className="sep">·</span>
      {activeNote
        ? <span><b>{activeNote.name}</b></span>
        : <span className="mute">no note open</span>
      }
      <div className="right">
        <span className="mute">theme: <b className="acc">{theme}</b></span>
        <span className="mute">cbosa v0.1</span>
      </div>
    </div>
  )
}
