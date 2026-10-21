
import { useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000'

function App() {
  const [page, setPage] = useState('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loggedIn, setLoggedIn] = useState(false)

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

    if (page === 'register' && password.length < 8) {
      setError(true)
      setMessage('Password must be at least 8 characters and contain a letter and a number.')
      return
    }

    if (page === 'register' && !/[A-Za-z]/.test(password)) {
      setError(true)
      setMessage('Password must contain at least one letter.')
      return
    }

    if (page === 'register' && !/\d/.test(password)) {
      setError(true)
      setMessage('Password must contain at least one number.')
      return
    }

    setLoading(true)

    try {
      const endpoint = page === 'register' ? '/api/auth/register' : '/api/auth/login'

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
        setMessage('Account created successfully! You can now log in.')
        setError(false)
        setPage('login')
        setPassword('')
      } else {
        sessionStorage.setItem('access_token', data.access_token)
        sessionStorage.setItem('user_role', data.role)
        setLoggedIn(true)
        setMessage(`Welcome, ${username}! You are logged in.`)
      }
    } catch (err) {
      setError(true)
      setMessage(
        err instanceof TypeError
          ? 'Cannot connect to the server. Make sure the backend is running on port 8000.'
          : err.message
      )
    } finally {
      setLoading(false)
    }
  }

  function logout() {
    sessionStorage.removeItem('access_token')
    sessionStorage.removeItem('user_role')
    setLoggedIn(false)
    changePage('login')
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="brand-icon" aria-hidden="true">A</div>
        <p className="eyebrow">AI-POWERED CONTENT MANAGEMENT</p>
        <h1>{loggedIn ? 'You’re signed in' : page === 'login' ? 'Welcome back' : 'Create your account'}</h1>
        <p className="subtitle">
          {loggedIn
            ? 'Your AI-CMS session is ready.'
            : page === 'login'
              ? 'Sign in to continue to your workspace.'
              : 'Join us and organize your content smarter.'}
        </p>

        {loggedIn ? (
          <div className="logged-in">
            <p className="message success">{message}</p>
            <button className="primary-button" onClick={logout}>
              Log out
            </button>
          </div>
        ) : (
          <>
            <div className="tabs">
              <button
                type="button"
                className={page === 'login' ? 'tab active' : 'tab'}
                onClick={() => changePage('login')}
              >
                Login
              </button>
              <button
                type="button"
                className={page === 'register' ? 'tab active' : 'tab'}
                onClick={() => changePage('register')}
              >
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
                <p className="hint">
                  Use at least 8 characters, including a letter and a number.
                </p>
              )}

              {message && (
                <p className={error ? 'message error' : 'message success'} role="status">
                  {message}
                </p>
              )}

              <button className="primary-button" type="submit" disabled={loading}>
                {loading
                  ? 'Please wait...'
                  : page === 'login'
                    ? 'Sign in'
                    : 'Create account'}
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
          </>
        )}

        <p className="footer-note">AI-CMS · Your content, intelligently managed</p>
      </section>
    </main>
  )
}

export default App
