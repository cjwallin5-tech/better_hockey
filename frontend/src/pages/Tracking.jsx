import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { seasonLabel } from '../career.js'
import { useUrlSync } from '../urlState.js'

const day = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : '–')
const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

function formatValue(v, unit, stat) {
  if (v == null) return '–'
  if (unit === 'share') return `${(v * 100).toFixed(1)}%`
  if (unit === 'mph') return v.toFixed(1)
  if (unit === 'mi') return v.toFixed(stat === 'distance_per_game' ? 2 : 1)
  return Math.round(v).toLocaleString()
}
const UNIT_LABEL = { mph: ' mph', mi: ' mi', share: '' }

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

function SkaterBoard({ stat, setStat, season, setSeason, position, setPosition, minGp, setMinGp }) {
  const url = `/api/tracking/leaders?stat=${stat}&season=${season}&position=${position}&min_gp=${minGp || 0}&limit=50`
  const { data, error } = useApi(url)
  const meta = data
  const note = {
    top_shot: 'The hardest single shot of the season, from the NHL\'s tracking.',
    top_speed: 'The fastest the player skated at any point in the season.',
    bursts_22: 'Times the player skated faster than 22 mph (about 35 km/h).',
    bursts_20: 'Times the player skated faster than 20 mph.',
    hard_shots: 'Shot attempts (on goal, missed or blocked) at 90 mph or harder.',
    avg_shot: 'Average speed across all of the player\'s tracked shots.',
    distance_per_game: 'Miles skated per game played.',
    oz_time: 'Share of the player\'s ice time spent in the offensive zone.',
    dz_time: 'Share of the player\'s ice time spent in the defensive zone.',
    hd_sog: 'Shots on goal from the high-danger areas in front of the net.',
  }[stat]

  return (
    <>
      <div className="h2h-picks">
        <label className="h2h-pick">Stat
          <select value={stat} onChange={(e) => setStat(e.target.value)}>
            {(meta?.stats ?? [{ id: stat, label: stat }]).map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </label>
        <label className="h2h-pick">Season
          <select value={season} onChange={(e) => setSeason(e.target.value)}>
            <option value="">{meta?.seasons?.[0] ? `${seasonLabel(meta.seasons[0])} (latest)` : 'Latest'}</option>
            {(meta?.seasons ?? []).slice(1).map((s) => <option key={s} value={s}>{seasonLabel(s)}</option>)}
            <option value="all">All seasons</option>
          </select>
        </label>
        <label className="h2h-pick">Position
          <select value={position} onChange={(e) => setPosition(e.target.value)}>
            {[['', 'All skaters'], ['F', 'Forwards'], ['C', 'Centers'], ['L', 'Left wings'], ['R', 'Right wings'], ['D', 'Defensemen']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="h2h-pick">Min games
          <input type="number" min="0" max="82" value={minGp} onChange={(e) => setMinGp(e.target.value)} style={{ minWidth: 80, width: 80 }} />
        </label>
      </div>
      {note && <p className="sub">{note}</p>}
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && data.rows.length === 0 && <p className="status">No tracking data yet for these filters.</p>}
      {data && data.rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th><th className="left">Player</th><th className="left">Team</th><th className="left">Pos</th>
                {data.season === 'all' && <th className="left">Season</th>}
                <th>GP</th><th>{data.label}</th><th>NHL percentile</th>
                {data.rows.some((r) => r.event_date) && <th className="left">When</th>}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={`${r.player_id}-${r.season_id}`}>
                  <td>{i + 1}</td>
                  <td className="left"><Link to={`/player/${r.player_id}`}>{r.name}</Link></td>
                  <td className="left">{r.team}</td><td className="left">{r.position}</td>
                  {data.season === 'all' && <td className="left">{seasonLabel(r.season_id)}</td>}
                  <td>{r.games_played}</td>
                  <td className="accent">{formatValue(r.value, data.unit, data.stat)}{UNIT_LABEL[data.unit] ?? ''}</td>
                  <td>{r.percentile == null ? '–' : `${Math.round(r.percentile * 100)}`}</td>
                  {data.rows.some((x) => x.event_date) && (
                    <td className="left">{r.game_id && r.current_season ? <Link to={`/game/${r.game_id}`}>{day(r.event_date)}</Link> : day(r.event_date)}</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function GoalieBoard({ stat, setStat, season, setSeason }) {
  const { data, error } = useApi(`/api/tracking/goalies?stat=${stat}&season=${season}&limit=50`)
  const pct = (v) => (stat === 'games_above_900' ? (v == null ? '–' : `${(v * 100).toFixed(1)}%`) : sv(v))
  return (
    <>
      <div className="h2h-picks">
        <label className="h2h-pick">Stat
          <select value={stat} onChange={(e) => setStat(e.target.value)}>
            {(data?.stats ?? [{ id: stat, label: stat }]).map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </label>
        <label className="h2h-pick">Season
          <select value={season} onChange={(e) => setSeason(e.target.value)}>
            <option value="">{data?.seasons?.[0] ? `${seasonLabel(data.seasons[0])} (latest)` : 'Latest'}</option>
            {(data?.seasons ?? []).slice(1).map((s) => <option key={s} value={s}>{seasonLabel(s)}</option>)}
          </select>
        </label>
      </div>
      <p className="sub">
        Save percentage by where the shot came from, from the NHL's tracking. Goalies need at least {data?.minimum_shots ?? 60} shots faced
        from that range to qualify.
      </p>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && data.rows.length === 0 && <p className="status">No tracking data yet for these filters.</p>}
      {data && data.rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead><tr><th>#</th><th className="left">Goalie</th><th className="left">Team</th><th>{data.label}</th><th>Overall</th><th>High</th><th>Mid</th><th>Long</th><th>Shots</th></tr></thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={r.player_id}>
                  <td>{i + 1}</td>
                  <td className="left"><Link to={`/goalie/${r.player_id}`}>{r.name}</Link></td>
                  <td className="left">{r.team ?? '–'}</td>
                  <td className="accent">{pct(r.value)}</td>
                  <td>{sv(r.sv_all)}</td><td>{sv(r.sv_high)}</td><td>{sv(r.sv_mid)}</td><td>{sv(r.sv_long)}</td><td>{r.shots_faced}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export default function Tracking() {
  const initial = new URLSearchParams(window.location.search)
  const [kind, setKind] = useState(initial.get('kind') === 'goalie' ? 'goalie' : 'skater')
  const [stat, setStat] = useState(initial.get('stat') ?? '')
  const [season, setSeason] = useState(initial.get('season') ?? '')
  const [position, setPosition] = useState(initial.get('pos') ?? '')
  const [minGp, setMinGp] = useState(initial.get('gp') ?? '10')

  const defaultStat = kind === 'goalie' ? 'sv_high' : 'top_shot'
  const active = stat || defaultStat
  useUrlSync([['kind', kind, 'skater'], ['stat', stat, ''], ['season', season, ''], ['pos', position, ''], ['gp', minGp, '10']])

  const switchKind = (k) => { setKind(k); setStat(''); setSeason('') }

  return (
    <main>
      <header>
        <h1>Speed &amp; shots</h1>
        <p>
          The NHL's puck and player tracking (EDGE): who shoots hardest, skates fastest and covers the most ice. Tracking
          begins in 2021-22.
        </p>
      </header>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={kind === 'skater'} className={kind === 'skater' ? 'on' : ''} onClick={() => switchKind('skater')}>Skaters</button>
        <button role="tab" aria-selected={kind === 'goalie'} className={kind === 'goalie' ? 'on' : ''} onClick={() => switchKind('goalie')}>Goalies</button>
      </div>
      {kind === 'skater'
        ? <SkaterBoard stat={active} setStat={setStat} season={season} setSeason={setSeason} position={position} setPosition={setPosition} minGp={minGp} setMinGp={setMinGp} />
        : <GoalieBoard stat={active} setStat={setStat} season={season} setSeason={setSeason} />}
    </main>
  )
}
