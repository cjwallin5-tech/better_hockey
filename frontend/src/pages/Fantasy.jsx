import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import FantasyWeek from '../components/FantasyWeek.jsx'
import Pickups from '../components/Pickups.jsx'
import { useAuth } from '../auth.js'
import RosterTools from '../components/RosterTools.jsx'
import { GOALIE_CATS, SCORING_PRESETS, SKATER_CATS, fantasyPoints, useFantasy, useScoring } from '../fantasy.js'
import { fmt1 } from '../format.js'

const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))
const signed = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)
const sum = (rows, key) => rows.reduce((t, r) => t + (r?.[key] ?? 0), 0)

const fp = (v) => v.toFixed(1)

function ScoringSettings({ scoring, setScoring }) {
  const setCat = (key, value) => {
    const next = { ...scoring }
    if (value === '' || Number.isNaN(Number(value))) delete next[key]
    else next[key] = Number(value)
    setScoring(next)
  }
  const field = ([key, label]) => (
    <label key={key} className="scoring-field">
      <input type="number" step="any" value={scoring[key] ?? ''} placeholder="0" onChange={(e) => setCat(key, e.target.value)} />
      <span>{label}</span>
    </label>
  )
  return (
    <details className="scoring" open>
      <summary>League scoring</summary>
      <p className="muted">Points per stat, to match your league's rules. Leave a stat blank to ignore it. Negative values work (e.g. goals against).</p>
      <div className="tabs" role="group" aria-label="Scoring presets">
        {Object.entries(SCORING_PRESETS).map(([name, preset]) => (
          <button key={name} onClick={() => setScoring(preset)}>{name}</button>
        ))}
      </div>
      <h3>Skaters</h3>
      <div className="scoring-grid">{SKATER_CATS.map(field)}</div>
      <h3>Goalies</h3>
      <div className="scoring-grid">{GOALIE_CATS.map(field)}</div>
    </details>
  )
}

export default function Fantasy() {
  const { list, togglePlayer, replacePlayers } = useFantasy()
  const [params, setParams] = useSearchParams()
  const { user, sync } = useAuth()
  const { scoring, setScoring } = useScoring()
  const [data, setData] = useState(null)
  const [kind, setKind] = useState('skater')
  const [query, setQuery] = useState('')

  useEffect(() => {
    Promise.all([fetch('/api/skaters').then((r) => r.json()), fetch('/api/goalies').then((r) => r.json())])
      .then(([skaters, goalies]) => setData({ skaters, goalies: goalies.goalies }))
      .catch(() => setData({ skaters: [], goalies: [] }))
  }, [])

  const taken = useMemo(() => new Set(list.players.map((p) => p.id)), [list])
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q || !data) return []
    const pool = kind === 'goalie' ? data.goalies : data.skaters
    return pool.filter((r) => r.name.toLowerCase().includes(q) && !taken.has(r.player_id)).slice(0, 8)
  }, [query, kind, data, taken])

  const loadRoster = ({ players, scoring: sc }) => {
    replacePlayers(players)
    if (sc && Object.keys(sc).length) setScoring(sc)
    if (params.has('roster')) setParams({}, { replace: true }) // the link has done its job
  }

  const add = (r) => {
    togglePlayer({ id: r.player_id, kind, name: r.name })
    setQuery('')
  }

  const skaterRows = list.players.filter((p) => p.kind === 'skater').map((p) => ({ p, row: data?.skaters.find((s) => s.player_id === p.id) }))
  const goalieRows = list.players.filter((p) => p.kind === 'goalie').map((p) => ({ p, row: data?.goalies.find((g) => g.player_id === p.id) }))
  const skaterTotals = skaterRows.map((r) => r.row).filter(Boolean)
  const goalieTotals = goalieRows.map((r) => r.row).filter(Boolean)

  return (
    <main>
      <header>
        <h1>Your fantasy team</h1>
        <p>Add the players on your fantasy roster, set your league's scoring below, and follow their fantasy points in one place. The roster is saved in this browser only.</p>
      </header>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={kind === 'skater'} className={kind === 'skater' ? 'on' : ''} onClick={() => setKind('skater')}>Skaters</button>
        <button role="tab" aria-selected={kind === 'goalie'} className={kind === 'goalie' ? 'on' : ''} onClick={() => setKind('goalie')}>Goalies</button>
      </div>
      <div className="picker">
        <div className="search-box">
          <input
            type="search"
            placeholder={`Add a ${kind}…`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {matches.length > 0 && (
            <ul className="results">
              {matches.map((m) => (
                <li key={m.player_id}>
                  <button onClick={() => add(m)}>
                    {m.name} <span>{m.team} · {kind === 'goalie' ? 'G' : m.position}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <RosterTools players={list.players} scoring={scoring} onLoad={loadRoster} shared={params.get('roster')} />

      <ScoringSettings scoring={scoring} setScoring={setScoring} />

      {list.players.length === 0 && (
        <p className="status">No players yet. Search above, or press ☆ Add to team on a <Link to="/skaters">player</Link> or <Link to="/goalies">goalie</Link> page.</p>
      )}
      {list.players.length > 0 && !data && <p className="status">Loading…</p>}

      {data && skaterRows.length > 0 && (
        <>
          <h2>Skaters</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th className="left">Player</th><th className="left">Team</th><th>GP</th><th>G</th><th>A</th><th>P</th><th>Fantasy pts</th><th>Per GP</th><th>Pace</th><th>L10 P</th><th>L10 pace</th><th /></tr>
              </thead>
              <tbody>
                {skaterRows.map(({ p, row }) => (
                  <tr key={p.id}>
                    <td className="left">
                      <Link to={`/player/${p.id}`}>{p.name}</Link>
                      {row?.traded && <span className="badge">↔ traded</span>}
                      {row?.games_out >= 2 && <span className="badge warn" title="Not in the team's last games">out {row.games_out}</span>}
                    </td>
                    {row ? (
                      <>
                        <td className="left">{row.team}</td><td>{row.games_played}</td><td>{row.goals}</td><td>{row.assists}</td>
                        <td>{row.points}</td>
                        <td className="accent">{fp(fantasyPoints(row, SKATER_CATS, scoring))}</td>
                        <td>{row.games_played ? (fantasyPoints(row, SKATER_CATS, scoring) / row.games_played).toFixed(2) : '–'}</td>
                        <td>{fmt1(row.point_pace)}</td>
                        <td>{row.recent_points ?? '–'}</td><td>{fmt1(row.recent_pace)}</td>
                      </>
                    ) : (
                      <td className="left" colSpan="10"><span className="muted">No games this season</span></td>
                    )}
                    <td><button className="link-button" onClick={() => togglePlayer(p)}>Remove</button></td>
                  </tr>
                ))}
              </tbody>
              {skaterTotals.length > 1 && (
                <tfoot>
                  <tr>
                    <td className="left">Team total</td><td />
                    <td /><td>{sum(skaterTotals, 'goals')}</td><td>{sum(skaterTotals, 'assists')}</td>
                    <td>{sum(skaterTotals, 'points')}</td>
                    <td className="accent">{fp(skaterTotals.reduce((t, r) => t + fantasyPoints(r, SKATER_CATS, scoring), 0))}</td><td />
                    <td>{fmt1(sum(skaterTotals, 'point_pace'))}</td>
                    <td>{sum(skaterTotals, 'recent_points')}</td><td>{fmt1(sum(skaterTotals, 'recent_pace'))}</td><td />
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </>
      )}

      {data && goalieRows.length > 0 && (
        <>
          <h2>Goalies</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th className="left">Goalie</th><th className="left">Team</th><th>GP</th><th>W</th><th>L</th><th>Fantasy pts</th><th>Per GP</th><th>SV%</th><th>GAA</th><th>GSAA</th><th>Recent SV%</th><th /></tr>
              </thead>
              <tbody>
                {goalieRows.map(({ p, row }) => (
                  <tr key={p.id}>
                    <td className="left"><Link to={`/goalie/${p.id}`}>{p.name}</Link></td>
                    {row ? (
                      <>
                        <td className="left">{row.team}</td><td>{row.games_played}</td><td>{row.wins}</td><td>{row.losses}</td>
                        <td className="accent">{fp(fantasyPoints(row, GOALIE_CATS, scoring))}</td>
                        <td>{row.games_played ? (fantasyPoints(row, GOALIE_CATS, scoring) / row.games_played).toFixed(2) : '–'}</td>
                        <td>{sv(row.save_pct)}</td><td>{row.gaa?.toFixed(2)}</td><td>{signed(row.gsaa)}</td><td>{sv(row.recent_save_pct)}</td>
                      </>
                    ) : (
                      <td className="left" colSpan="10"><span className="muted">No games this season</span></td>
                    )}
                    <td><button className="link-button" onClick={() => togglePlayer(p)}>Remove</button></td>
                  </tr>
                ))}
              </tbody>
              {goalieTotals.length > 1 && (
                <tfoot>
                  <tr>
                    <td className="left">Team total</td><td /><td>{sum(goalieTotals, 'games_played')}</td>
                    <td>{sum(goalieTotals, 'wins')}</td><td>{sum(goalieTotals, 'losses')}</td>
                    <td className="accent">{fp(goalieTotals.reduce((t, r) => t + fantasyPoints(r, GOALIE_CATS, scoring), 0))}</td><td /><td /><td /><td /><td /><td />
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </>
      )}

      {list.players.length > 0 && <FantasyWeek players={list.players} />}

      {data && <Pickups data={data} kind={kind} rosterIds={taken} scoring={scoring} onAdd={add} />}

      {list.players.length > 1 && (
        <p><Link to={`/compare?ids=${list.players.filter((p) => p.kind === (skaterRows.length ? 'skater' : 'goalie')).slice(0, 3).map((p) => p.id).join(',')}`}>Compare your players →</Link></p>
      )}
    </main>
  )
}
