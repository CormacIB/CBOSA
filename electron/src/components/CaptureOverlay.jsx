import { useState, useRef, useEffect } from 'react'
import { capture } from '../api.js'

export default function CaptureOverlay() {
  const [text, setText] = useState('')
  const [saved, setSaved] = useState(false)
  const taRef = useRef(null)

  useEffect(() => {
    taRef.current?.focus()
  }, [])

  const handleSave = async () => {
    if (!text.trim()) return close()
    try {
      await capture(text.trim())
      setSaved(true)
      setTimeout(close, 400)
    } catch (e) {
      console.error('Capture failed', e)
    }
  }

  const close = () => {
    if (window.electron?.closeCapture) {
      window.electron.closeCapture()
    } else {
      window.close()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') { close(); return }
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { handleSave(); return }
  }

  return (
    <div className="capture-overlay">
      <div className="capture-header">
        quick capture <span className="mute">· ⌘↵ save · esc cancel</span>
      </div>
      <textarea
        ref={taRef}
        className="capture-textarea"
        placeholder="capture a thought..."
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={handleKeyDown}
      />
      <div className="capture-footer">
        <span className="mute">{saved ? '✓ saved' : ''}</span>
        <button className="capture-save" onClick={handleSave}>save ↵</button>
      </div>
    </div>
  )
}
