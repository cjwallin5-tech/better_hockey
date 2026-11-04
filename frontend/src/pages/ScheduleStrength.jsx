import { useEffect, useMemo, useState } from 'react'
import PageShell from '../components/PageShell.jsx'
import { Link } from 'react-router-dom'
import TeamLogo from '../components/TeamLogo.jsx'
import { useUrlSync } from '../urlState.js'
import { biggestSwing, difficultyRanks, extreme, fmtNet, fmtPts } from '../scheduleStrength.js'
import { Skeleton } from '../components/Skeleton.jsx'

const SORTS = [
  ['left', 'Remaining schedule'], ['next', 'Next 10 games'], ['played', 'Schedule so far'], ['b2b', 'Back-to-backs left'],
]
const value = (sort) => (r) => (sort === 'b2b' ? -r.back_to_backs_left : r[sort].schedule_points)
const pct = (v) => (v == null ? '–' : `${Math.round(v * 100)}%`)

/** How hard each team's remaining games are, next to the schedule it has played, the next ten games and back-to-backs. */
export default function ScheduleStrength({ embedded = false }) {
  const initial = new URLSearchParams(window.location.search)
  const [sort, setSort] = useState(initial.get('sort') ?? 'left')
  const [conf, setConf] = useState(initial.get('conf') ?? 'all')
  useUrlSync([['sort', sort, 'left'], ['conf', conf, 'all']])
  const [state, setState] = useState({ data: null, error: null })

  useEffect(() => {
    fetch('/api/schedule-strength')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
      .then((data) => setState({ data, error: null }))
      .catch((error) => setState({ data: null, error: error.message }))
  }, [])
  const { data, error } = state

  const rows = useMemo(() => {
    if (!data) return []
    const v = value(sort)
    return data.teams.filter((t) => conf === 'all' || t.conference?.startsWith(conf)).sort((a, b) => (v(a) ?? 99) - (v(b) ?? 99) || a.team.localeCompare(b.team))
  }, [data, sort, conf])
  const ranks = useMemo(() => (data ? difficultyRanks(data.teams, value(sort)) : {}), [data, sort])

  return (
    <PageShell embedded={embedded}>
      <header>
        {!embedded && <h1>Schedule strength</h1>}
        <p>
          How hard each team's remaining games are: the opponents' strength, in expected points against an average schedule, next to the
          schedule already played, the next ten games and how many back-to-backs are left.
        </p>
      </header>
      <div className="h2h-picks">
        <label className="h2h-pick">Rank by
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="h2h-pick">Conference
          <select value={conf} onChange={(e) => setConf(e.target.value)}>
            <option value="all">Both</option><option value="East">Eastern</option><option value="West">Western</option>
          </select>
        </label>
      </div>
      {error && <p className="status">{error}</p>}
      {!data && !error && <Skeleton />}
      {data && (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th title="Rank by the chosen column: 1 is the hardest schedule">#</th><th className="left">Team</th><th className="left">Division</th>
                  <th title="Games played">GP</th><th title="Standings points">Pts</th>
                  <th title="Chance of making the playoffs, from the playoff odds simulation">Playoffs</th>
                  <th title="Games left, split home and away">Left (H-A)</th>
                  <th title="Opponents' average expected-goal margin per game over the remaining games; positive means better opponents">Opp. margin</th>
                  <th title="Expected points over the remaining games minus what an average opponent at the same venues would give; negative is harder">Remaining</th>
                  <th title="The same for the next 10 games">Next 10</th>
                  <th title="The same for the games already played, using today's ratings">Played</th>
                  <th title="Remaining games played the night after another game">B2B left</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => {
                  const mark = extreme(ranks[t.team], data.teams.length)
                  return (
                    <tr key={t.team} className={mark ? `ss-${mark}` : undefined}>
                      <td>{ranks[t.team] ?? '–'}</td>
                      <td className="left"><TeamLogo team={t} /> <Link to={`/team/${t.team}`}>{t.team}</Link></td>
                      <td className="left">{t.division}</td>
                      <td>{t.games_played}</td><td>{t.points}</td><td>{pct(t.make_playoffs)}</td>
                      <td>{t.left.games} ({t.left.home}-{t.left.away})</td>
                      <td>{fmtNet(t.left.opp_net)}</td>
                      <td className={sort === 'left' ? 'accent' : ''}>{fmtPts(t.left.schedule_points)}</td>
                      <td className={sort === 'next' ? 'accent' : ''}>{fmtPts(t.next.schedule_points)}</td>
                      <td className={sort === 'played' ? 'accent' : ''}>{fmtPts(t.played.schedule_points)}</td>
                      <td className={sort === 'b2b' ? 'accent' : ''}>{t.back_to_backs_left}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="sub">
            Each game is priced with the same on-paper model as the What to watch page (expected-goal ratings, with home ice); a team's
            schedule figure is its expected points over those games minus what it would expect against an average opponent at the same
            venues, so negative means harder. It uses today's ratings for every opponent, pulled toward average while the sample is
            small, so the figures move as the season does.
            {' '}Right now the remaining schedule moves a team's expected points by at most{' '}
            {biggestSwing(data.teams, (r) => r.left.schedule_points).toFixed(1)} over {Math.round(data.teams.reduce((a, r) => a + r.left.games, 0) / data.teams.length)} games, and the next ten by at most{' '}
            {biggestSwing(data.teams, (r) => r.next.schedule_points).toFixed(1)}: early in a season almost every team has most of its schedule still ahead, so the spread is small and a few
            tenths of a point are noise. It becomes useful later, when one team's last 20 games are much harder than another's.
          </p>
        </>
      )}
    </PageShell>
  )
}
