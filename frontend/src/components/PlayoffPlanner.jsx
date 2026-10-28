import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import TeamLogo from './TeamLogo.jsx'
import { MatchupTag, ratioLabel } from './Matchups.jsx'
import { buildEntries, buildWeeks, goaliesInRange, planWeeks, playerWeeks, rangeFromSaved, rosterWeek, teamWindows } from '../playoffweeks.js'

const KEY = 'nhl-stats.fantasy-playoff-weeks'
const GROUP_ORDER = ['C', 'L', 'R', 'D', 'G']
const ok = (r) => (r.ok ? r.json() : null)
const short = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

function readSaved() {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? 'null')
  } catch {
    return null
  }
}

/**
 * How your roster's schedule looks in the weeks that decide your fantasy playoffs: pick the weeks (they default to the last three of the
 * season), and see what the best daily lineup is expected to score each week, how many games each player has, and which teams have the
 * most and softest games to target with pickups and trades. See playoffweeks.js for the maths.
 */
export default function PlayoffPlanner({ players, values, scoring, league }) {
  const [schedule, setSchedule] = useState({ status: 'loading', teams: [] })
  const [goalies, setGoalies] = useState(null)
  const [saved, setSaved] = useState(readSaved)
  const [showAll, setShowAll] = useState(false)
  const isCats = league.format === 'categories'
  const goalieKey = players.filter((p) => p.kind === 'goalie').map((p) => p.id).join(',')

  useEffect(() => {
    let ignore = false
    fetch('/api/fantasy/schedule').then(ok).then((d) => !ignore && setSchedule(d ? { status: 'ready', teams: d.teams } : { status: 'error', teams: [] }))
      .catch(() => !ignore && setSchedule({ status: 'error', teams: [] }))
    return () => { ignore = true }
  }, [])
  useEffect(() => {
    if (!goalieKey) return undefined
    let ignore = false
    fetch(`/api/fantasy/goalie-schedule?ids=${goalieKey}`).then(ok).then((d) => !ignore && setGoalies(d?.goalies ?? null)).catch(() => !ignore && setGoalies(null))
    return () => { ignore = true }
  }, [goalieKey])

  const weeks = useMemo(() => buildWeeks(schedule.teams.flatMap((t) => t.games.map((g) => g.date))), [schedule])
  const range = useMemo(() => rangeFromSaved(saved, weeks), [saved, weeks])
  const choose = (patch) => {
    const next = { from: weeks[range.from].start, to: weeks[range.to].start, ...patch }
    if (next.to < next.from) { if (patch.from) next.to = next.from; else next.from = next.to }   // keep the range from running backwards
    setSaved(next)
    try {
      localStorage.setItem(KEY, JSON.stringify(next))
    } catch {
      // storage unavailable: the choice simply won't persist
    }
  }

  const first = weeks[range.from]?.start
  const last = weeks[range.to]?.end
  const entries = useMemo(() => {
    if (!first) return []
    const week = rosterWeek({ roster: players, teams: schedule.teams, teamOf: (id) => values.get(id)?.team, first, last })
    return buildEntries({ roster: players, week, streaming: goaliesInRange(goalieKey ? goalies : [], first, last), values, scoring, isCats })
  }, [players, schedule, goalies, goalieKey, values, scoring, isCats, first, last])
  const plan = useMemo(() => (entries.length ? planWeeks({ entries, slots: league.slots, weeks, range }) : null), [entries, league.slots, weeks, range])
  const rows = useMemo(() => (plan ? playerWeeks({ entries, plan: plan.plan, weeks, range }) : []), [plan, entries, weeks, range])
  const teams = useMemo(() => (first ? teamWindows(schedule.teams, weeks, range).sort((a, b) => b.index - a.index || b.games - a.games || a.name.localeCompare(b.name)) : []), [schedule, weeks, range, first])
  const mine = useMemo(() => {
    const count = new Map()
    for (const p of players) {
      const team = values.get(p.id)?.team
      if (team) count.set(team, (count.get(team) ?? 0) + 1)
    }
    return count
  }, [players, values])

  if (schedule.status === 'loading') return <p className="status">Loading…</p>
  if (schedule.status === 'error' || weeks.length === 0) return <p className="status">Couldn't load the rest of the schedule.</p>

  const span = weeks.slice(range.from, range.to + 1)
  const unit = isCats ? 'z' : 'pts'
  const noGoalieData = goalieKey && goalies === null
  const unknown = entries.filter((e) => !e.known)
  const lightest = plan && plan.weeks.length > 1 ? plan.weeks.reduce((a, b) => (b.score < a.score ? b : a)) : null
  const shown = showAll ? teams : teams.slice(0, 10)
  const weekLabel = (w, i) => `${short(w.start)} – ${short(w.end)}${i === weeks.length - 1 ? ' (last week)' : ''}`

  return (
    <section>
      <h2>Playoff-week planner</h2>
      <p className="sub">
        The weeks that decide a fantasy season are usually the last few. Pick yours (they default to the last three weeks of the season) to see
        what your best daily lineup is expected to score in each, how many games each player has, and which teams have the most and softest
        games to target. Weeks run Monday to Sunday. Matchup ratings use today's team strength, so far-off weeks are rough, and nothing here
        sees injuries or trades that have not happened yet.
      </p>
      <div className="controls">
        <label>From week{' '}
          <select value={range.from} onChange={(e) => choose({ from: weeks[Number(e.target.value)].start })} aria-label="First playoff week">
            {weeks.map((w, i) => <option key={w.start} value={i}>{weekLabel(w, i)}</option>)}
          </select>
        </label>{' '}
        <label>to{' '}
          <select value={range.to} onChange={(e) => choose({ to: weeks[Number(e.target.value)].start })} aria-label="Last playoff week">
            {weeks.map((w, i) => <option key={w.start} value={i} disabled={i < range.from}>{weekLabel(w, i)}</option>)}
          </select>
        </label>
      </div>

      {players.length === 0 && <p className="status">Add players to plan your weeks.</p>}
      {noGoalieData && <p className="notice">Goalie start chances didn't load, so your goalies have no games below.</p>}
      {unknown.length > 0 && <p className="muted">No stats yet for {unknown.map((e) => e.name).join(', ')}, so they are scored 0.</p>}

      {plan && (
        <>
          <h3>Your expected score by week</h3>
          <p>
            Best daily lineup ({GROUP_ORDER.filter((g) => league.slots[g]).map((g) => `${league.slots[g]} ${g}`).join(', ')}), added up per week:{' '}
            <strong className="accent">{plan.total.toFixed(1)} {unit}</strong> over {span.length} week{span.length === 1 ? '' : 's'}.
            {lightest && <> Your lightest week is <strong>{short(lightest.start)}</strong> ({lightest.score.toFixed(1)} {unit}).</>}
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="left">Week</th>
                  <th title="Games your players have that week">Games</th>
                  <th title="Games your best lineup uses">Started</th>
                  <th title={isCats ? 'Expected z-score of the started games' : 'Expected fantasy points of the started games'}>Expected {unit}</th>
                </tr>
              </thead>
              <tbody>
                {plan.weeks.map((w) => (
                  <tr key={w.start} className={lightest && w.start === lightest.start ? 'muted' : ''}>
                    <td className="left">{short(w.start)} – {short(w.end)}</td><td>{w.games}</td><td>{w.starts}</td><td className="accent">{w.score.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3>Your players</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="left">Player</th><th>Pos</th><th>Team</th>
                  {span.map((w) => <th key={w.start} title={`Games the week of ${short(w.start)}`}>{short(w.start)}</th>)}
                  <th title="Games in all the chosen weeks">Games</th>
                  <th title="The score your best lineup gets from him over these weeks">Adds ({unit})</th>
                </tr>
              </thead>
              <tbody>
                {[...rows].sort((a, b) => GROUP_ORDER.indexOf(a.group) - GROUP_ORDER.indexOf(b.group) || b.score - a.score).map((r) => {
                  const team = values.get(r.id)?.team
                  const busiest = Math.max(...rows.map((x) => x.total), 0)
                  return (
                    <tr key={r.id}>
                      <td className="left"><Link to={`/${r.kind === 'goalie' ? 'goalie' : 'player'}/${r.id}`}>{r.name}</Link></td>
                      <td>{r.group}</td><td>{team ?? '–'}</td>
                      {r.weeks.map((n, i) => <td key={span[i].start} className={n <= 2 ? 'muted' : n >= 4 ? 'accent' : ''} title={n <= 2 ? 'A light week' : n >= 4 ? 'A heavy week' : undefined}>{n}</td>)}
                      <td><strong>{r.total}</strong>{r.total === 0 && busiest > 0 ? <span className="badge warn" title="No games in these weeks">none</span> : null}</td>
                      <td className="accent">{r.score.toFixed(1)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h3>Teams to target</h3>
      <p className="sub">
        Ranked by how many soft games a team has in these weeks (the sum of each game's matchup ratio above or below average, so more games and
        softer opponents both count). Use it to pick up or trade for players on teams with a heavy, soft finish. A goalie's schedule is better read from
        the average goalie matchup column.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Team</th>
              {span.map((w) => <th key={w.start} title={`Games the week of ${short(w.start)}`}>{short(w.start)}</th>)}
              <th title="Games in all the chosen weeks">Games</th>
              <th title="Games on the second night of a back-to-back">B2B</th>
              <th title="Average skater matchup: above average means softer defenses">Skater matchup</th>
              <th title="Average goalie matchup: above average means weaker offenses">Goalie matchup</th>
              <th title="The sum of each game's ratio above or below average: more games and softer games both raise it">Index</th>
              <th title="Players of yours on this team">Yours</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((t) => (
              <tr key={t.team}>
                <td className="left team-cell"><TeamLogo team={t} /><Link to={`/team/${t.team}`}>{t.name}</Link></td>
                {t.weeks.map((n, i) => <td key={span[i].start} className={n <= 2 ? 'muted' : n >= 4 ? 'accent' : ''}>{n}</td>)}
                <td><strong>{t.games}</strong></td><td>{t.backToBacks}</td>
                <td>{t.skaters != null && <MatchupTag ratio={t.skaters} label={ratioLabel(t.skaters)} />}{t.skaters != null ? ` ${t.skaters.toFixed(2)}` : '–'}</td>
                <td>{t.goalies != null && <MatchupTag ratio={t.goalies} label={ratioLabel(t.goalies)} who="goalies" />}{t.goalies != null ? ` ${t.goalies.toFixed(2)}` : '–'}</td>
                <td className="accent">{t.index >= 0 ? '+' : '−'}{Math.abs(t.index).toFixed(1)}</td>
                <td>{mine.get(t.team) ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {teams.length > 10 && (
        <p><button onClick={() => setShowAll((v) => !v)}>{showAll ? 'Show the top 10' : `Show all ${teams.length} teams`}</button></p>
      )}
    </section>
  )
}
