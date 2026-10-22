import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { mmss, signedMmss } from '../components/Roles.jsx'
import { useUrlSync } from '../urlState.js'
import { describe } from '../glossary.js'

function useApi(url) {
  const [state, setState] = useState({ url: null, data: null, error: null })
  useEffect(() => {
    let ignore = false
    fetch(url)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
      .then((data) => !ignore && setState({ url, data, error: null }))
      .catch((error) => !ignore && setState({ url, data: null, error: error.message }))
    return () => { ignore = true }
  }, [url])
  return state.url === url ? state : { data: null, error: null }
}

const unitName = (u) => u ?? 'no PP'
const pct = (v) => `${Math.round(v * 100)}%`

export default function Roles() {
  const initial = new URLSearchParams(window.location.search)
  const [dir, setDir] = useState(initial.get('dir') === 'down' ? 'down' : 'up')
  const [window_, setWindow] = useState(initial.get('window') ?? '5')
  const [kind, setKind] = useState(['pp', 'ev'].includes(initial.get('what')) ? initial.get('what') : 'all')
  const [position, setPosition] = useState(initial.get('pos') ?? '')
  useUrlSync([['dir', dir, 'up'], ['window', window_, '5'], ['what', kind, 'all'], ['pos', position, '']])

  const { data, error } = useApi(`/api/roles/changes?dir=${dir}&window=${window_}&kind=${kind}&position=${position}&limit=60`)
  const th = data?.thresholds

  return (
    <main>
      <header>
        <h1>Role changes</h1>
        <p>
          Who has moved up or down the power-play units, and who is playing more or less, over their last few games compared with
          earlier this season. Ice time is the earliest sign of a new role, and it shows up before the points do.
        </p>
      </header>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={dir === 'up'} className={dir === 'up' ? 'on' : ''} onClick={() => setDir('up')}>Moving up</button>
        <button role="tab" aria-selected={dir === 'down'} className={dir === 'down' ? 'on' : ''} onClick={() => setDir('down')}>Moving down</button>
      </div>
      <div className="h2h-picks">
        <label className="h2h-pick">Last
          <select value={window_} onChange={(e) => setWindow(e.target.value)}>
            {[3, 5, 8, 10, 15].map((n) => <option key={n} value={n}>{n} games</option>)}
          </select>
        </label>
        <label className="h2h-pick">Looking at
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="all">Everything</option>
            <option value="pp">Power play only</option>
            <option value="ev">Even-strength time only</option>
          </select>
        </label>
        <label className="h2h-pick">Position
          <select value={position} onChange={(e) => setPosition(e.target.value)}>
            {[['', 'All skaters'], ['F', 'Forwards'], ['C', 'Centers'], ['L', 'Left wings'], ['R', 'Right wings'], ['D', 'Defensemen']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>
      <p className="sub">
        Power-play unit comes from each player's share of their team's power-play time: {th ? pct(th.pp1) : '45%'} or more is PP1,{' '}
        {th ? pct(th.pp2) : '15%'} or more is PP2. A move counts when the unit changed and the share moved by a real amount, so
        someone hovering at a cut-off isn't reported every week. Even-strength time (overtime left out) is flagged at a
        {' '}{th ? mmss(th.ev_seconds) : '1:30'} change. It can't say why a role changed (an injury, a coach's choice), and early in the
        season the earlier games are few, so read the first weeks lightly.
      </p>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && data.rows.length === 0 && <p className="status">No skaters fit this yet. Try a shorter window or a different filter.</p>}
      {data && data.rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th><th className="left">Player</th><th className="left" title={describe('Team')}>Team</th><th className="left" title={describe('Pos')}>Pos</th><th title={describe('GP')}>GP</th>
                <th className="left" title={describe('Power-play unit')}>Power-play unit</th><th title={describe('PP time / game')}>PP time / game</th><th title={describe('PP share')}>PP share</th>
                <th title={describe('Even strength / game')}>Even strength / game</th><th title={describe('Total / game')}>Total / game</th><th className="left">What changed</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={r.player_id}>
                  <td>{i + 1}</td>
                  <td className="left"><Link to={`/player/${r.player_id}`}>{r.name}</Link></td>
                  <td className="left">{r.team}</td><td className="left">{r.position}</td><td>{r.games_played}</td>
                  <td className="left">{unitName(r.unit_base)} → <strong>{unitName(r.unit)}</strong></td>
                  <td>{mmss(r.pp_base)} → {mmss(r.pp)}</td>
                  <td>{pct(r.pp_share_base)} → {pct(r.pp_share)}</td>
                  <td>{mmss(r.ev_base)} → {mmss(r.ev)} <span className="muted">({signedMmss(r.ev_delta)})</span></td>
                  <td>{mmss(r.total_base)} → {mmss(r.total)}</td>
                  <td className="left">
                    {r.pp_change && <span className={r.pp_change === 'down' ? 'badge warn' : 'badge'}>{r.pp_label}</span>}
                    {r.ev_change && <span className={r.ev_change === 'down' ? 'badge warn' : 'badge'}>{r.ev_change === 'up' ? 'More ice time' : 'Less ice time'}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  )
}
