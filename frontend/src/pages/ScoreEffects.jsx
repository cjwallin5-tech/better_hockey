import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import TeamLogo from '../components/TeamLogo.jsx'
import { useUrlSync } from '../urlState.js'
import { STATE_LABEL, adjustment, pct1, signedPts } from '../scoreState.js'
import { seasonLabel } from '../career.js'
import { Skeleton } from '../components/Skeleton.jsx'

const SORTS = [
  ['xg_pct_adj', 'Score-adjusted xG share'], ['xg_pct', 'Raw xG share'], ['att_pct_adj', 'Score-adjusted shot-attempt share'],
  ['change', 'Biggest adjustment'],
]

/** How the score changes play, league-wide, and every team's xG share with the score effect taken out. */
export default function ScoreEffects() {
  const initial = new URLSearchParams(window.location.search)
  const [season, setSeason] = useState(initial.get('season') ?? 'current')
  const [sort, setSort] = useState(initial.get('sort') ?? 'xg_pct_adj')
  useUrlSync([['season', season, 'current'], ['sort', sort, 'xg_pct_adj']])
  const [state, setState] = useState({ season: null, data: null, error: null })

  useEffect(() => {
    let ignore = false
    fetch(`/api/score-effects?season=${season}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
      .then((data) => !ignore && setState({ season, data, error: null }))
      .catch((error) => !ignore && setState({ season, data: null, error: error.message }))
    return () => { ignore = true }
  }, [season])
  const { data, error } = state.season === season ? state : { data: null, error: null }

  const rows = useMemo(() => {
    if (!data) return []
    const value = (t) => (sort === 'change' ? Math.abs(adjustment(t) ?? 0) : t[sort] ?? -Infinity)
    return [...data.teams].sort((a, b) => value(b) - value(a) || a.team.localeCompare(b.team))
  }, [data, sort])

  return (
    <main>
      <header>
        <h1>Score effects</h1>
        <p>
          Teams that trail shoot more and teams that lead sit back, so a team that spent the season ahead looks worse by raw shot
          share than it is. This page shows the effect and every team's expected-goal share with it taken out.
        </p>
      </header>

      {error && <p className="status">{error}</p>}
      {!data && !error && <Skeleton />}
      {data && (
        <>
          <h2>What the score does to play</h2>
          <p className="sub">
            Even-strength shots in the three regulation periods, {data.available.length} season{data.available.length === 1 ? '' : 's'} pooled
            ({data.available.map(seasonLabel).join(', ')}). Each row is the share of shots, expected goals and goals going to the team in
            that situation, so 50% means no effect.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="left">Team is</th><th title="Share of all shots taken in this state">Time in state</th>
                  <th title="Share of shot attempts (on goal and missed) taken by the team in this state">Shot attempts</th>
                  <th title="Share of expected goals created by the team in this state">xG</th>
                  <th title="Share of the goals scored by the team in this state">Goals</th>
                </tr>
              </thead>
              <tbody>
                {data.effects_all.map((e) => (
                  <tr key={e.state}>
                    <td className="left">{STATE_LABEL[e.state]}</td>
                    <td>{pct1(e.pct_of_attempts)}</td>
                    <td className="accent">{pct1(e.att_share)}</td>
                    <td className="accent">{pct1(e.xg_share)}</td>
                    <td>{pct1(e.goal_share)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="sub">
            The trailing team takes the bigger share of shot attempts and the leading team the smaller, which is why raw shot counts
            reward teams that played from behind. The effect is weaker in expected goals (trailing teams take more but lower-quality
            shots) and almost gone in goals: the team that is ahead or behind scores about half of the goals either way.
          </p>

          <h2>Teams, with the score effect taken out</h2>
          <div className="h2h-picks">
            <label className="h2h-pick">Season
              <select value={season} onChange={(e) => setSeason(e.target.value)}>
                <option value="current">This season</option>
                {data.available.filter((s) => String(s) !== String(data.available[data.available.length - 1])).reverse().map((s) => (
                  <option key={s} value={s}>{seasonLabel(s)}</option>
                ))}
                {data.available.length > 1 && <option value="all">All seasons together</option>}
              </select>
            </label>
            <label className="h2h-pick">Rank by
              <select value={sort} onChange={(e) => setSort(e.target.value)}>
                {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th><th className="left">Team</th>
                  <th title="Share of expected goals while the game is on, as played">xGF%</th>
                  <th title="The same share with each score state weighted so the league sits at 50% in all of them">Adj. xGF%</th>
                  <th title="Adjusted minus raw, in percentage points: positive means the team looks better once the score effect is removed">Change</th>
                  <th title="Share of shot attempts, as played">Shot%</th>
                  <th title="Share of shot attempts with the score effect removed">Adj. shot%</th>
                  <th title="Expected-goal share while trailing">Trailing</th><th title="Expected-goal share while tied">Tied</th>
                  <th title="Expected-goal share while leading">Leading</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((t, i) => {
                  const d = adjustment(t)
                  return (
                    <tr key={t.team}>
                      <td>{i + 1}</td>
                      <td className="left"><TeamLogo team={t} /> <Link to={`/team/${t.team}`}>{t.team}</Link></td>
                      <td>{pct1(t.xg_pct)}</td><td className="accent">{pct1(t.xg_pct_adj)}</td><td>{signedPts(d)}</td>
                      <td>{pct1(t.att_pct)}</td><td>{pct1(t.att_pct_adj)}</td>
                      <td>{pct1(t.by_state.trailing.xg_pct)}</td><td>{pct1(t.by_state.tied.xg_pct)}</td><td>{pct1(t.by_state.leading.xg_pct)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="sub">
            Adjusted shares re-weight each team's shots and its opponents' by score state so that the league sits at exactly 50% in
            every state; the effect itself is measured on every season shown above. {data.teams.length > 0 && (
              <>It moves a team's xG share by at most {(Math.max(...data.teams.map((t) => Math.abs(adjustment(t) ?? 0))) * 100).toFixed(1)} points
              and its shot-attempt share by at most {(Math.max(...data.teams.map((t) => Math.abs(adjustment(t, 'att') ?? 0))) * 100).toFixed(1)}, so
              it mostly confirms the raw ranking rather than changing it. </>
            )}A team's trailing and leading columns are noisy early in a season, since each rests on a few hundred shots.
          </p>
        </>
      )}
    </main>
  )
}
