import { useState, useEffect, useRef } from 'react'
import { listNotes, getNote, search } from '../api.js'

// Build a nested tree from flat names like ["inbox/idea", "daily/2025-01-01"]
function buildTree(names) {
  const root = {}
  for (const name of names) {
    const parts = name.split('/')
    let node = root
    for (let i = 0; i < parts.length - 1; i++) {
      if (!node[parts[i]]) node[parts[i]] = { _isFolder: true, _children: {} }
      node = node[parts[i]]._children
    }
    const leaf = parts[parts.length - 1]
    node[leaf] = { _isLeaf: true, _name: name }
  }
  return root
}

function TreeNode({ label, entry, depth, activeNote, onOpen }) {
  const [open, setOpen] = useState(depth === 0)

  if (entry._isLeaf) {
    const isActive = activeNote?.name === entry._name
    return (
      <div
        className={`tree-row${isActive ? ' active' : ''}`}
        style={{ paddingLeft: depth * 14 + 4 }}
        onClick={() => {
          getNote(entry._name)
            .then(note => onOpen(note))
            .catch(console.error)
        }}
      >
        <span className="glyph">›</span>
        <span className="name">{label}</span>
      </div>
    )
  }

  if (entry._isFolder) {
    return (
      <>
        <div
          className="tree-row folder"
          style={{ paddingLeft: depth * 14 + 4 }}
          onClick={() => setOpen(v => !v)}
        >
          <span className="glyph">{open ? '▾' : '▸'}</span>
          <span className="name">{label}/</span>
        </div>
        {open && Object.entries(entry._children)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([key, child]) => (
            <TreeNode
              key={key}
              label={key}
              entry={child}
              depth={depth + 1}
              activeNote={activeNote}
              onOpen={onOpen}
            />
          ))
        }
      </>
    )
  }
  return null
}

export default function NoteBrowser({ activeNote, onOpenNote, onNewNote }) {
  const [notes, setNotes] = useState([])
  const [tree, setTree] = useState({})
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [showResults, setShowResults] = useState(false)
  const searchRef = useRef(null)
  const debounceRef = useRef(null)

  useEffect(() => {
    listNotes()
      .then(data => {
        setNotes(data.notes)
        setTree(buildTree(data.notes))
      })
      .catch(console.error)
  }, [activeNote])  // refresh when active note changes (new note created)

  const handleSearch = (q) => {
    setQuery(q)
    clearTimeout(debounceRef.current)
    if (!q.trim()) { setShowResults(false); return }
    debounceRef.current = setTimeout(() => {
      search(q)
        .then(data => { setResults(data.results); setShowResults(true) })
        .catch(() => setShowResults(false))
    }, 250)
  }

  const handleResultClick = (name) => {
    setQuery('')
    setShowResults(false)
    getNote(name).then(onOpenNote).catch(console.error)
  }

  return (
    <div className="panel" style={{ flex: '0 0 260px' }}>
      <div className="panel-head">
        <span className="glyph">◈</span>
        <span className="tab active">Notes</span>
        <div className="ctrl">
          <span title="New note" onClick={onNewNote}>+</span>
        </div>
      </div>

      {/* Search */}
      <div className="browser-search">
        <input
          ref={searchRef}
          className="input"
          placeholder="search..."
          value={query}
          onChange={e => handleSearch(e.target.value)}
          onBlur={() => setTimeout(() => setShowResults(false), 150)}
        />
        {showResults && results.length > 0 && (
          <div className="search-results">
            {results.map(r => (
              <div key={r.name} className="search-result" onMouseDown={() => handleResultClick(r.name)}>
                <div className="result-name">{r.name}</div>
                {r.snippet && <div className="result-snippet">{r.snippet}</div>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* File tree */}
      <div className="panel-body" style={{ padding: '4px 0' }}>
        <div className="tree">
          {Object.entries(tree)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([key, entry]) => (
              <TreeNode
                key={key}
                label={key}
                entry={entry}
                depth={0}
                activeNote={activeNote}
                onOpen={onOpenNote}
              />
            ))
          }
          {notes.length === 0 && (
            <div className="mute" style={{ padding: '8px', fontSize: 11 }}>
              No notes yet — press + to create one
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
