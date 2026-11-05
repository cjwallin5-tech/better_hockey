import { useEffect, useMemo, useState } from 'react'
import { nhlSeasons, seasonLabel } from '../career.js'
import { rankNote, useRankings } from './Rankings.jsx'
import { describe } from '../glossary.js'

const dash = (v) => (v == null ? '–' : v)
const pct = (v) => (v == null || v === 0 ? '–' : `${(v * 100).toFixed(1)}`)
const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))
const dec = (v, d = 2) => (v == null ? '–' : v.toFixed(d))

export default function Career({ playerId }) {
  const [result, setResult] = useState({ id: null, data: null, error: null })
  const [kind, setKind] = useState('regularSeason')
  const [allLeagues, setAllLeagues] = useState(false)
  const ranks = useRankings(playerId)

  useEffect(() => {
    fetch(`/api/players/${playerId}/career`)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `API returned ${r.status}`)
        return r.json()
      })
      .then((data) => setResult({ id: playerId, data, error: null }))
      .catch((error) => setResult({ id: playerId, data: null, error: error.message }))
  }, [playerId])

  const { data, error } = result.id === playerId ? result : { data: null, error: null }
  const annual = useMemo(() => (data ? nhlSeasons(data.seasons) : []), [data])

  if (error) return <section><h2>Career</h2><p className="status">Couldn't load career stats: {error}</p></section>
  if (!data) return <section><h2>Career</h2><p className="status">Loading career stats…</p></section>

  const { bio, career, seasons } = data
  const totals = career[kind]
  const rank = (stat) => rankNote(ranks?.alltime?.[kind === 'playoffs' ? 'playoffs' : 'regular']?.[stat], 'alltime')
  const goalie = bio.is_goalie

  const best = (key) =>
    annual.length ? annual.reduce((b, s) => (s[key] > b[key] ? s : b), annual[0]) : null
  const bestP = best('p')
  const bestG = best('g')

  const rows = seasons
    .filter((s) => s.gameTypeId === (kind === 'regularSeason' ? 2 : 3) && (allLeagues || s.leagueAbbrev === 'NHL'))
    // Newest first all the way down: within a season (mid-year trade) the most recent team comes first too.
    .sort((a, b) => b.season - a.season || (b.sequence ?? 0) - (a.sequence ?? 0))

  const hasNonNhl = seasons.some((s) => s.leagueAbbrev !== 'NHL')
  // hits, blocks, takeaways and giveaways are stored for regular seasons only, and not for goalies
  const tracking = !goalie && kind === 'regularSeason' && Object.keys(data.tracked ?? {}).length > 0

  return (
    <section>
      <div className="section-head">
        <h2>Career</h2>
        <div className="subtabs" role="tablist">
          <button role="tab" aria-selected={kind === 'regularSeason'} className={kind === 'regularSeason' ? 'on' : ''} onClick={() => setKind('regularSeason')}>Regular season</button>
          <button role="tab" aria-selected={kind === 'playoffs'} className={kind === 'playoffs' ? 'on' : ''} onClick={() => setKind('playoffs')}>Playoffs</button>
        </div>
      </div>

      {!totals ? (
        <p className="status">No {kind === 'playoffs' ? 'playoff' : 'regular-season'} games in the NHL yet.</p>
      ) : goalie ? (
        <CareerSummary
          key={kind}
          main={[
            ['GP / GS', `${totals.gamesPlayed} / ${dash(totals.gamesStarted)}`, rank('games_played')],
            ['W-L-OTL', `${dash(totals.wins)}-${dash(totals.losses)}-${dash(totals.otLosses)}`, rank('wins')],
            ['Save %', sv(totals.savePctg), rank('save_pct')],
            ['GAA', dec(totals.goalsAgainstAvg), rank('gaa')],
            ['Shutouts', dash(totals.shutouts), rank('shutouts')],
          ]}
          more={[
            ['Shots against', dash(totals.shotsAgainst)],
            ['Goals against', dash(totals.goalsAgainst)],
          ]}
        />
      ) : (
        <CareerSummary
          key={kind}
          main={[
            ['GP', totals.gamesPlayed, rank('games_played')],
            ['Goals', totals.goals, rank('goals')],
            ['Assists', totals.assists, rank('assists')],
            ['Points', totals.points, rank('points')],
            ['Points / game', dec(totals.points / totals.gamesPlayed), rank('points_per_game')],
          ]}
          more={[
            ['+/-', dash(totals.plusMinus), rank('plus_minus')],
            ['PIM', dash(totals.pim), rank('pim')],
            ['PP goals', dash(totals.powerPlayGoals), rank('pp_goals')],
            ['PP points', dash(totals.powerPlayPoints)],
            ['GW goals', dash(totals.gameWinningGoals), rank('game_winning_goals')],
            ['Shots', dash(totals.shots), rank('shots')],
            ['Shooting %', pct(totals.shootingPctg)],
            ['Avg TOI', dash(totals.avgToi)],
            ...(kind === 'regularSeason' && bestP ? [[`Most points (${seasonLabel(bestP.season)})`, bestP.p]] : []),
            ...(kind === 'regularSeason' && bestG ? [[`Most goals (${seasonLabel(bestG.season)})`, bestG.g]] : []),
          ]}
        />
      )}

      <h3 className="career-table-title">
        Season by season
        {hasNonNhl && (
          <label className="inline-check">
            <input type="checkbox" checked={allLeagues} onChange={(e) => setAllLeagues(e.target.checked)} />
            include junior, minor and international
          </label>
        )}
      </h3>
      <div className="table-wrap">
        <table className={tracking ? 'career-tight' : undefined}>
          <thead>
            <tr>
              <th className="left">Season</th><th className="left" title={describe('Team')}>Team</th>
              {allLeagues && <th className="left">League</th>}
              <th title={describe('GP')}>GP</th>
              {goalie ? (
                <><th title={describe('GS')}>GS</th><th title={describe('W')}>W</th><th title={describe('L')}>L</th><th title={describe('OTL')}>OTL</th><th title={describe('SV%')}>SV%</th><th title={describe('GAA')}>GAA</th><th title={describe('SO')}>SO</th></>
              ) : (
                <><th title={describe('G')}>G</th><th title={describe('A')}>A</th><th title={describe('P')}>P</th><th title={describe('+/-')}>+/-</th><th title={describe('PIM')}>PIM</th><th title={describe('PPP')}>PPP</th><th title={describe('GWG')}>GWG</th><th title={describe('S')}>S</th><th title={describe('S%')}>S%</th><th title={describe('TOI')}>TOI</th>{tracking && <><th title={describe('Hits')}>H</th><th title={describe('BLK')}>BLK</th><th title={describe('TK')}>TK</th><th title={describe('GV')}>GV</th></>}</>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={`${s.season}-${s.sequence}-${s.leagueAbbrev}-${s.team}`}>
                <td className="left">{seasonLabel(s.season)}</td>
                <td className="left">{s.team}</td>
                {allLeagues && <td className="left">{s.leagueAbbrev}</td>}
                <td>{s.gamesPlayed}</td>
                {goalie ? (
                  <><td>{dash(s.gamesStarted)}</td><td>{dash(s.wins)}</td><td>{dash(s.losses)}</td><td>{dash(s.otLosses)}</td><td>{sv(s.savePctg)}</td><td>{dec(s.goalsAgainstAvg)}</td><td>{dash(s.shutouts)}</td></>
                ) : (
                  <><td>{s.goals}</td><td>{s.assists}</td><td>{s.points}</td><td>{dash(s.plusMinus)}</td><td>{dash(s.pim)}</td><td>{dash(s.powerPlayPoints)}</td><td>{dash(s.gameWinningGoals)}</td><td>{dash(s.shots)}</td><td>{pct(s.shootingPctg)}</td><td>{dash(s.avgToi)}</td>{tracking && <TrackedCells t={s.leagueAbbrev === 'NHL' ? data.tracked?.[s.season] : null} split={rows.filter((r) => r.season === s.season && r.leagueAbbrev === 'NHL').length > 1} />}</>
                )}
              </tr>
            ))}
            {rows.length === 0 && <tr><td className="left" colSpan="18">No seasons to show.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  )
}

/** Hits, blocks, takeaways and giveaways for one season row (empty dashes when the season is not tracked or is not an NHL one). A season's counts
 *  cover every team he played for, so on a traded player's team rows they are greyed and say so. */
function TrackedCells({ t, split }) {
  const cell = (v) => <td className={split ? 'muted' : ''} title={split ? 'Whole-season total, all teams' : undefined}>{dash(v)}</td>
  return <>{cell(t?.hits)}{cell(t?.blocks)}{cell(t?.takeaways)}{cell(t?.giveaways)}</>
}

/** The career totals as one card: the few numbers that matter large, with their all-time rank, and the rest as a quiet list. */
export function CareerSummary({ main, more }) {
  return (
    <div className="card career-summary">
      <dl className="career-key">
        {main.map(([label, value, rank]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value ?? '–'}</dd>
            {rank && <small>{rank}</small>}
          </div>
        ))}
      </dl>
      {more.length > 0 && (
        <dl className="career-more">
          {more.map(([label, value, rank]) => (
            <div key={label} title={rank}>
              <dt>{label}</dt>
              <dd>{value ?? '–'}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}
