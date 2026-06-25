import { useState, useRef, useEffect } from 'react'
import { chat, aiInfo } from '../api.js'

export default function ChatPanel({ activeNote }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [useNoteCtx, setUseNoteCtx] = useState(false)
  const [model, setModel] = useState('')
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    aiInfo()
      .then(info => setModel(info.model || ''))
      .catch(() => setModel(''))
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || loading) return

    const userMsg = { role: 'user', content: text }
    const history = [...messages, userMsg]
    setMessages(history)
    setInput('')
    setLoading(true)

    const contextNotes = useNoteCtx && activeNote ? [activeNote.name] : []

    try {
      const data = await chat(
        history.map(m => ({ role: m.role, content: m.content })),
        contextNotes
      )
      setMessages(prev => [...prev, { role: 'assistant', content: data.response || '(no response)' }])
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${e.message}` }])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="panel" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      <div className="panel-head">
        <span className="glyph">◆</span>
        <span className="tab active">AI</span>
        {model && <span className="mute" style={{ marginLeft: 'auto', fontSize: 10 }}>{model}</span>}
        <div className="ctrl" style={{ marginLeft: model ? 0 : 'auto' }}>
          <span
            title={useNoteCtx ? 'Note context: ON' : 'Note context: OFF'}
            style={{ color: useNoteCtx ? 'var(--accent)' : 'var(--fg-mute)', cursor: 'default' }}
            onClick={() => setUseNoteCtx(v => !v)}
          >
            {useNoteCtx ? '◈' : '◇'}
          </span>
          <span
            title="Clear chat"
            onClick={() => setMessages([])}
            style={{ cursor: 'default' }}
          >
            ✕
          </span>
        </div>
      </div>

      {/* Message list */}
      <div className="chat-messages">
        {messages.length === 0 && !loading && (
          <div className="mute" style={{ fontSize: 11, padding: '8px 0' }}>
            {model
              ? `model: ${model} · ${useNoteCtx ? 'note ctx on' : 'no context'}`
              : 'AI not configured — set backend=ollama in cbosa.toml'}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role}`}>
            <div className="role">{m.role === 'user' ? '▸ you' : '◆ ai'}</div>
            <div className="body">{m.content}</div>
          </div>
        ))}
        {loading && (
          <div className="chat-msg assistant">
            <div className="role">◆ ai</div>
            <div className="chat-thinking">thinking<span className="blink">▌</span></div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="chat-input-row">
        <input
          ref={inputRef}
          className="input"
          placeholder="ask anything..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button className="chat-send" onClick={sendMessage} disabled={loading || !input.trim()}>
          ↵
        </button>
      </div>
    </div>
  )
}
