import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { createLeague, joinLeague, setActive, useLeagues } from '../leagues.js'
import { useLeague, useScoring } from '../fantasy.js'
import { cleanLeague } from '../value.js'

/** Your leagues, with forms to start one or join one by invite code. */
export default function Leagues() {
  const { signedIn, status, leagues, activeId, error } = useLeagues()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { scoring } = useScoring()
  const { league } = useLeague()
  const [name, setName] = useState('')
  const [team, setTeam] = useState('')
  const [size, setSize] = useState(12)
  const [share, setShare] = useState(true)
  const [code, setCode] = useState(params.get('join') ?? '')
  const [joinTeam, setJoinTeam] = useState('')
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  const run = async (fn) => {
    setBusy(true)
    setMessage(null)
    try {
      const detail = await fn()
      navigate(`/league/${detail.id}`)
    } catch (e) {
      setMessage(e.message)
    } finally {
      setBusy(false)
    }
  }

  const create = (e) => {
    e.preventDefault()
    const cfg = cleanLeague(league)
    const settings = share ? { format: cfg.format, slots: cfg.slots, scoring, categories: cfg.categories } : {}
    return run(() => createLeague({ name, team_name: team, teams: Number(size) || 12, settings }))
  }
  const join = (e) => {
    e.preventDefault()
    return run(() => joinLeague(code, joinTeam))
  }

  if (!signedIn) {
    return (
      <main>
        <header><h1>Leagues</h1><p>Share rosters with the friends in your fantasy league so the site knows who is actually available.</p></header>
        <p className="status"><Link to="/account">Log in</Link> to start or join a league{params.get('join') ? ' (keep this page open, or come back to the same invite link)' : ''}.</p>
      </main>
    )
  }

  return (
    <main>
      <header>
        <h1>Leagues</h1>
        <p>
          A league shares each member's fantasy roster with the others in it. With one set as your active league, the waiver wire shows
          who is really available and the matchup projector can load a league-mate's team. Only league members can see rosters, and only
          team names are shown, never emails. Your roster is the one on the Fantasy page, kept current while you are signed in.
        </p>
      </header>
      {error && <p className="notice" role="alert">{error}</p>}
      {message && <p className="notice" role="alert">{message}</p>}
      {status === 'loading' && <p className="status">Loading…</p>}

      {leagues.length > 0 && (
        <section>
          <h2>Your leagues</h2>
          <ul className="plain-list">
            {leagues.map((l) => (
              <li key={l.id}>
                <Link to={`/league/${l.id}`}>{l.name}</Link>{' '}
                <span className="muted">{l.team_count} of {l.teams_allowed} teams · you are {l.my_team}{l.is_owner ? ' · owner' : ''}</span>{' '}
                {l.id === activeId
                  ? <span className="badge">active on the Fantasy page</span>
                  : <button className="link-button" onClick={() => setActive(l.id)}>Use on the Fantasy page</button>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2>Join a league</h2>
        <form onSubmit={join} className="h2h-picks">
          <label className="h2h-pick">Invite code
            <input type="text" value={code} onChange={(e) => setCode(e.target.value)} maxLength={12} required />
          </label>
          <label className="h2h-pick">Your team name
            <input type="text" value={joinTeam} onChange={(e) => setJoinTeam(e.target.value)} maxLength={60} placeholder="My team" />
          </label>
          <button type="submit" disabled={busy || !code.trim()}>Join</button>
        </form>
      </section>

      <section>
        <h2>Start a league</h2>
        <form onSubmit={create} className="h2h-picks">
          <label className="h2h-pick">League name
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} required />
          </label>
          <label className="h2h-pick">Your team name
            <input type="text" value={team} onChange={(e) => setTeam(e.target.value)} maxLength={60} placeholder="My team" />
          </label>
          <label className="h2h-pick">Teams
            <input type="number" min="2" max="32" value={size} onChange={(e) => setSize(e.target.value)} style={{ minWidth: 80, width: 80 }} />
          </label>
          <label className="h2h-pick">
            <span><input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} /> Share my current scoring and slots with the league</span>
          </label>
          <button type="submit" disabled={busy || !name.trim()}>Create</button>
        </form>
        <p className="muted">You get an invite link to send to the others. You can add teams yourself for friends who don't use the site.</p>
      </section>
    </main>
  )
}
