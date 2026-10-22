import { useEffect, useState } from 'react'

// One rankings request per player, shared by the stat tiles and the table below them.
const cache = new Map()
function fetchRankings(id) {
  if (!cache.has(id)) {
    cache.set(id, fetch(`/api/players/${id}/rankings`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => { cache.delete(id); return null }))
  }
  return cache.get(id)
}

/** The player's rankings ({ season, alltime: { regular, playoffs } }), or null until loaded or when unavailable. */
export function useRankings(playerId) {
  const [state, setState] = useState({ id: null, data: null })
  useEffect(() => {
    let ignore = false
    fetchRankings(playerId).then((data) => !ignore && setState({ id: playerId, data }))
    return () => { ignore = true }
  }, [playerId])
  return state.id === playerId ? state.data : null
}

/** Short caption for a stat tile: 'season' gives '12th of 704', 'alltime' gives '5th all-time'. */
export function rankNote(r, scope) {
  if (!r) return undefined
  return scope === 'season' ? `${ordinal(r.rank)} of ${r.of.toLocaleString()}` : `${ordinal(r.rank)} all-time`
}

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

// Stats whose rank already shows on a stat tile (this season on the page's tiles, all-time on the Career tiles).
const ON_SEASON_TILES = new Set(['games_played', 'goals', 'assists', 'points', 'plus_minus', 'wins', 'shutouts', 'save_pct', 'gaa'])
const ON_CAREER_TILES = new Set(['games_played', 'goals', 'assists', 'points', 'points_per_game', 'plus_minus', 'pim', 'pp_goals', 'game_winning_goals', 'shots', 'wins', 'shutouts', 'save_pct', 'gaa'])

/** The rankings that have no tile: stats not shown elsewhere on the page, this season next to all-time. */
export default function Rankings({ playerId, kind }) {
  const d = useRankings(playerId)
  if (!d) return null
  const season = Object.fromEntries(Object.entries(d.season ?? {}).filter(([k]) => !ON_SEASON_TILES.has(k)))
  const career = Object.fromEntries(Object.entries(d.alltime?.regular ?? {}).filter(([k]) => !ON_CAREER_TILES.has(k)))
  const stats = [...new Set([...Object.keys(season), ...Object.keys(career)])]
  if (stats.length === 0) return null
  const cell = (stat, r, scope) => {
    if (!r) return <td className="muted">–</td>
    const [, fmt] = LABELS[stat] ?? [stat, (v) => v]
    return <td>{fmt(r.value)} <span className="muted">· {rankNote(r, scope)}</span></td>
  }
  return (
    <section>
      <h2>More rankings</h2>
      <p className="sub">
        Among every {kind} with a game played this season, and among every {kind} in NHL history. Rate stats only count
        players with enough games. Ranks for the other stats are shown on the tiles above.
      </p>
      <div className="table-wrap">
        <table className="rank-table">
          <thead><tr><th className="left">Stat</th><th className="left">This season</th><th className="left">All-time</th></tr></thead>
          <tbody>
            {stats.map((stat) => (
              <tr key={stat}>
                <td className="left">{(LABELS[stat] ?? [stat])[0]}</td>
                {cell(stat, season[stat], 'season')}
                {cell(stat, career[stat], 'alltime')}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
