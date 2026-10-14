import { useState } from 'react'
import { Link } from 'react-router-dom'

export default function ResetPassword() {
  // Read the token once, then take it out of the address bar so it isn't left in history or screenshots.
  const [token] = useState(() => {
    const t = new URLSearchParams(window.location.search).get('token') ?? ''
    if (t) window.history.replaceState(null, '', window.location.pathname)
    return t
  })
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (password !== confirm) return setError("The two passwords don't match.")
    setBusy(true)
    setError('')
    try {
      const r = await fetch('/api/auth/reset', {
        method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ token, password }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(body.detail ?? `Request failed (${r.status})`)
      setDone(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <main>
        <header><h1>Password changed</h1></header>
        <p className="status">You've been signed out everywhere. <Link to="/account">Log in with your new password →</Link></p>
      </main>
    )
  }
  if (!token) {
    return (
      <main>
        <header><h1>Reset your password</h1></header>
        <p className="status">This page needs the link from your reset email. <Link to="/account">Request a new one →</Link></p>
      </main>
    )
  }
  return (
    <main>
      <header><h1>Choose a new password</h1></header>
      <form className="auth-form" onSubmit={submit}>
        <label>New password
          <input type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <label>Confirm new password
          <input type="password" required minLength={8} maxLength={128} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </label>
        <p className="muted">At least 8 characters.</p>
        {error && <p className="notice" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>Change password</button>
      </form>
    </main>
  )
}
