import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { mmss } from './Roles.jsx'

const n1 = (v) => (v == null ? '–' : v.toFixed(1))
const pct = (v) => (v == null ? '–' : `${(v * 100).toFixed(1)}%`)
const share = (v) => (v == null ? '–' : `${Math.round(v * 100)}%`)
const ordinal = (n) => {
  if (n == null) return ''
  const v = n % 100
  return `${n}${v >= 11 && v <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th')}`
}

function Stat({ label, value, rank, of, note }) {
  return (
    <div className="tile">
      <span>{label}</span>
      <strong>{value}</strong>
      <small className="muted">{rank ? `${ordinal(rank)} of ${of}` : ''}{rank && note ? '. ' : ''}{note}</small>
    </div>
  )
}

function Units({ units, kind }) {
  if (!units.length) return <p className="status">No {kind === 'pp' ? 'power-play' : 'penalty-kill'} units yet: not enough ice time on record.</p>
  const key = kind === 'pp' ? 'pp_share' : 'pk_share'
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="left">Unit</th><th className="left">Player</th><th className="left">Pos</th>
            <th title={kind === 'pp' ? "Share of the team's power-play time" : "Share of the team's penalty-kill time"}>{kind === 'pp' ? 'PP share' : 'PK share'}</th>
            <th title="Average per game">{kind === 'pp' ? 'PP TOI' : 'PK TOI'}</th>
            {kind === 'pp' && <><th title="Power-play goals this season">PPG</th><th title="Power-play points this season">PPP</th></>}
          </tr>
        </thead>
        <tbody>
          {units.flatMap((u) => u.players.map((p, i) => (
            <tr key={`${u.unit}-${p.player_id}`}>
              <td className="left">{i === 0 ? <strong>{u.unit}</strong> : ''}</td>
              <td className="left"><Link to={`/player/${p.player_id}`}>{p.name}</Link></td>
              <td className="left">{p.position}</td>
              <td className="accent">{share(p[key])}</td>
              <td>{mmss((kind === 'pp' ? p.pp_sec : p.sh_sec) / p.games)}</td>
              {kind === 'pp' && <><td>{p.pp_goals ?? '–'}</td><td>{p.pp_points ?? '–'}</td></>}
            </tr>
          )))}
        </tbody>
      </table>
    </div>
  )
}

/** A team's power play and penalty kill: figures with league ranks, and the units inferred from ice time. */
export default function SpecialTeams({ abbrev }) {
  const [last, setLast] = useState('0')
  const [state, setState] = useState({ key: null, data: null, error: null })
  const key = `${abbrev}|${last}`

  useEffect(() => {
    let ignore = false
    fetch(`/api/teams/${abbrev}/special-teams?last=${last}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status === 404 ? 'No ice-time data yet.' : `API returned ${r.status}`))))
      .then((data) => !ignore && setState({ key, data, error: null }))
      .catch((error) => !ignore && setState({ key, data: null, error: error.message }))
    return () => { ignore = true }
  }, [abbrev, last, key])
  const { data, error } = state.key === key ? state : { data: null, error: null }
  const t = data?.team
  const of = data?.league_teams

  return (
    <section>
      <h2>Special teams</h2>
      <div className="tabs" role="tablist">
        {[['0', 'Season'], ['10', 'Last 10'], ['5', 'Last 5']].map(([v, l]) => (
          <button key={v} role="tab" aria-selected={last === v} className={last === v ? 'on' : ''} onClick={() => setLast(v)}>{l}</button>
        ))}
      </div>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {t && (
        <>
          <section className="tiles">
            <Stat label="Power play %" value={pct(t.pp_pct)} rank={t.pp_pct_rank} of={of} note="season" />
            <Stat label="PP xG / 60" value={n1(t.pp_xgf60)} rank={t.pp_xgf60_rank} of={of} note="chances made" />
            <Stat label="PP goals / 60" value={n1(t.pp_gf60)} rank={t.pp_gf60_rank} of={of} />
            <Stat label="PP time / game" value={mmss(t.pp_toi_pg)} rank={t.pp_toi_pg_rank} of={of} />
            <Stat label="Penalty kill %" value={pct(t.pk_pct)} rank={t.pk_pct_rank} of={of} note="season" />
            <Stat label="PK xG against / 60" value={n1(t.pk_xga60)} rank={t.pk_xga60_rank} of={of} note="chances allowed" />
            <Stat label="PK goals against / 60" value={n1(t.pk_ga60)} rank={t.pk_ga60_rank} of={of} />
            <Stat label="Short-handed time / game" value={mmss(t.pk_toi_pg)} rank={t.pk_toi_pg_rank} of={of} note="1st = least" />
          </section>
          <h3>Power-play units</h3>
          <Units units={data.power_play} kind="pp" />
          <h3>Penalty-kill units</h3>
          <Units units={data.penalty_kill} kind="pk" />
          <p className="sub">
            The NHL doesn't publish units, so these are inferred from each skater's share of the team's special-teams ice time over
            these {t.games} games: PP1 is {Math.round(data.thresholds.pp1 * 100)}% or more (five at most), PP2 {Math.round(data.thresholds.pp2 * 100)}% or more.
            The penalty kill ranks forwards and defensemen separately, two of each per unit. xG per 60 counts the quality of the shots
            in that situation, so it settles faster than goals. Early in the season a few games decide a lot. League view:{' '}
            <Link to="/special-teams">all teams' special teams →</Link>
          </p>
        </>
      )}
    </section>
  )
}
