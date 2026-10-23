import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const signed = (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(Math.round(v))}`
const KIND = { luck: 'Results vs. chances', real: 'Real change' }

/** The one-word badge for a finding: where it points, with the group it belongs to in the tooltip so colour isn't the only cue. */
function Finding({ f, games }) {
  const cls = f.direction === 'down' ? 'badge warn' : f.direction === 'up' ? 'badge' : 'badge'
  const arrow = f.direction === 'down' ? '↓' : f.direction === 'up' ? '↑' : '•'
  return (
    <li className="finding">
      <span className={cls} title={KIND[f.kind]}>{arrow} {f.title}</span>{' '}
      {f.price != null && <strong className="muted" title={`Estimated ${f.unit} over ${games} games`}>{signed(f.price)} {f.unit}</strong>}{' '}
      {f.text}
    </li>
  )
}

/** What changed for one skater: pace against last season, split into luck and real change, with the biggest factors listed. */
export default function Explain({ playerId }) {
  const [state, setState] = useState({ id: null, data: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/skaters/${playerId}/explain`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setState({ id: playerId, data }))
      .catch(() => !ignore && setState({ id: playerId, data: null }))
    return () => { ignore = true }
  }, [playerId])
  const d = state.id === playerId ? state.data : null
  if (!d) return null

  return (
    <section>
      <h2>What changed</h2>
      <p>{d.headline}</p>
      {d.findings.length > 0 && (
        <ul className="findings">
          {d.findings.map((f) => <Finding key={f.key} f={f} games={d.games} />)}
        </ul>
      )}
      <p className="sub">
        {d.early && 'Early in the season a handful of games can swing any of this, so treat it as a first read. '}
        Amounts are estimated over a full {d.games}-game season at the current rate. "Results vs. chances" is luck that tends to fade
        (see <Link to="/luck">Luck &amp; regression</Link>); "Real change" is shot volume, shot quality, ice time and role, which tend to last
        while the role does. The factors overlap a little (more ice time also means more shots), so they won't add up exactly.
        Injuries and coaching changes that don't show in ice time aren't known.
      </p>
    </section>
  )
}
