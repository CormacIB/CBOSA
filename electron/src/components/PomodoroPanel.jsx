import { useEffect, useRef, useCallback } from 'react'
import { listGroups, addGroup, listCategories, addCategory, logSession } from '../api.js'

const WORK_SECS = 25 * 60
const BREAK_SECS = 5 * 60

// Ensure a "Pomodoro" group + "Focus" category exists; returns category_id
async function ensureCategory() {
  let groups = (await listGroups()).groups
  let group = groups.find(g => g.name === 'Pomodoro')
  if (!group) {
    const { id } = await addGroup('Pomodoro')
    group = { id }
  }
  const { categories } = await listCategories(group.id)
  let cat = categories.find(c => c.name === 'Focus')
  if (!cat) {
    const { id } = await addCategory(group.id, 'Focus')
    cat = { id }
  }
  return cat.id
}

export default function PomodoroPanel({ pomoState, onPomoStateChange }) {
  const { mode, secondsLeft, isRunning, sessions } = pomoState
  const intervalRef = useRef(null)
  const sessionStartRef = useRef(null)
  const categoryIdRef = useRef(null)

  // Pre-fetch category id
  useEffect(() => {
    ensureCategory()
      .then(id => { categoryIdRef.current = id })
      .catch(console.error)
  }, [])

  const update = (patch) => onPomoStateChange(prev => ({ ...prev, ...patch }))

  const logCompletedSession = useCallback(async (startISO, endISO) => {
    if (!categoryIdRef.current) return
    try {
      await logSession(categoryIdRef.current, startISO, endISO)
    } catch (e) {
      console.error('Failed to log session', e)
    }
  }, [])

  const tick = useCallback(() => {
    onPomoStateChange(prev => {
      if (!prev.isRunning) return prev
      const next = prev.secondsLeft - 1
      if (next <= 0) {
        // Session complete — switch modes
        if (prev.mode === 'work') {
          const endISO = new Date().toISOString().slice(0, 19)
          if (sessionStartRef.current) {
            logCompletedSession(sessionStartRef.current, endISO)
            sessionStartRef.current = null
          }
          return { ...prev, mode: 'break', secondsLeft: BREAK_SECS, isRunning: false, sessions: prev.sessions + 1 }
        } else {
          return { ...prev, mode: 'work', secondsLeft: WORK_SECS, isRunning: false }
        }
      }
      return { ...prev, secondsLeft: next }
    })
  }, [logCompletedSession])

  useEffect(() => {
    if (isRunning) {
      intervalRef.current = setInterval(tick, 1000)
    } else {
      clearInterval(intervalRef.current)
    }
    return () => clearInterval(intervalRef.current)
  }, [isRunning, tick])

  const start = () => {
    if (mode === 'work' && !isRunning) {
      sessionStartRef.current = new Date().toISOString().slice(0, 19)
    }
    update({ isRunning: true })
  }

  const pause = () => update({ isRunning: false })

  const reset = () => {
    sessionStartRef.current = null
    update({ isRunning: false, secondsLeft: mode === 'work' ? WORK_SECS : BREAK_SECS })
  }

  const skipToBreak = () => {
    sessionStartRef.current = null
    update({ isRunning: false, mode: 'break', secondsLeft: BREAK_SECS })
  }

  const skipToWork = () => {
    update({ isRunning: false, mode: 'work', secondsLeft: WORK_SECS })
  }

  const total = mode === 'work' ? WORK_SECS : BREAK_SECS
  const progress = ((total - secondsLeft) / total) * 100
  const mins = String(Math.floor(secondsLeft / 60)).padStart(2, '0')
  const secs = String(secondsLeft % 60).padStart(2, '0')

  return (
    <div className="panel" style={{ flex: '0 0 auto' }}>
      <div className="panel-head">
        <span className="glyph">◎</span>
        <span className="tab active">Timer</span>
        <div className="ctrl">
          <span
            title={mode === 'work' ? 'Skip to break' : 'Skip to work'}
            onClick={mode === 'work' ? skipToBreak : skipToWork}
          >↷</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="pomo-progress">
        <div className="pomo-progress-fill" style={{ width: `${progress}%` }} />
      </div>

      {/* Timer display */}
      <div className="pomo-display">
        <div className="pomo-time">{mins}:{secs}</div>
        <div className="pomo-mode">{mode === 'work' ? '▸ focus' : '☕ break'}</div>
      </div>

      {/* Controls */}
      <div className="pomo-controls">
        {isRunning
          ? <button className="pomo-btn active" onClick={pause}>pause</button>
          : <button className="pomo-btn" onClick={start}>start</button>
        }
        <button className="pomo-btn" onClick={reset}>reset</button>
      </div>

      {sessions > 0 && (
        <div className="pomo-sessions">
          {'🍅'.repeat(Math.min(sessions, 8))} {sessions} {sessions === 1 ? 'session' : 'sessions'}
        </div>
      )}
    </div>
  )
}
