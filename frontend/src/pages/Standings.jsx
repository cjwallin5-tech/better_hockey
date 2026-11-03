import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import PlayoffOdds from '../components/PlayoffOdds.jsx'
import TeamLogo from '../components/TeamLogo.jsx'
import { fmt1, fmtPct, STABLE_GP } from '../format.js'
import { describe } from '../glossary.js'
import PageSkeleton from '../components/Skeleton.jsx'
import { teamColor } from '../teamColors.js'

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
  const [more, setMore] = useState(false) // every column, not just the essentials

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
  if (!teams) return <main><PageSkeleton /></main>

  const games = meta.games_per_season
  const early = Math.max(...teams.map((t) => t.games_played)) < STABLE_GP

  return (
    <main>
      <header>
        <h1>Standings</h1>
        <p>
          Pace projects each team's points over {games} games (max {games * 2}). A dot marks a team in a playoff position:
          the top three in its division, plus two wild cards in each conference.
        </p>
      </header>
      {early && viewId !== 'odds' && (
        <p className="notice">
          Early season: teams have played at most {Math.max(...teams.map((t) => t.games_played))}{' '}
          games, so pace projections are very noisy (shown dimmed).
        </p>
      )}

      <div className="tabs standings-tabs" role="tablist">
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
        {viewId !== 'odds' && (
          <button type="button" className="more-cols" aria-pressed={more} onClick={() => setMore(!more)}>
            {more ? 'Fewer stats' : 'More stats'}
          </button>
        )}
      </div>

      {viewId === 'odds' && <PlayoffOdds teams={teams} />}

      {viewId !== 'odds' && groups.map(([name, rows]) => (
        <section key={name} className="standings-group">
          {view.id !== 'league' && <div className="eyebrow">{name}</div>}
          <div className="table-wrap fit">
            <table className="standings-table">
              <colgroup>
                <col className="col-team" />
                {Array.from({ length: more ? 14 : 9 }, (_, i) => <col key={i} />)}
              </colgroup>
              <thead>
                <tr>
                  <th className="left" title={describe('Team')}>Team</th>
                  <th title={describe('GP')}>GP</th><th title={describe('W')}>W</th><th title={describe('L')}>L</th><th title={describe('OTL')}>OTL</th><th title={describe('PTS')}>PTS</th>
                  {more && <th title={describe('P%')}>P%</th>}
                  <th title={`Points pace over ${games} games`}>Pace</th>
                  {more && <><th title={describe('GF')}>GF</th><th title={describe('GA')}>GA</th></>}
                  <th title={describe('Diff')}>Diff</th>
                  {more && <><th title={describe('PP%')}>PP%</th><th title={describe('PK%')}>PK%</th></>}
                  <th title={describe('L10')}>L10</th><th title={describe('Strk')}>Strk</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => {
                  const wildCard = t.wildcard_rank === 1 || t.wildcard_rank === 2
                  const inPlayoffs = t.division_rank <= 3 || wildCard
                  return (
                    <tr key={t.abbrev} style={{ '--team': teamColor(t.abbrev) }}>
                      <td className="left team-cell">
                        <div className="team-inner">
                          <span className={`po-dot${inPlayoffs ? ' in' : ''}`} title={inPlayoffs ? 'In a playoff position' : undefined} />
                          <span className="rank">{t[view.rank]}</span>
                          <TeamLogo team={t} />
                          <Link to={`/team/${t.abbrev}`}>{t.name}</Link>
                          {wildCard && <span className="badge wc" title={`Wild card ${t.wildcard_rank}`}>WC{t.wildcard_rank}</span>}
                        </div>
                      </td>
                      <td>{t.games_played}</td><td>{t.wins}</td><td>{t.losses}</td>
                      <td>{t.ot_losses}</td><td><strong>{t.points}</strong></td>
                      {more && <td>{t.point_pct == null ? '–' : t.point_pct.toFixed(3).replace(/^0/, '')}</td>}
                      <td className={'accent' + (t.games_played < STABLE_GP ? ' low' : '')}>
                        {fmt1(t.points_pace)}
                      </td>
                      {more && <><td>{t.goals_for}</td><td>{t.goals_against}</td></>}
                      <td>{t.goal_diff > 0 ? `+${t.goal_diff}` : t.goal_diff}</td>
                      {more && <><td>{fmtPct(t.pp_pct)}</td><td>{fmtPct(t.pk_pct)}</td></>}
                      <td>{t.l10_wins}-{t.l10_losses}-{t.l10_ot_losses}</td>
                      <td>{t.streak_code}{t.streak_count}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </main>
  )
}
