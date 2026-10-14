import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import PlayoffOdds from '../components/PlayoffOdds.jsx'
import TeamLogo from '../components/TeamLogo.jsx'
import { fmt1, fmtPct, STABLE_GP } from '../format.js'

const VIEWS = [
  { id: 'division', label: 'Division', rank: 'division_rank', group: (t) => t.division, order: ['Atlantic', 'Metropolitan', 'Central', 'Pacific'] },
  { id: 'conference', label: 'Conference', rank: 'conference_rank', group: (t) => `${t.conference} Conference`, order: ['Eastern Conference', 'Western Conference'] },
  { id: 'league', label: 'League', rank: 'league_rank', group: () => 'League', order: ['League'] },
]

export default function Standings() {
  const [teams, setTeams] = useState(null)
  const [meta, setMeta] = useState(null)
  const [error, setError] = useState(null)
  const [viewId, setViewId] = useState('division')

  useEffect(() => {
    Promise.all([
      fetch('/api/meta').then((r) => r.json()),
      fetch('/api/teams').then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      }),
    ])
      .then(([m, t]) => {
        setMeta(m)
        setTeams(t)
      })
      .catch((e) => setError(e.message))
  }, [])

  const view = VIEWS.find((v) => v.id === viewId) ?? VIEWS[0]
  const groups = useMemo(() => {
    if (!teams) return []
    const byGroup = new Map()
    for (const t of teams) {
      const g = view.group(t)
      if (!byGroup.has(g)) byGroup.set(g, [])
      byGroup.get(g).push(t)
    }
    return view.order
      .filter((g) => byGroup.has(g))
      .map((g) => [g, byGroup.get(g).sort((a, b) => a[view.rank] - b[view.rank])])
  }, [teams, view])

  if (error) return <main><p className="status">Couldn't load standings: {error}</p></main>
  if (!teams) return <main><p className="status">Loading…</p></main>

  const games = meta.games_per_season
  const early = Math.max(...teams.map((t) => t.games_played)) < STABLE_GP

  return (
    <main>
      <header>
        <h1>Standings</h1>
        <p>
          Pace projects each team's points over {games} games (max {games * 2}).
        </p>
      </header>
      {early && viewId !== 'odds' && (
        <p className="notice">
          Early season: teams have played at most {Math.max(...teams.map((t) => t.games_played))}{' '}
          games, so pace projections are very noisy (shown dimmed).
        </p>
      )}

      <div className="tabs" role="tablist">
        {VIEWS.map((v) => (
          <button
            key={v.id}
            role="tab"
            aria-selected={v.id === viewId}
            className={v.id === viewId ? 'on' : ''}
            onClick={() => setViewId(v.id)}
          >
            {v.label}
          </button>
        ))}
        <button role="tab" aria-selected={viewId === 'odds'} className={viewId === 'odds' ? 'on' : ''} onClick={() => setViewId('odds')}>
          Playoff odds
        </button>
      </div>

      {viewId === 'odds' && <PlayoffOdds teams={teams} />}

      {viewId !== 'odds' && groups.map(([name, rows]) => (
        <section key={name} className="standings-group">
          {view.id !== 'league' && <h2>{name}</h2>}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="left">Team</th>
                  <th>GP</th><th>W</th><th>L</th><th>OTL</th><th>PTS</th><th>P%</th>
                  <th>Pace ({games})</th><th>GF</th><th>GA</th><th>Diff</th>
                  <th>PP%</th><th>PK%</th><th>L10</th><th>Strk</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.abbrev}>
                    <td className="left team-cell">
                      <span className="rank">{t[view.rank]}</span>
                      <TeamLogo team={t} />
                      <Link to={`/team/${t.abbrev}`}>{t.name}</Link>
                    </td>
                    <td>{t.games_played}</td><td>{t.wins}</td><td>{t.losses}</td>
                    <td>{t.ot_losses}</td><td><strong>{t.points}</strong></td>
                    <td>{t.point_pct == null ? '–' : t.point_pct.toFixed(3).replace(/^0/, '')}</td>
                    <td className={'accent' + (t.games_played < STABLE_GP ? ' low' : '')}>
                      {fmt1(t.points_pace)}
                    </td>
                    <td>{t.goals_for}</td><td>{t.goals_against}</td>
                    <td>{t.goal_diff > 0 ? `+${t.goal_diff}` : t.goal_diff}</td>
                    <td>{fmtPct(t.pp_pct)}</td><td>{fmtPct(t.pk_pct)}</td>
                    <td>{t.l10_wins}-{t.l10_losses}-{t.l10_ot_losses}</td>
                    <td>{t.streak_code}{t.streak_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </main>
  )
}
