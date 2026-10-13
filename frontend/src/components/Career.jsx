import { useEffect, useMemo, useState } from 'react'
import { nhlSeasons, seasonLabel } from '../career.js'
import { SeasonBars } from './Charts.jsx'

const shortSeason = (s) => `'${String(s).slice(6)}`
const dash = (v) => (v == null ? '–' : v)
const pct = (v) => (v == null || v === 0 ? '–' : `${(v * 100).toFixed(1)}`)
const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))
const dec = (v, d = 2) => (v == null ? '–' : v.toFixed(d))

function age(birthDate) {
  const b = new Date(`${birthDate}T00:00:00`)
  const now = new Date()
  let a = now.getFullYear() - b.getFullYear()
  if (now < new Date(now.getFullYear(), b.getMonth(), b.getDate())) a--
  return a
}

export default function Career({ playerId }) {
  const [result, setResult] = useState({ id: null, data: null, error: null })
  const [kind, setKind] = useState('regularSeason')
  const [allLeagues, setAllLeagues] = useState(false)

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
  const goalie = bio.is_goalie
  const current = Math.max(...annual.map((s) => s.season), 0)

  const bars = annual.map((s) => ({
    label: shortSeason(s.season),
    season: `${seasonLabel(s.season)} · ${s.teams.join(' / ')}`,
    value: goalie ? s.w : s.p,
    highlight: s.season === current && bio.is_active,
    lines: goalie ? [`${s.gp} games played`] : [`${s.gp} GP · ${s.g} G · ${s.a} A`],
  }))

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

      <div className="bio">
        {bio.headshot && <img src={bio.headshot} alt="" width="72" height="72" className="headshot" loading="lazy" />}
        <div>
          <p className="bio-line">
            {bio.sweater != null && `#${bio.sweater} · `}{bio.position}
            {bio.shoots_catches && ` · ${goalie ? 'Catches' : 'Shoots'} ${bio.shoots_catches}`}
            {bio.height_in && ` · ${Math.floor(bio.height_in / 12)}'${bio.height_in % 12}"`}
            {bio.weight_lb && `, ${bio.weight_lb} lb`}
          </p>
          <p className="bio-line muted">
            Born {new Date(`${bio.birth_date}T00:00:00`).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}
            {' '}(age {age(bio.birth_date)}) in {[bio.birth_city, bio.birth_state, bio.birth_country].filter(Boolean).join(', ')}
            {bio.draft && ` · Drafted ${bio.draft.year}, round ${bio.draft.round} (#${bio.draft.overall} overall) by ${bio.draft.team}`}
            {bio.draft === null || bio.draft === undefined ? ' · Undrafted' : ''}
          </p>
          {(bio.awards.length > 0 || !!bio.in_hhof) && (
            <ul className="awards">
              {bio.in_hhof ? <li>Hockey Hall of Fame</li> : null}
              {bio.awards.map((a) => (
                <li key={a.name} title={a.seasons.map(seasonLabel).join(', ')}>
                  {a.name}{a.seasons.length > 1 ? ` ×${a.seasons.length}` : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={kind === 'regularSeason'} className={kind === 'regularSeason' ? 'on' : ''} onClick={() => setKind('regularSeason')}>Regular season</button>
        <button role="tab" aria-selected={kind === 'playoffs'} className={kind === 'playoffs' ? 'on' : ''} onClick={() => setKind('playoffs')}>Playoffs</button>
      </div>

      {!totals ? (
        <p className="status">No {kind === 'playoffs' ? 'playoff' : 'regular-season'} games in the NHL yet.</p>
      ) : goalie ? (
        <div className="tiles">
          <Tile label="GP / GS" value={`${totals.gamesPlayed} / ${dash(totals.gamesStarted)}`} />
          <Tile label="W-L-OTL" value={`${dash(totals.wins)}-${dash(totals.losses)}-${dash(totals.otLosses)}`} />
          <Tile label="Save %" value={sv(totals.savePctg)} />
          <Tile label="GAA" value={dec(totals.goalsAgainstAvg)} />
          <Tile label="Shutouts" value={dash(totals.shutouts)} />
          <Tile label="Shots against" value={dash(totals.shotsAgainst)} />
          <Tile label="Goals against" value={dash(totals.goalsAgainst)} />
        </div>
      ) : (
        <div className="tiles">
          <Tile label="GP" value={totals.gamesPlayed} />
          <Tile label="Goals" value={totals.goals} />
          <Tile label="Assists" value={totals.assists} />
          <Tile label="Points" value={totals.points} />
          <Tile label="Points / game" value={dec(totals.points / totals.gamesPlayed)} />
          <Tile label="+/-" value={dash(totals.plusMinus)} />
          <Tile label="PIM" value={dash(totals.pim)} />
          <Tile label="PP goals" value={dash(totals.powerPlayGoals)} />
          <Tile label="PP points" value={dash(totals.powerPlayPoints)} />
          <Tile label="GW goals" value={dash(totals.gameWinningGoals)} />
          <Tile label="Shots" value={dash(totals.shots)} />
          <Tile label="Shooting %" value={pct(totals.shootingPctg)} />
          <Tile label="Avg TOI" value={dash(totals.avgToi)} />
          {kind === 'regularSeason' && bestP && <Tile label={`Best season (P) · ${seasonLabel(bestP.season)}`} value={bestP.p} />}
          {kind === 'regularSeason' && bestG && <Tile label={`Best season (G) · ${seasonLabel(bestG.season)}`} value={bestG.g} />}
        </div>
      )}

      {annual.length > 0 && kind === 'regularSeason' && (
        <SeasonBars
          title={goalie ? 'Wins by NHL season' : 'Points by NHL season'}
          rows={bars}
          valueLabel={goalie ? 'wins' : 'points'}
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
        <table>
          <thead>
            <tr>
              <th className="left">Season</th><th className="left">Team</th>
              {allLeagues && <th className="left">League</th>}
              <th>GP</th>
              {goalie ? (
                <><th>GS</th><th>W</th><th>L</th><th>OTL</th><th>SV%</th><th>GAA</th><th>SO</th></>
              ) : (
                <><th>G</th><th>A</th><th>P</th><th>+/-</th><th>PIM</th><th>PPP</th><th>GWG</th><th>S</th><th>S%</th><th>TOI</th></>
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

function Tile({ label, value }) {
  return (
    <div className="tile">
      <span>{label}</span>
      <strong>{value ?? '–'}</strong>
    </div>
  )
}
