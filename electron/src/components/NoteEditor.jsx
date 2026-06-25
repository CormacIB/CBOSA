import { useState, useEffect, useRef, useCallback } from 'react'
import { createNote, updateNote, updateDaily, getBacklinks, getNote } from '../api.js'

const SAVE_DELAY_MS = 1200

export default function NoteEditor({ note, onNoteChange }) {
  const [content, setContent] = useState('')
  const [wordCount, setWordCount] = useState(0)
  const [backlinks, setBacklinks] = useState([])
  const [saveState, setSaveState] = useState('saved')  // 'saved' | 'saving' | 'unsaved'
  const saveTimerRef = useRef(null)
  const isFirstLoad = useRef(true)

  // Load content when note changes
  useEffect(() => {
    if (!note) { setContent(''); setBacklinks([]); return }
    setContent(note.content ?? '')
    setWordCount(countWords(note.content ?? ''))
    setSaveState('saved')
    isFirstLoad.current = true

    if (!note.isNew && !note.isDaily) {
      getBacklinks(note.name)
        .then(d => setBacklinks(d.backlinks ?? []))
        .catch(() => setBacklinks([]))
    } else {
      setBacklinks([])
    }
  }, [note?.name])

  const scheduleSave = useCallback((newContent) => {
    if (isFirstLoad.current) { isFirstLoad.current = false; return }
    setSaveState('unsaved')
    clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      doSave(newContent)
    }, SAVE_DELAY_MS)
  }, [note])

  const doSave = useCallback(async (text) => {
    if (!note) return
    setSaveState('saving')
    try {
      if (note.isNew) {
        await createNote(note.name, text, note.frontmatter ?? {})
        onNoteChange({ ...note, content: text, isNew: false })
      } else if (note.isDaily) {
        await updateDaily(note.name, text, note.frontmatter)
        onNoteChange({ ...note, content: text })
      } else {
        await updateNote(note.name, text, note.frontmatter)
        onNoteChange({ ...note, content: text })
      }
      setSaveState('saved')
    } catch (e) {
      console.error('Save failed', e)
      setSaveState('unsaved')
    }
  }, [note, onNoteChange])

  const handleChange = (e) => {
    const val = e.target.value
    setContent(val)
    setWordCount(countWords(val))
    scheduleSave(val)
  }

  // Ctrl/Cmd+S to force immediate save
  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault()
      clearTimeout(saveTimerRef.current)
      doSave(content)
    }
    // Tab → insert 2 spaces
    if (e.key === 'Tab') {
      e.preventDefault()
      const ta = e.target
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const newVal = content.slice(0, start) + '  ' + content.slice(end)
      setContent(newVal)
      scheduleSave(newVal)
      requestAnimationFrame(() => {
        ta.selectionStart = ta.selectionEnd = start + 2
      })
    }
  }

  if (!note) {
    return (
      <div className="panel grow" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span className="mute" style={{ fontSize: 12 }}>select a note to edit</span>
      </div>
    )
  }

  const saveDot = saveState === 'saved' ? '' : saveState === 'saving' ? ' ·' : ' ●'

  return (
    <div className="panel grow" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* Breadcrumb / editor toolbar */}
      <div className="editor-bar">
        <div className="crumb">
          {note.isDaily
            ? <><span className="mute">daily</span><span className="sep">/</span><b>{note.name}</b></>
            : note.name.includes('/')
              ? <>
                  <span className="mute">{note.name.split('/').slice(0, -1).join('/')}</span>
                  <span className="sep">/</span>
                  <b>{note.name.split('/').pop()}</b>
                </>
              : <b>{note.name}</b>
          }
        </div>
        <div className="right">
          <span className="mute">{wordCount} words</span>
          <span className={saveState === 'unsaved' ? 'acc' : 'mute'}>
            {saveState === 'saved' ? '✓ saved' : saveState === 'saving' ? '··· saving' : '● unsaved'}
          </span>
        </div>
      </div>

      {/* Textarea */}
      <textarea
        className="note-textarea"
        value={content}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={`# ${note.name}\n\nStart writing...`}
        spellCheck={false}
        autoFocus
      />

      {/* Backlinks footer */}
      {backlinks.length > 0 && (
        <div style={{ borderTop: '1px dashed var(--rule)', padding: '8px 16px', fontSize: 11 }}>
          <span className="mute" style={{ textTransform: 'uppercase', letterSpacing: '0.08em' }}>backlinks · </span>
          {backlinks.map((bl, i) => (
            <span key={bl}>
              <span className="wikilink" onClick={() => getNote(bl).then(n => onNoteChange({ ...n, isDaily: false })).catch(console.error)}>
                {bl}
              </span>
              {i < backlinks.length - 1 && <span className="mute"> · </span>}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function countWords(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0
}
