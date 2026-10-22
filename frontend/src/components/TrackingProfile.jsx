import { useEffect, useState } from 'react'
import { seasonLabel } from '../career.js'
import { describe } from '../glossary.js'

const ordinal = (n) => {
  const v = n % 100
  if (v >= 11 && v <= 13) return `${n}th`
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`
}
const n1 = (v) => (v == null ? '–' : v.toFixed(1))
const pct1 = (v) => (v == null ? '–' : `${(v * 100).toFixed(1)}%`)
const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))
const dateText = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : null)
const pctile = (p) => (p == null ? null : `${ordinal(Math.min(99, Math.max(1, Math.round(p * 100))))} percentile`)

function Card({ label, value, unit, percentile, note }) {
  return (
    <div className="tile">
      <span>{label}</span>
      <strong>{value}{value !== '–' && unit ? <small> {unit}</small> : null}</strong>
      {percentile != null && <small className="muted">{pctile(percentile)}</small>}
      {note && <small className="muted">{note}</small>}
    </div>
  )
}

/**
 * NHL EDGE tracking stats for one player, season by season: a skater's speeds, shot speeds, distance and
 * zone time, or a goalie's save percentage by shot range. Percentiles are the NHL's, among tracked players.
 */
export default function TrackingProfile({ playerId }) {
  const [state, setState] = useState({ id: null, data: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/players/${playerId}/tracking`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setState({ id: playerId, data }))
      .catch(() => !ignore && setState({ id: playerId, data: null }))
    return () => { ignore = true }
  }, [playerId])

  const data = state.id === playerId ? state.data : null
  if (!data || data.seasons.length === 0) return null
  const all = data.seasons
  const [latest] = all

  if (data.kind === 'goalie') {
    return (
      <section>
        <h2>Save % by shot range</h2>
        <p className="sub">
          From the NHL's puck and player tracking ({seasonLabel(latest.season_id)}). High-danger shots come from the slot and
          crease, mid-range from the circles and faceoff dots, long-range from the perimeter. Percentiles compare with other
          goalies.
        </p>
        <section className="tiles">
          <Card label="High-danger SV%" value={sv(latest.sv_high)} percentile={latest.sv_high_pctile} note={`${latest.saves_high}–${latest.ga_high} (saves–goals)`} />
          <Card label="Mid-range SV%" value={sv(latest.sv_mid)} percentile={latest.sv_mid_pctile} note={`${latest.saves_mid}–${latest.ga_mid}`} />
          <Card label="Long-range SV%" value={sv(latest.sv_long)} percentile={latest.sv_long_pctile} note={`${latest.saves_long}–${latest.ga_long}`} />
          <Card label="Games above .900" value={pct1(latest.games_above_900)} percentile={latest.games_above_900_pctile} />
        </section>
        {all.length > 1 && (
          <div className="table-wrap">
            <table>
              <thead><tr><th className="left">Season</th><th title={describe('SV%')}>SV%</th><th title={describe('High')}>High</th><th title={describe('Mid')}>Mid</th><th title={describe('Long')}>Long</th><th title={describe('Games > .900')}>Games &gt; .900</th></tr></thead>
              <tbody>
                {all.map((s) => (
                  <tr key={s.season_id}>
                    <td className="left">{seasonLabel(s.season_id)}</td><td>{sv(s.sv_all)}</td><td>{sv(s.sv_high)}</td>
                    <td>{sv(s.sv_mid)}</td><td>{sv(s.sv_long)}</td><td>{pct1(s.games_above_900)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    )
  }

  const perGame = (s) => (s.games_played ? s.distance_miles / s.games_played : null)
  return (
    <section>
      <h2>Speed &amp; tracking</h2>
      <p className="sub">
        From the NHL's puck and player tracking, {seasonLabel(latest.season_id)}. Percentiles compare with other tracked
        skaters. Tracking starts in 2021-22.
      </p>
      <section className="tiles">
        <Card label="Top skating speed" value={n1(latest.top_speed_mph)} unit="mph" percentile={latest.top_speed_pctile}
          note={latest.top_speed_date ? `set ${dateText(latest.top_speed_date)}` : null} />
        <Card label="Hardest shot" value={n1(latest.top_shot_mph)} unit="mph" percentile={latest.top_shot_pctile}
          note={latest.top_shot_date ? `set ${dateText(latest.top_shot_date)}` : null} />
        <Card label="Average shot speed" value={n1(latest.avg_shot_mph)} unit="mph" percentile={latest.avg_shot_pctile} />
        <Card label="Bursts over 22 mph" value={latest.bursts_22_plus ?? '–'} percentile={latest.bursts_22_pctile} />
        <Card label="Distance per game" value={perGame(latest) == null ? '–' : perGame(latest).toFixed(2)} unit="mi" percentile={latest.distance_pctile} />
        <Card label="Offensive-zone time" value={pct1(latest.oz_pct)} percentile={latest.oz_pctile} note={`defensive zone ${pct1(latest.dz_pct)}`} />
      </section>
      {(
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="left">Season</th><th title={describe('GP')}>GP</th><th title={describe('Top speed')}>Top speed</th><th title={describe('22+ bursts')}>22+ bursts</th><th title={describe('Hardest shot')}>Hardest shot</th>
                <th title={describe('Avg shot')}>Avg shot</th><th title="Shot attempts of any kind at 90 mph or harder">90+ mph attempts</th><th title={describe('Miles / GP')}>Miles / GP</th><th title={describe('OZ %')}>OZ %</th><th title={describe('DZ %')}>DZ %</th>
              </tr>
            </thead>
            <tbody>
              {all.map((s) => (
                <tr key={s.season_id}>
                  <td className="left">{seasonLabel(s.season_id)}</td><td>{s.games_played ?? '–'}</td>
                  <td>{n1(s.top_speed_mph)}</td><td>{s.bursts_22_plus ?? '–'}</td>
                  <td>{n1(s.top_shot_mph)}</td><td>{n1(s.avg_shot_mph)}</td>
                  <td>{s.shots_90_100 == null ? '–' : (s.shots_90_100 ?? 0) + (s.shots_100_plus ?? 0)}</td>
                  <td>{perGame(s) == null ? '–' : perGame(s).toFixed(2)}</td><td>{pct1(s.oz_pct)}</td><td>{pct1(s.dz_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
