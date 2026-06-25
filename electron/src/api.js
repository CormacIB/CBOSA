const PORT = 8765
const BASE = `http://127.0.0.1:${PORT}`

async function req(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status}`)
  return res.json()
}

// ── Notes ────────────────────────────────────────────────────────────────────

export const listNotes = () => req('GET', '/api/notes')
export const getNote = (name) => req('GET', `/api/notes/${encodeURIComponent(name)}`)
export const createNote = (name, content = '', frontmatter = {}) =>
  req('POST', '/api/notes', { name, content, frontmatter })
export const updateNote = (name, content, frontmatter) =>
  req('PUT', `/api/notes/${encodeURIComponent(name)}`, { content, frontmatter })
export const deleteNote = (name) => req('DELETE', `/api/notes/${encodeURIComponent(name)}`)
export const getBacklinks = (name) => req('GET', `/api/notes/${encodeURIComponent(name)}/backlinks`)

// ── Search ───────────────────────────────────────────────────────────────────

export const search = (q) => req('GET', `/api/search?q=${encodeURIComponent(q)}`)

// ── Tags ─────────────────────────────────────────────────────────────────────

export const listTags = () => req('GET', '/api/tags')

// ── Daily note ───────────────────────────────────────────────────────────────

export const getDaily = () => req('GET', '/api/daily')
export const updateDaily = (name, content, frontmatter) =>
  req('PUT', `/api/daily/${encodeURIComponent(name)}`, { content, frontmatter })

// ── Capture ──────────────────────────────────────────────────────────────────

export const capture = (content) => req('POST', '/api/capture', { content })

// ── AI chat ──────────────────────────────────────────────────────────────────

export const chat = (messages, contextNotes = []) =>
  req('POST', '/api/chat', { messages, context_notes: contextNotes })

export const aiInfo = () => req('GET', '/api/ai/info')

// ── Timer ─────────────────────────────────────────────────────────────────────

export const listGroups = () => req('GET', '/api/timer/groups')
export const addGroup = (name) => req('POST', '/api/timer/groups', { name })
export const listCategories = (groupId) => req('GET', `/api/timer/groups/${groupId}/categories`)
export const addCategory = (groupId, name) =>
  req('POST', `/api/timer/groups/${groupId}/categories`, { name })
export const logSession = (categoryId, startTime, endTime) =>
  req('POST', '/api/timer/sessions', { category_id: categoryId, start_time: startTime, end_time: endTime })
export const listSessions = () => req('GET', '/api/timer/sessions')

// ── Config ───────────────────────────────────────────────────────────────────

export const getConfig = () => req('GET', '/api/config')
