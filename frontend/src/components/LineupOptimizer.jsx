import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { buildEntries, optimize } from '../lineup.js'

const dayName = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short' })
const GROUP_ORDER = ['C', 'L', 'R', 'D', 'G']
const ok = (r) => (r.ok ? r.json() : null)

/**
 * Who to start each day this week: your players' games over the next 7 days, scored under your league (points per game,
 * or z-score per game in a category league) and moved by the matchup, then the best players per position into your slots.
 * values is the Map from value.js / categories.js; league is the cleaned league ({ slots, format }).
 */
export default function LineupOptimizer({ players, values, scoring, league }) {
  const [mode, setMode] = useState('daily')
  const [state, setState] = useState({ key: null, week: null, streaming: null })
  const key = players.map((p) => p.id).join(',')
  const isCats = league.format === 'categories'

  useEffect(() => {
    if (!key) return
    let ignore = false
    const hasGoalie = players.some((p) => p.kind === 'goalie')
    Promise.all([
      fetch(`/api/fantasy/week?ids=${key}&days=7`).then(ok).catch(() => null),
      hasGoalie ? fetch('/api/streaming/goalies?days=7').then(ok).catch(() => null) : null,
    ]).then(([week, streaming]) => !ignore && setState({ key, week, streaming }))
    return () => { ignore = true }
  }, [key, players])

  const ready = state.key === key
  const entries = useMemo(
    () => (ready && state.week ? buildEntries({
      roster: players, week: state.week.players, streaming: state.streaming?.goalies, values, scoring, isCats,
    }) : []),
    [ready, state, players, values, scoring, isCats],
  )
  const plan = useMemo(() => optimize({ entries, slots: league.slots, mode }), [entries, league.slots, mode])

  if (!key) return <p className="status">Add players to build a lineup.</p>
  if (!ready) return <p className="status">Loading…</p>
  if (!state.week) return <p className="status">Couldn't load this week's schedule.</p>

  const sorted = [...entries].sort((a, b) => GROUP_ORDER.indexOf(a.group) - GROUP_ORDER.indexOf(b.group) || (plan.byPlayer.get(b.id).score - plan.byPlayer.get(a.id).score))
  const today = plan.dates[0]
  const todayStart = sorted.filter((e) => plan.starts.get(today)?.has(e.id))
  const todaySit = sorted.filter((e) => e.games.some((g) => g.date === today) && !plan.starts.get(today)?.has(e.id))
  const unit = isCats ? 'z' : 'pts'
  const noGoalieData = players.some((p) => p.kind === 'goalie') && !state.streaming
  const unknown = entries.filter((e) => !e.known)

  return (
    <section>
      <h2>Lineup optimizer</h2>
      <p className="sub">
        The best lineup for the next 7 days under your {isCats ? 'categories' : 'scoring'} and slots
        ({GROUP_ORDER.filter((g) => league.slots[g]).map((g) => `${league.slots[g]} ${g}`).join(', ')}; change them in Scoring &amp; backup).
        Each game is scored by the player's expected {isCats ? 'z-score' : 'fantasy points'} a game, nudged up or down by how soft the opponent is,
        and a goalie's by his chance to start times what a start there is worth. It can't see injuries (a badge marks players who have missed
        recent games), so check your lineup against the news before locking it.
      </p>
      <div className="tabs" role="group" aria-label="Lineup changes">
        <button className={mode === 'daily' ? 'on' : ''} onClick={() => setMode('daily')}>Change lineup daily</button>
        <button className={mode === 'weekly' ? 'on' : ''} onClick={() => setMode('weekly')}>Lock lineup for the week</button>
      </div>
      {noGoalieData && <p className="notice">Goalie start chances didn't load, so your goalies have no games below.</p>}
      {unknown.length > 0 && <p className="muted">No stats yet for {unknown.map((e) => e.name).join(', ')}, so they are scored 0.</p>}

      {plan.dates.length === 0 ? <p className="status">None of your players have a game in the next 7 days.</p> : (
        <>
          <p>
            Expected total over the week: <strong className="accent">{plan.total.toFixed(1)} {unit}</strong>
            {mode === 'daily' && <> ({dayName(today)}: <strong>{todayStart.map((e) => e.name).join(', ') || 'nobody'}</strong>{todaySit.length > 0 && <>; sit {todaySit.map((e) => e.name).join(', ')}</>})</>}
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="left">Player</th><th>Pos</th>
                  {plan.dates.map((d) => <th key={d}>{dayName(d)} {d.slice(5)}</th>)}
                  <th title="Games started, and the expected score they add">Starts</th>
                  <th title="Games he plays that you would sit, and what they would have scored">Benched</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((e) => {
                  const stat = plan.byPlayer.get(e.id)
                  return (
                    <tr key={e.id}>
                      <td className="left">
                        <Link to={`/${e.kind === 'goalie' ? 'goalie' : 'player'}/${e.id}`}>{e.name}</Link>
                        {e.out >= 3 && <span className="badge warn" title="Has missed several of the team's recent games: check he is healthy">out {e.out}</span>}
                      </td>
                      <td>{e.group}</td>
                      {plan.dates.map((d) => {
                        const games = e.games.filter((g) => g.date === d)
                        if (games.length === 0) return <td key={d} className="muted">–</td>
                        const started = plan.starts.get(d).has(e.id)
                        const score = games.reduce((t, g) => t + g.score, 0)
                        const g = games[0]
                        return (
                          <td key={d} className={started ? 'accent' : 'muted'} title={`${g.home ? 'vs' : '@'} ${g.opponent}${g.chance != null ? `, ${Math.round(g.chance * 100)}% to start` : ''}`}>
                            {started ? 'Start' : 'Sit'} <span className="muted">{score.toFixed(1)}</span>
                          </td>
                        )
                      })}
                      <td>{stat.starts} <span className="muted">({stat.score.toFixed(1)})</span></td>
                      <td>{stat.sat} <span className="muted">({stat.satScore.toFixed(1)})</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
