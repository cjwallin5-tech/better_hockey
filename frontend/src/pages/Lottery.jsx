import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import TeamLogo from '../components/TeamLogo.jsx'
import { useUrlSync } from '../urlState.js'
import { SORTS, chance, ordinal, shade, visibleTeams } from '../lotteryView.js'
import { Skeleton } from '../components/Skeleton.jsx'

const SORT_LABELS = [
  ['first_overall', 'Chance of the first pick'], ['worst_record', 'Chance of the worst record'], ['top_two', 'Chance of a top-two pick'],
  ['points', 'Fewest points now'], ['expected_pick', 'Expected pick'],
]

/** The draft lottery: each team's chance of missing the playoffs, finishing last, and of every pick from first to sixteenth. */
export default function Lottery() {
  const initial = new URLSearchParams(window.location.search)
  const [sort, setSort] = useState(initial.get('sort') ?? 'first_overall')
  const [all, setAll] = useState(initial.get('all') === '1')
  useUrlSync([['sort', sort, 'first_overall'], ['all', all ? '1' : '', '']])
  const [state, setState] = useState({ data: null, error: null })

  useEffect(() => {
    fetch('/api/lottery')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
      .then((data) => setState({ data, error: null }))
      .catch((error) => setState({ data: null, error: error.message }))
  }, [])
  const { data, error } = state

  const rows = useMemo(() => {
    if (!data) return []
    const key = SORTS[sort]
    return visibleTeams(data.teams, all).sort((a, b) => key(a) - key(b) || a.team.localeCompare(b.team))
  }, [data, sort, all])

  return (
    <main>
      <header>
        <h1>Draft lottery</h1>
        <p>
          Every team's chance of missing the playoffs, of finishing with the worst record, and of each pick in the first round, from
          playing out the rest of the season thousands of times and then running the NHL's lottery on each ending. Mostly a spring
          page: this early the table is wide open.
        </p>
      </header>
      {error && <p className="status">{error}</p>}
      {!data && !error && <Skeleton />}
      {data && (
        <>
          <div className="h2h-picks">
            <label className="h2h-pick">Rank by
              <select value={sort} onChange={(e) => setSort(e.target.value)}>
                {SORT_LABELS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label className="inline-check"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> Show every team</label>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th><th className="left">Team</th><th title="Games played">GP</th><th title="Standings points">Pts</th>
                  <th title="Expected points at the end of the season, with the range that 80% of simulations fall in">Final pts</th>
                  <th title="Chance of missing the playoffs, which puts the team in the lottery">In lottery</th>
                  <th title="Chance of finishing with the fewest points of the teams that miss the playoffs, the best lottery odds">Worst record</th>
                  <th title="Chance of winning the first overall pick, after the NHL's lottery rules">1st pick</th>
                  <th title="Chance of a first or second overall pick">Top 2</th>
                  <th title="Chance of a pick from first to fifth">Top 5</th>
                  <th title="Average pick over the simulations in which the team is in the lottery">Exp. pick</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((t, i) => (
                  <tr key={t.team}>
                    <td>{i + 1}</td>
                    <td className="left"><TeamLogo team={t} /> <Link to={`/team/${t.team}`}>{t.team}</Link></td>
                    <td>{t.games_played}</td><td>{t.points}</td>
                    <td>{Math.round(t.exp_points)} <span className="muted">({Math.round(t.p10_points)}-{Math.round(t.p90_points)})</span></td>
                    <td>{chance(t.in_lottery) || '0%'}</td>
                    <td className={sort === 'worst_record' ? 'accent' : ''}>{chance(t.worst_record)}</td>
                    <td className={sort === 'first_overall' ? 'accent' : ''}>{chance(t.first_overall, t.first_overall < 0.1 ? 1 : 0)}</td>
                    <td className={sort === 'top_two' ? 'accent' : ''}>{chance(t.top_two)}</td>
                    <td>{chance(t.top_five)}</td>
                    <td>{t.expected_pick == null ? '–' : t.expected_pick.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2>Chance of each pick</h2>
          <p className="sub">
            Each row is a team's chance of picking at each spot in the first round (blank under 0.5%). The picks in a row add up to the
            team's chance of being in the lottery; a playoff team's pick is not decided by the lottery and isn't shown here.
          </p>
          <div className="table-wrap">
            <table className="heat">
              <thead>
                <tr><th className="left">Team</th>{Array.from({ length: 16 }, (_, k) => <th key={k} title={`${ordinal(k + 1)} overall`}>{k + 1}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.team}>
                    <td className="left"><TeamLogo team={t} /> {t.team}</td>
                    {t.picks.map((p, k) => (
                      <td key={k} style={shade(p) ? { background: `color-mix(in srgb, var(--series-1) ${shade(p)}%, transparent)` } : undefined}>
                        {chance(p)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2>How the lottery works</h2>
          <p className="sub">
            The 16 teams that miss the playoffs are seeded by points, fewest first, and two drawings are held: the first for the first overall
            pick, the second for the second. A team can move up at most 10 spots, so only the 11 worst records can win first overall; a team
            from 12th to 16th that wins a drawing moves up as far as the cap allows and the worst team keeps the first pick. Everyone else
            keeps their order. These are the NHL's published odds.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th title="Lottery seed: 1 is the fewest points of the 16 teams that miss the playoffs">Seed</th>
                  <th title="Chance of winning the first drawing">1st draw</th>
                  <th title="Chance of the first overall pick once the 10-spot limit is applied">1st pick</th>
                  <th title="Chance of a first or second overall pick">Top 2</th>
                  <th title="The worst pick the seed can fall to">Worst pick</th>
                </tr>
              </thead>
              <tbody>
                {data.seeds.map((s) => (
                  <tr key={s.seed}>
                    <td>{s.seed}</td><td>{chance(s.first_draw, 1)}</td><td>{chance(s.first_overall, 1) || '0%'}</td>
                    <td>{chance(s.top_two, 1) || '0%'}</td><td>{ordinal(s.worst_pick)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="sub">
            Not modelled: who owns each pick (a traded or conditional pick changes who drafts there), and the NHL's limit on a team moving up in the
            lottery more than twice in five years. The rules are the NHL's 2026 ones; check its guide for any change before next spring. Who is in the
            class is on the <Link to="/prospects">Prospects</Link> page.
          </p>
        </>
      )}
    </main>
  )
}
