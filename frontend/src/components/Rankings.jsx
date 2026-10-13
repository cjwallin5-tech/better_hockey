import { useEffect, useState } from 'react'

const ordinal = (n) => {
  const v = n % 100
  if (v >= 11 && v <= 13) return `${n}th`
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`
}
const sv = (v) => v.toFixed(3).replace(/^0/, '')
const int = (v) => v.toLocaleString()

const LABELS = {
  games_played: ['Games played', int],
  goals: ['Goals', int],
  assists: ['Assists', int],
  points: ['Points', int],
  points_per_game: ['Points / game', (v) => v.toFixed(2), 'min 300 GP'],
  point_pace: ['Point pace', (v) => v.toFixed(1), 'half the busiest player\'s games'],
  plus_minus: ['Plus/minus', int],
  pim: ['Penalty minutes', int],
  pp_goals: ['Power-play goals', int],
  pp_points: ['Power-play points', int],
  game_winning_goals: ['Game-winning goals', int],
  shots: ['Shots', int],
  hits: ['Hits', int, 'since 2005-06'],
  blocked_shots: ['Blocked shots', int, 'since 2005-06'],
  takeaways: ['Takeaways', int, 'since 2005-06'],
  giveaways: ['Giveaways', int, 'since 2005-06'],
  wins: ['Wins', int],
  shutouts: ['Shutouts', int],
  saves: ['Saves', int],
  save_pct: ['Save %', sv, 'min 150 GP'],
  gaa: ['Goals-against average', (v) => v.toFixed(2), 'min 150 GP'],
  gsaa: ['Goals saved above average', (v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}`],
}
// Rate stats are floored differently for a single season than for a career.
const SEASON_NOTES = { point_pace: 'half the busiest player\'s games', save_pct: 'half the busiest goalie\'s games', gaa: 'half the busiest goalie\'s games' }

export function RankCards({ ranks, scope, noun }) {
  const entries = Object.entries(ranks ?? {})
  if (entries.length === 0) return <p className="status">No ranked stats for this selection.</p>
  return (
    <div className="def-grid">
      {entries.map(([stat, r]) => {
        const [label, fmt, careerNote] = LABELS[stat] ?? [stat, (v) => v]
        const note = scope === 'season' ? SEASON_NOTES[stat] : careerNote
        const pct = Math.max(2, 100 * (1 - (r.rank - 1) / r.of)) // top of the board = full bar
        return (
          <div className="def-card" key={stat}>
            <div className="def-top">
              <span>{label}</span>
              <strong>{fmt(r.value)}</strong>
            </div>
            <div className="bar" title={`${ordinal(r.rank)} of ${r.of.toLocaleString()}`}>
              <div style={{ width: `${pct}%` }} />
            </div>
            <div className="def-foot">
              {ordinal(r.rank)} {scope === 'season' ? `of ${r.of.toLocaleString()} ${noun}s this season` : `all-time of ${r.of.toLocaleString()}`}
              {note && <em> · {note}</em>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/** Where a current player ranks this season and where their career ranks among all NHL history. */
export default function Rankings({ playerId, kind }) {
  const [result, setResult] = useState({ id: null, data: null })
  const [view, setView] = useState('season')

  useEffect(() => {
    fetch(`/api/players/${playerId}/rankings`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setResult({ id: playerId, data }))
      .catch(() => setResult({ id: playerId, data: null }))
  }, [playerId])

  const d = result.id === playerId ? result.data : null
  if (!d) return null
  const tabs = [['season', 'This season'], ['regular', 'All-time'], ...(d.alltime.playoffs ? [['playoffs', 'All-time playoffs']] : [])]

  return (
    <section>
      <h2>Rankings</h2>
      <p className="sub">
        This season: among every {kind} with a game played. All-time: this career among every {kind} in NHL
        history. Rate stats only count players with enough games.
      </p>
      <div className="tabs" role="tablist">
        {tabs.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={view === id} className={view === id ? 'on' : ''} onClick={() => setView(id)}>{label}</button>
        ))}
      </div>
      <RankCards
        ranks={view === 'season' ? d.season : d.alltime[view]}
        scope={view === 'season' ? 'season' : 'alltime'}
        noun={kind}
      />
    </section>
  )
}
