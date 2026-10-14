import { useState } from 'react'
import { Link } from 'react-router-dom'
import DigestToggle from '../components/DigestToggle.jsx'
import { resolveConflict, signIn, signOut, useAuth } from '../auth.js'

const names = (players) => players.map((p) => p.name).join(', ')

export default function Account() {
  const { ready, user, sync, server, error: syncError } = useAuth()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)

  const sendReset = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const r = await fetch('/api/auth/forgot', {
        method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email }),
      })
      if (!r.ok) throw new Error(`Request failed (${r.status})`)
      setSent(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await signIn(mode === 'login' ? 'login' : 'register', email, password)
      setPassword('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!ready) return <main><p className="status">Loading…</p></main>

  if (user) {
    return (
      <main>
        <header>
          <h1>Account</h1>
          <p>Signed in as <strong>{user.email}</strong>.</p>
        </header>
        {sync === 'conflict' && server && (
          <section className="notice">
            <p><strong>Your account already has a roster, and it differs from this browser's.</strong> Which one should win?</p>
            <p className="muted">Account: {server.players.length} players ({names(server.players)})</p>
            <p>
              <button onClick={() => resolveConflict('account')}>Use the account's roster</button>{' '}
              <button onClick={() => resolveConflict('browser')}>Use this browser's roster</button>
            </p>
          </section>
        )}
        {sync === 'synced' && <p className="status">Your fantasy roster and scoring are synced to this account. Changes save automatically and show up on your other devices.</p>}
        {sync === 'checking' && <p className="status">Syncing…</p>}
        {sync === 'error' && <p className="notice">Couldn't sync: {syncError}. Your data is still safe in this browser.</p>}
        <DigestToggle />
        <p><Link to="/fantasy">Go to your fantasy team →</Link></p>
        <p><button onClick={signOut}>Log out</button></p>
      </main>
    )
  }

  if (mode === 'forgot') {
    return (
      <main>
        <header>
          <h1>Reset your password</h1>
          <p>Enter your account email and we'll send you a link to choose a new password.</p>
        </header>
        {sent ? (
          <p className="status">If an account exists for that email, a reset link is on its way. It works once and expires in an hour.</p>
        ) : (
          <form className="auth-form" onSubmit={sendReset}>
            <label>Email
              <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
            {error && <p className="notice" role="alert">{error}</p>}
            <button type="submit" disabled={busy}>Send reset link</button>
          </form>
        )}
        <p><button type="button" className="link-button" onClick={() => { setMode('login'); setSent(false); setError('') }}>← Back to log in</button></p>
      </main>
    )
  }

  return (
    <main>
      <header>
        <h1>{mode === 'login' ? 'Log in' : 'Create an account'}</h1>
        <p>An account keeps your fantasy roster and league scoring synced across devices. Everything else on the site works without one.</p>
      </header>
      <form className="auth-form" onSubmit={submit}>
        <label>Email
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>Password
          <input type="password" required minLength={mode === 'login' ? undefined : 8} maxLength={128}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {mode === 'register' && <p className="muted">At least 8 characters.</p>}
        {error && <p className="notice" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>{mode === 'login' ? 'Log in' : 'Create account'}</button>
      </form>
      {mode === 'login' && (
        <p><button type="button" className="link-button" onClick={() => { setMode('forgot'); setError('') }}>Forgot your password?</button></p>
      )}
      <p>
        {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
        <button type="button" className="link-button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
          {mode === 'login' ? 'Create one' : 'Log in'}
        </button>
      </p>
    </main>
  )
}
