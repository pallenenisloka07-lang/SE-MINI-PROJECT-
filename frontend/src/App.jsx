
import { useEffect, useState } from 'react'
import './App.css'

const API_URL = 'http://127.0.0.1:8000'

async function apiRequest(path, options = {}) {
  const token = sessionStorage.getItem('access_token')

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })

  if (response.status === 204) return null

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    if (response.status === 401) {
      sessionStorage.removeItem('access_token')
      sessionStorage.removeItem('user_role')
      throw new Error('Your session expired. Please log in again.')
    }
    throw new Error(data.detail || 'Something went wrong. Please try again.')
  }

  return data
}

function App() {
  const [page, setPage] = useState('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loggedIn, setLoggedIn] = useState(
    () => Boolean(sessionStorage.getItem('access_token'))
  )

  const [documents, setDocuments] = useState([])
  const [documentsLoading, setDocumentsLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [dashboardMessage, setDashboardMessage] = useState('')
  const [dashboardError, setDashboardError] = useState(false)
  const [saving, setSaving] = useState(false)

  function changePage(nextPage) {
    setPage(nextPage)
    setUsername('')
    setEmail('')
    setPassword('')
    setMessage('')
    setError(false)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setMessage('')
    setError(false)

    if (page === 'register') {
      if (password.length < 8 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) {
        setError(true)
        setMessage('Use at least 8 characters, including a letter and a number.')
        return
      }
    }

    setLoading(true)

    try {
      const endpoint = page === 'register'
        ? '/api/auth/register'
        : '/api/auth/login'

      const body = page === 'register'
        ? { username, email, password }
        : { username, password }

      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Please check your details and try again.'
        )
      }

      if (page === 'register') {
        setPage('login')
        setPassword('')
        setError(false)
        setMessage('Account created successfully! You can now log in.')
      } else {
        sessionStorage.setItem('access_token', data.access_token)
        sessionStorage.setItem('user_role', data.role)
        setLoggedIn(true)
        setDashboardMessage(`Welcome, ${username}!`)
        setDashboardError(false)
      }
    } catch (err) {
      setError(true)
      setMessage(
        err instanceof TypeError
          ? 'Cannot connect to the server. Check that the backend is running.'
          : err.message
      )
    } finally {
      setLoading(false)
    }
  }

  async function loadDocuments(keyword = '') {
    setDocumentsLoading(true)
    setDashboardMessage('')
    setDashboardError(false)

    try {
      const query = keyword.trim()
        ? `?search=${encodeURIComponent(keyword.trim())}`
        : ''
      const data = await apiRequest(`/api/documents${query}`)
      setDocuments(data)
    } catch (err) {
      setDashboardError(true)
      setDashboardMessage(err.message)
      if (err.message.includes('session expired')) {
        logout()
      }
    } finally {
      setDocumentsLoading(false)
    }
  }

  useEffect(() => {
    if (loggedIn) loadDocuments()
  }, [loggedIn])

  function openNewDocument() {
    setEditingId(null)
    setTitle('')
    setContent('')
    setEditorOpen(true)
    setDashboardMessage('')
    setDashboardError(false)
  }

  function openEditDocument(document) {
    setEditingId(document.id)
    setTitle(document.title)
    setContent(document.content)
    setEditorOpen(true)
    setDashboardMessage('')
    setDashboardError(false)
  }

  async function saveDocument(event) {
    event.preventDefault()
    setSaving(true)
    setDashboardMessage('')
    setDashboardError(false)

    try {
      const isEditing = editingId !== null
      const path = isEditing
        ? `/api/documents/${editingId}`
        : '/api/documents'

      await apiRequest(path, {
        method: isEditing ? 'PUT' : 'POST',
        body: JSON.stringify({ title, content }),
      })

      setEditorOpen(false)
      setDashboardMessage(isEditing ? 'Document updated successfully.' : 'Document created successfully.')
      await loadDocuments(search)
    } catch (err) {
      setDashboardError(true)
      setDashboardMessage(err.message)
      if (err.message.includes('session expired')) logout()
    } finally {
      setSaving(false)
    }
  }

  async function deleteDocument(document) {
    const confirmed = window.confirm(
      `Delete "${document.title}"? This action cannot be undone.`
    )
    if (!confirmed) return

    setDashboardMessage('')
    setDashboardError(false)

    try {
      await apiRequest(`/api/documents/${document.id}`, {
        method: 'DELETE',
      })
      setDashboardMessage('Document deleted.')
      await loadDocuments(search)
    } catch (err) {
      setDashboardError(true)
      setDashboardMessage(err.message)
      if (err.message.includes('session expired')) logout()
    }
  }

  function logout() {
    sessionStorage.removeItem('access_token')
    sessionStorage.removeItem('user_role')
    setLoggedIn(false)
    setDocuments([])
    setEditorOpen(false)
    setSearch('')
    changePage('login')
  }

  if (loggedIn) {
    return (
      <main className="dashboard-page">
        <aside className="dashboard-sidebar">
          <div className="dashboard-brand">
            <div className="brand-icon">A</div>
            <div>
              <strong>AI-CMS</strong>
              <span>Content workspace</span>
            </div>
          </div>

          <p className="sidebar-label">WORKSPACE</p>
          <button className="sidebar-link active" onClick={() => {
            setEditorOpen(false)
            loadDocuments()
          }}>
            <span>▦</span> Dashboard
          </button>
          <button className="sidebar-link" onClick={openNewDocument}>
            <span>＋</span> New document
          </button>

          <div className="sidebar-bottom">
            <div className="profile-row">
              <div className="profile-avatar">
                {(sessionStorage.getItem('user_role') || 'U').charAt(0)}
              </div>
              <div className="profile-info">
                <strong>{sessionStorage.getItem('user_role') || 'User'}</strong>
                <span>Signed in</span>
              </div>
            </div>
            <button className="sidebar-link logout-link" onClick={logout}>
              ↪ Log out
            </button>
          </div>
        </aside>

        <section className="dashboard-main">
          <header className="dashboard-header">
            <div>
              <p className="eyebrow dashboard-eyebrow">YOUR WORKSPACE</p>
              <h1>{editorOpen ? (editingId ? 'Edit document' : 'Create document') : 'Dashboard'}</h1>
              <p className="dashboard-subtitle">
                {editorOpen
                  ? 'Write and organize your content.'
                  : 'Manage your content, all in one place.'}
              </p>
            </div>
            {!editorOpen && (
              <button className="primary-button new-document-button" onClick={openNewDocument}>
                + New document
              </button>
            )}
          </header>

          {dashboardMessage && (
            <p className={`message ${dashboardError ? 'error' : 'success'}`} role="status">
              {dashboardMessage}
            </p>
          )}

          {editorOpen ? (
            <section className="content-panel">
              <form className="document-form" onSubmit={saveDocument}>
                <label htmlFor="document-title">Document title</label>
                <input
                  id="document-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Give your document a title"
                  maxLength={200}
                  required
                />

                <label htmlFor="document-content">Content</label>
                <textarea
                  id="document-content"
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                  placeholder="Start writing your content..."
                  maxLength={100000}
                  rows={12}
                  required
                />

                <div className="form-actions">
                  <button type="button" className="secondary-button" onClick={() => setEditorOpen(false)}>
                    Cancel
                  </button>
                  <button className="primary-button" type="submit" disabled={saving}>
                    {saving ? 'Saving...' : editingId ? 'Save changes' : 'Create document'}
                  </button>
                </div>
              </form>
            </section>
          ) : (
            <>
              <section className="stats-grid">
                <div className="stat-card">
                  <div className="stat-icon purple">▤</div>
                  <span>Total documents</span>
                  <strong>{documents.length}</strong>
                  <small>Documents in your workspace</small>
                </div>
                <div className="stat-card">
                  <div className="stat-icon green">✓</div>
                  <span>Workspace status</span>
                  <strong>Active</strong>
                  <small>Your account is connected</small>
                </div>
              </section>

              <section className="content-panel">
                <div className="panel-heading">
                  <div>
                    <h2>Your documents</h2>
                    <p>Search, edit, and organize your saved content.</p>
                  </div>
                  <span className="document-count">{documents.length} items</span>
                </div>

                <form className="search-row" onSubmit={(event) => {
                  event.preventDefault()
                  loadDocuments(search)
                }}>
                  <input
                    aria-label="Search documents by title"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search by document title..."
                  />
                  <button className="secondary-button" type="submit">Search</button>
                  {search && (
                    <button className="secondary-button" type="button" onClick={() => {
                      setSearch('')
                      loadDocuments('')
                    }}>Clear</button>
                  )}
                </form>

                {documentsLoading ? (
                  <p className="empty-state">Loading your documents...</p>
                ) : documents.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon">▤</div>
                    <h3>{search ? 'No matching documents' : 'Your workspace is ready'}</h3>
                    <p>{search ? 'Try another title or clear your search.' : 'Create your first document to get started.'}</p>
                    {!search && (
                      <button className="primary-button" onClick={openNewDocument}>
                        Create your first document
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="document-list">
                    {documents.map((document) => (
                      <article className="document-item" key={document.id}>
                        <div className="document-symbol">▤</div>
                        <div className="document-details">
                          <h3>{document.title}</h3>
                          <p>{document.content}</p>
                          <small>Document #{document.id}</small>
                        </div>
                        <div className="document-actions">
                          <button className="secondary-button" onClick={() => openEditDocument(document)}>
                            Edit
                          </button>
                          <button className="delete-button" onClick={() => deleteDocument(document)}>
                            Delete
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}

          <footer className="dashboard-footer">
            AI-CMS · Your content, intelligently managed
          </footer>
        </section>
      </main>
    )
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="brand-icon" aria-hidden="true">A</div>
        <p className="eyebrow">AI-POWERED CONTENT MANAGEMENT</p>
        <h1>{page === 'login' ? 'Welcome back' : 'Create your account'}</h1>
        <p className="subtitle">
          {page === 'login'
            ? 'Sign in to continue to your workspace.'
            : 'Join us and organize your content smarter.'}
        </p>

        <div className="tabs">
          <button type="button" className={page === 'login' ? 'tab active' : 'tab'} onClick={() => changePage('login')}>
            Login
          </button>
          <button type="button" className={page === 'register' ? 'tab active' : 'tab'} onClick={() => changePage('register')}>
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <label htmlFor="username">Username</label>
          <input
            id="username"
            type="text"
            placeholder="Enter your username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            maxLength={50}
            autoComplete="username"
            required
          />

          {page === 'register' && (
            <>
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                required
              />
            </>
          )}

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            placeholder="Enter your password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete={page === 'login' ? 'current-password' : 'new-password'}
            required
          />

          {page === 'register' && (
            <p className="hint">Use at least 8 characters, including a letter and a number.</p>
          )}

          {message && (
            <p className={`message ${error ? 'error' : 'success'}`} role="status">
              {message}
            </p>
          )}

          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? 'Please wait...' : page === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <p className="switch-text">
          {page === 'login' ? 'New to AI-CMS?' : 'Already have an account?'}{' '}
          <button
            type="button"
            className="text-button"
            onClick={() => changePage(page === 'login' ? 'register' : 'login')}
          >
            {page === 'login' ? 'Create an account' : 'Sign in'}
          </button>
        </p>

        <p className="footer-note">AI-CMS · Your content, intelligently managed</p>
      </section>
    </main>
  )
}

export default App
