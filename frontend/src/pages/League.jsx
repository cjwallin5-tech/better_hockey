import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { call, refresh, setActive, useLeagues } from '../leagues.js'
import { useLeague, useScoring } from '../fantasy.js'
import { GROUPS, cleanLeague } from '../value.js'
import { matchNames } from '../h2h.js'

const linkFor = (p) => `/${p.kind === 'goalie' ? 'goalie' : 'player'}/${p.id}`

function Roster({ players }) {
  if (players.length === 0) return <p className="muted">No players yet.</p>
  const skaters = players.filter((p) => p.kind === 'skater')
  const goalies = players.filter((p) => p.kind === 'goalie')
  const list = (rows) => rows.map((p, i) => <span key={p.id}>{i > 0 && ', '}<Link to={linkFor(p)}>{p.name}</Link></span>)
  return (
    <>
      {skaters.length > 0 && <p style={{ margin: '4px 0' }}><span className="muted">Skaters ({skaters.length}): </span>{list(skaters)}</p>}
      {goalies.length > 0 && <p style={{ margin: '4px 0' }}><span className="muted">Goalies ({goalies.length}): </span>{list(goalies)}</p>}
    </>
  )
}

/** A form that turns pasted names into a roster for a hand-managed team. */
function PasteRoster({ pool, onSave, label, initial = [] }) {
  const [text, setText] = useState('')
  const [unmatched, setUnmatched] = useState([])
  const submit = () => {
    const { matched, unmatched: bad } = matchNames(text, pool)
    setUnmatched(bad)
    setText(bad.join('\n'))
    return onSave([...initial, ...matched.filter((m) => !initial.some((p) => p.id === m.id))])
  }
  return (
    <div>
      <textarea rows={5} style={{ width: '100%', maxWidth: 420 }} value={text} onChange={(e) => setText(e.target.value)} placeholder="One player name per line, or separated by commas" />
      <p><button onClick={submit} disabled={!text.trim() || !pool}>{label}</button></p>
      {unmatched.length > 0 && <p className="notice">Couldn't match: {unmatched.join(', ')}. Check the spelling (players with no games this season aren't listed).</p>}
    </div>
  )
}

/** One league: its teams and rosters, the invite link, and the owner's controls. */
export default function League() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { signedIn, activeId } = useLeagues()
  const { scoring, setScoring } = useScoring()
  const { league: mySettings, setLeague } = useLeague()
  const [state, setState] = useState({ id: null, data: null, error: null })
  const [message, setMessage] = useState(null)
  const [pool, setPool] = useState(null)
  const [newTeam, setNewTeam] = useState('')
  const [editing, setEditing] = useState(null)

  const load = useCallback(() => {
    call('GET', `/api/leagues/${id}`)
      .then((data) => setState({ id, data, error: null }))
      .catch((error) => setState({ id, data: null, error: error.message }))
  }, [id])
  useEffect(() => { if (signedIn) load() }, [signedIn, load])

  const { data, error } = state.id === id ? state : { data: null, error: null }
  const owner = data?.is_owner
  useEffect(() => {
    if (!owner) return
    Promise.all([fetch('/api/skaters').then((r) => r.json()), fetch('/api/goalies').then((r) => r.json())])
      .then(([skaters, goalies]) => setPool({ skaters, goalies: goalies.goalies }))
      .catch(() => setPool(null))
  }, [owner])

  const act = async (fn) => {
    setMessage(null)
    try {
      const out = await fn()
      if (out?.teams) setState({ id, data: out, error: null })
      if (Number(id) === activeId) refresh()
      return out
    } catch (e) {
      setMessage(e.message)
      return null
    }
  }

  const inviteLink = useMemo(() => (data?.invite_code ? `${window.location.origin}/leagues?join=${data.invite_code}` : ''), [data])
  const copy = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      setMessage('Copied.')
    } catch {
      setMessage(text)
    }
  }

  const back = <Link to="/leagues" className="back">← Leagues</Link>
  if (!signedIn) return <main>{back}<p className="status"><Link to="/account">Log in</Link> to see your leagues.</p></main>
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!data) return <main>{back}<p className="status">Loading…</p></main>

  const settings = data.settings ?? {}
  const myCfg = cleanLeague(mySettings)
  const hasSettings = Object.keys(settings).length > 0
  const applySettings = () => {
    if (settings.scoring) setScoring(settings.scoring)
    setLeague({ ...myCfg, teams: data.teams_allowed, ...(settings.format ? { format: settings.format } : {}),
      ...(settings.slots ? { slots: { ...myCfg.slots, ...settings.slots } } : {}), ...(settings.categories ? { categories: settings.categories } : {}) })
    setMessage('Your scoring and league settings now match this league.')
  }
  const shareMine = () => act(() => call('PUT', `/api/leagues/${id}`, { settings: { format: myCfg.format, slots: myCfg.slots, scoring, categories: myCfg.categories } }))
  const slotText = GROUPS.filter((g) => settings.slots?.[g] != null).map((g) => `${settings.slots[g]} ${g}`).join(', ')

  return (
    <main>
      {back}
      <header>
        <h1>{data.name}</h1>
        <p>
          {data.teams.length} of {data.teams_allowed} teams{data.owner_team ? `, run by ${data.owner_team}` : ''}.{' '}
          {Number(id) === activeId
            ? <span className="badge">active on the Fantasy page</span>
            : <button className="link-button" onClick={() => setActive(Number(id))}>Use on the Fantasy page</button>}
        </p>
      </header>
      {message && <p className="notice" role="status">{message}</p>}

      {owner && (
        <section>
          <h2>Invite</h2>
          <p>Send this link, or the code <strong>{data.invite_code}</strong>, to the people in your league.</p>
          <p>
            <input type="text" readOnly value={inviteLink} style={{ width: '100%', maxWidth: 460 }} onFocus={(e) => e.target.select()} />{' '}
            <button onClick={() => copy(inviteLink)}>Copy link</button>{' '}
            <button className="link-button" onClick={() => window.confirm('The old link and code stop working. Make a new one?') && act(() => call('POST', `/api/leagues/${id}/invite/reset`).then(load))}>New code</button>
          </p>
        </section>
      )}

      <section>
        <h2>League settings</h2>
        {hasSettings ? (
          <p>
            {settings.format === 'categories' ? 'Category league' : 'Points league'}{slotText ? ` · ${slotText}` : ''}
            {settings.scoring ? ` · ${Object.keys(settings.scoring).length} scored stats` : ''}.{' '}
            <button className="link-button" onClick={applySettings}>Use these on my Fantasy page</button>
          </p>
        ) : <p className="muted">No shared settings yet.</p>}
        {owner && <p><button className="link-button" onClick={shareMine}>Share my current scoring and slots with the league</button></p>}
      </section>

      <section>
        <h2>Teams</h2>
        {data.teams.map((t) => (
          <div key={t.id} className="card" style={{ marginBottom: 12 }}>
            <h3 style={{ marginTop: 0 }}>
              {t.name} {t.mine && <span className="badge">you</span>} {t.manual && <span className="badge" title="Managed by hand by the league owner">added by owner</span>}
            </h3>
            <Roster players={t.players} />
            {t.mine && !t.manual && <p className="muted">This is your roster from the Fantasy page. <Link to="/fantasy">Edit it there</Link>.</p>}
            <p>
              {(t.mine || owner) && (
                <button className="link-button" onClick={() => {
                  const name = window.prompt('Team name', t.name)
                  if (name && name.trim()) act(() => call('PUT', `/api/leagues/${id}/teams/${t.id}`, { name }))
                }}>Rename</button>
              )}{' '}
              {owner && t.manual && <button className="link-button" onClick={() => setEditing(editing === t.id ? null : t.id)}>{editing === t.id ? 'Close roster editor' : 'Edit roster'}</button>}{' '}
              {owner && !t.mine && <button className="link-button" onClick={() => window.confirm(`Remove ${t.name} from the league?`) && act(() => call('DELETE', `/api/leagues/${id}/teams/${t.id}`))}>Remove team</button>}
            </p>
            {owner && t.manual && editing === t.id && (
              <>
                <p>
                  {t.players.map((p) => (
                    <span key={p.id} style={{ marginRight: 10, whiteSpace: 'nowrap' }}>
                      {p.name} <button className="link-button" onClick={() => act(() => call('PUT', `/api/leagues/${id}/teams/${t.id}/players`, { players: t.players.filter((x) => x.id !== p.id) }))}>x</button>
                    </span>
                  ))}
                </p>
                <PasteRoster pool={pool} label="Add these players" initial={t.players} onSave={(players) => act(() => call('PUT', `/api/leagues/${id}/teams/${t.id}/players`, { players }))} />
              </>
            )}
          </div>
        ))}
        {data.teams.length === 0 && <p className="status">No teams yet.</p>}
      </section>

      {owner && data.teams.length < data.teams_allowed && (
        <section>
          <h2>Add a team by hand</h2>
          <p className="muted">For someone in your league who doesn't use the site. Enter their team name, then add their players from the roster editor.</p>
          <form className="h2h-picks" onSubmit={(e) => { e.preventDefault(); act(() => call('POST', `/api/leagues/${id}/teams`, { name: newTeam, players: [] })).then(() => setNewTeam('')) }}>
            <label className="h2h-pick">Team name
              <input type="text" value={newTeam} maxLength={60} onChange={(e) => setNewTeam(e.target.value)} required />
            </label>
            <button type="submit" disabled={!newTeam.trim()}>Add team</button>
          </form>
        </section>
      )}

      <section>
        <h2>{owner ? 'Delete this league' : 'Leave this league'}</h2>
        {owner ? (
          <button className="link-button" onClick={() => window.confirm(`Delete ${data.name} for everyone? This can't be undone.`) && call('DELETE', `/api/leagues/${id}`).then(() => refresh()).then(() => navigate('/leagues')).catch((e) => setMessage(e.message))}>Delete league</button>
        ) : (
          <button className="link-button" onClick={() => window.confirm(`Leave ${data.name}? Your roster stops being shared with it.`) && call('DELETE', `/api/leagues/${id}/membership`).then(() => refresh()).then(() => navigate('/leagues')).catch((e) => setMessage(e.message))}>Leave league</button>
        )}
      </section>
    </main>
  )
}
