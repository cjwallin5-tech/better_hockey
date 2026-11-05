import { useEffect, useState } from 'react'
import { factorPct } from '../nhle.js'

/** How NHLe works, and the league factors behind it. Collapsed by default. */
export default function NhleFactors() {
  const [data, setData] = useState(null)
  useEffect(() => {
    let ignore = false
    fetch('/api/nhle').then((r) => (r.ok ? r.json() : null)).then((d) => !ignore && setData(d)).catch(() => {})
    return () => { ignore = true }
  }, [])
  if (!data || data.factors.length === 0) return null
  return (
    <details className="howto">
      <summary>How NHLe is worked out</summary>
      <p>
        NHLe turns a prospect's points per game in his league into the NHL points he would score over {data.season_games} games. Each league's
        factor is how much an NHL season scored by players who went from that league to the NHL the next season was, as a share of what they scored
        in the league: the games-weighted ratio of their NHL points per game to their league points per game. The factors come from our own
        data, every NHL skater since 2006-07. Because only players who reached the NHL are in it, the figure answers "if he gets there", and
        it is higher than the average prospect's real outlook. It is then scaled for age: players 20 and under outscored the plain factor
        and players 23 and over fell well short of it, so the figure is multiplied by the age factor below. Checked on later seasons than it
        was fitted on, the factor plus the age adjustment predicted next season's NHL points per game about 16% better than assuming every
        player scores the average. Needs 20 or more games in a season.
      </p>
      <div className="table-wrap">
        <table>
          <thead><tr><th className="left">League</th><th title="NHL points per game as a share of the league's">Factor</th><th title="90% interval from resampling players">Range</th><th title="Players who went from this league to the NHL the next season">Pairs</th></tr></thead>
          <tbody>
            {data.factors.map((f) => (
              <tr key={f.league}>
                <td className="left">{f.league}</td><td className="accent">{factorPct(f.factor)}</td>
                <td>{factorPct(f.lo)} to {factorPct(f.hi)}</td><td>{f.pairs}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.age_multipliers?.length > 0 && (
        <p className="sub">
          Age adjustment (age on September 15 of the season): {data.age_multipliers.map((a) => `${a.bucket} ×${a.multiplier.toFixed(2)}`).join(', ')}.
        </p>
      )}
    </details>
  )
}
