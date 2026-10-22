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
    .sort((a, b) => b.season - a.season)

  const hasNonNhl = seasons.some((s) => s.leagueAbbrev !== 'NHL')

  return (
    <section>
      <h2>Career</h2>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={kind === 'regularSeason'} className={kind === 'regularSeason' ? 'on' : ''} onClick={() => setKind('regularSeason')}>Regular season</button>
        <button role="tab" aria-selected={kind === 'playoffs'} className={kind === 'playoffs' ? 'on' : ''} onClick={() => setKind('playoffs')}>Playoffs</button>
      </div>

      {!totals ? (
        <p className="status">No {kind === 'playoffs' ? 'playoff' : 'regular-season'} games in the NHL yet.</p>
      ) : goalie ? (
        <div className="tiles">
          <Tile label="GP / GS" value={`${totals.gamesPlayed} / ${dash(totals.gamesStarted)}`} rank={rank('games_played')} />
          <Tile label="W-L-OTL" value={`${dash(totals.wins)}-${dash(totals.losses)}-${dash(totals.otLosses)}`} rank={rank('wins')} />
          <Tile label="Save %" value={sv(totals.savePctg)} rank={rank('save_pct')} />
          <Tile label="GAA" value={dec(totals.goalsAgainstAvg)} rank={rank('gaa')} />
          <Tile label="Shutouts" value={dash(totals.shutouts)} rank={rank('shutouts')} />
          <Tile label="Shots against" value={dash(totals.shotsAgainst)} />
          <Tile label="Goals against" value={dash(totals.goalsAgainst)} />
        </div>
      ) : (
        <div className="tiles">
          <Tile label="GP" value={totals.gamesPlayed} rank={rank('games_played')} />
          <Tile label="Goals" value={totals.goals} rank={rank('goals')} />
          <Tile label="Assists" value={totals.assists} rank={rank('assists')} />
          <Tile label="Points" value={totals.points} rank={rank('points')} />
          <Tile label="Points / game" value={dec(totals.points / totals.gamesPlayed)} rank={rank('points_per_game')} />
          <Tile label="+/-" value={dash(totals.plusMinus)} rank={rank('plus_minus')} />
          <Tile label="PIM" value={dash(totals.pim)} rank={rank('pim')} />
          <Tile label="PP goals" value={dash(totals.powerPlayGoals)} rank={rank('pp_goals')} />
          <Tile label="PP points" value={dash(totals.powerPlayPoints)} />
          <Tile label="GW goals" value={dash(totals.gameWinningGoals)} rank={rank('game_winning_goals')} />
          <Tile label="Shots" value={dash(totals.shots)} rank={rank('shots')} />
          <Tile label="Shooting %" value={pct(totals.shootingPctg)} />
          <Tile label="Avg TOI" value={dash(totals.avgToi)} />
          {kind === 'regularSeason' && bestP && <Tile label={`Best season (P) · ${seasonLabel(bestP.season)}`} value={bestP.p} />}
          {kind === 'regularSeason' && bestG && <Tile label={`Best season (G) · ${seasonLabel(bestG.season)}`} value={bestG.g} />}
        </div>
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
        <table>
          <thead>
            <tr>
              <th className="left">Season</th><th className="left" title={describe('Team')}>Team</th>
              {allLeagues && <th className="left">League</th>}
              <th title={describe('GP')}>GP</th>
              {goalie ? (
                <><th title={describe('GS')}>GS</th><th title={describe('W')}>W</th><th title={describe('L')}>L</th><th title={describe('OTL')}>OTL</th><th title={describe('SV%')}>SV%</th><th title={describe('GAA')}>GAA</th><th title={describe('SO')}>SO</th></>
              ) : (
                <><th title={describe('G')}>G</th><th title={describe('A')}>A</th><th title={describe('P')}>P</th><th title={describe('+/-')}>+/-</th><th title={describe('PIM')}>PIM</th><th title={describe('PPP')}>PPP</th><th title={describe('GWG')}>GWG</th><th title={describe('S')}>S</th><th title={describe('S%')}>S%</th><th title={describe('TOI')}>TOI</th></>
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
                  <><td>{s.goals}</td><td>{s.assists}</td><td>{s.points}</td><td>{dash(s.plusMinus)}</td><td>{dash(s.pim)}</td><td>{dash(s.powerPlayPoints)}</td><td>{dash(s.gameWinningGoals)}</td><td>{dash(s.shots)}</td><td>{pct(s.shootingPctg)}</td><td>{dash(s.avgToi)}</td></>
                )}
              </tr>
            ))}
            {rows.length === 0 && <tr><td className="left" colSpan="14">No seasons to show.</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function Tile({ label, value, rank }) {
  return (
    <div className="tile">
      <span>{label}</span>
      <strong>{value ?? '–'}</strong>
      {rank && <small className="tile-rank">{rank}</small>}
    </div>
  )
}
