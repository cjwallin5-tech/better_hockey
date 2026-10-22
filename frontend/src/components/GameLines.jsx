import { Link } from 'react-router-dom'
import { describe } from '../glossary.js'

const MIN_SECONDS = 60   // combinations that shared less than a minute are noise
const MAX_ROWS = 6

const mmss = (sec) => `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, '0')}`
const pct = (cf, ca) => (cf + ca > 0 ? `${((100 * cf) / (cf + ca)).toFixed(1)}` : '–')

function Combos({ title, rows, ids }) {
  const shown = rows.filter((r) => r.toi_sec >= MIN_SECONDS).slice(0, MAX_ROWS)
  if (shown.length === 0) return null
  return (
    <div className="table-wrap">
      <table className="lines-table">
        <thead>
          <tr>
            <th className="left">{title}</th>
            <th title={describe('5v5 TOI')}>5v5 TOI</th>
            <th title={describe('CF')}>CF</th>
            <th title={describe('CA')}>CA</th>
            <th title={describe('CF%')}>CF%</th>
            <th title="Goals for and against at five-on-five while this combination was on the ice">GF–GA</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={ids(r).join('-')}>
              <td className="left">
                {ids(r).map((id, i) => (
                  <span key={id}>{i > 0 && ' · '}<Link to={`/player/${id}`}>{r.names[i]}</Link></span>
                ))}
              </td>
              <td>{mmss(r.toi_sec)}</td><td>{r.cf}</td><td>{r.ca}</td>
              <td className="accent">{pct(r.cf, r.ca)}</td><td>{r.gf}{'–'}{r.ga}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Who played together at five-on-five in this game: forward lines and defense pairs, most-used first, with how each fared. */
export default function GameLines({ lines, pairs, sides }) {
  if (lines.length === 0 && pairs.length === 0) return null
  return (
    <section>
      <h2>Lines and pairings</h2>
      <p className="sub">
        Five-on-five only, ranked by ice time together, so the first row is the most-used combination, not necessarily the nominal first
        line. Combinations that shared under a minute are left out. CF% is the share of shot attempts the team took while they were on
        the ice.
      </p>
      {sides.map((team) => (
        <div key={team} className="game-lines">
          <h3>{team}</h3>
          <Combos title="Forwards" rows={lines.filter((l) => l.team === team)} ids={(r) => [r.p1, r.p2, r.p3]} />
          <Combos title="Defense" rows={pairs.filter((p) => p.team === team)} ids={(r) => [r.p1, r.p2]} />
        </div>
      ))}
    </section>
  )
}
