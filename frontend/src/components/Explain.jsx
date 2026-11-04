import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const signed = (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(Math.round(v))}`
const KIND = { luck: 'Results vs. chances', real: 'Real change' }

// The two kinds of finding, in plain words. Luck evens out; real change holds while the role does.
const GROUPS = [
  {
    kind: 'luck',
    title: 'Luck, likely to fade',
    blurb: 'Scoring above (or below) what the shots and the linemates\' shots support. Over a full season this tends to even out.',
  },
  {
    kind: 'real',
    title: 'Real change, likely to last',
    blurb: 'How many shots, how good the shots are, ice time and role. These hold for as long as the role does.',
  },
]

/** One factor, as a badge, a sentence about it and what it is worth over a full season. */
function Finding({ f, games }) {
  const cls = f.direction === 'down' ? 'badge warn' : 'badge'
  const arrow = f.direction === 'down' ? '↓' : f.direction === 'up' ? '↑' : '•'
  return (
    <li className="finding">
      <span className={cls} title={KIND[f.kind]}>{arrow} {f.title}</span>
      <span className="finding-text">{f.text}</span>
      {f.price != null && (
        <span className="finding-price" title={`Estimated ${f.unit} over ${games} games`}>
          <strong>{signed(f.price)} {f.unit}</strong>
          <small>over {games} games</small>
        </span>
      )}
    </li>
  )
}

/** One row of the chart: a label, a bar sized to the amount, and the amount in points. Up and down differ by position and sign, not colour alone. */
function Row({ label, note, value, scale, tone }) {
  const width = scale ? Math.max(3, (Math.abs(value) / scale) * 100) : 0
  return (
    <li className="explain-row">
      <div className="explain-row-label">
        <strong>{label}</strong>
        <span>{note}</span>
      </div>
      <div className="explain-bar" aria-hidden="true">
        <i className={`${tone} ${value < 0 ? 'neg' : ''}`} style={{ width: `${width}%` }} />
      </div>
      <strong className="explain-row-value">{signed(value)} pts</strong>
    </li>
  )
}

/** The sentence about what to expect, from how much of the change is luck. */
function Takeaway({ d }) {
  if (d.change == null || !d.luck_total) return null
  const luck = Math.round(d.luck_total)
  if (Math.abs(luck) < 3) return null
  if (luck > 0) {
    return (
      <p className="explain-takeaway">
        <strong>What it means:</strong> about {luck} points of the pace is luck that should fade, so expect the pace to come down. The projected finish beside this card shows where it is likely to land.
      </p>
    )
  }
  return (
    <p className="explain-takeaway">
      <strong>What it means:</strong> results are running about {Math.abs(luck)} points below what the chances support, so expect the pace to come back up. The projected finish beside this card shows where it is likely to land.
    </p>
  )
}

/**
 * The opening sentence: this season's pace against last season. Last season's total is shown as it happened (points in games) next to
 * the same rate stretched to this season's length, because that stretched number is what the comparison uses and is not a real total.
 */
function Lead({ d, name }) {
  const last = d.facts?.last
  const stretched = last && last.gp !== d.games
  return (
    <>
      {name ? `${name} is on` : 'On'} pace for <strong>{Math.round(d.pace)} points</strong> over {d.games} games
      {d.last_pace != null && d.change != null && (
        <>, {d.change >= 0 ? 'up' : 'down'} <strong>{Math.abs(Math.round(d.change))}</strong> on last season&rsquo;s {Math.round(d.last_pace)}
          {stretched && <> ({last.points} points in {last.gp} games, stretched to {d.games} games)</>}</>
      )}
      .
    </>
  )
}

/** What changed for one skater: pace against last season, split into luck and real change, with the biggest factors listed. */
export default function Explain({ playerId, name }) {
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

  const split = d.change != null && (d.luck_total || d.real_total)
  const rows = split ? [
    { label: 'Luck', note: 'tends to fade', value: d.luck_total, tone: 'luck' },
    { label: 'Real change', note: 'tends to last', value: d.real_total, tone: 'real' },
    { label: 'Everything else', note: 'not explained by the factors below', value: d.unexplained, tone: 'rest' },
  ] : []
  const scale = Math.max(0, ...rows.map((r) => Math.abs(r.value ?? 0)))

  return (
    <section className="card explain">
      <div className="eyebrow">What changed</div>
      {split ? (
        <>
          <p className="explain-lead"><Lead d={d} name={name} /></p>
          <div className="explain-sub">Where the {signed(d.change)} comes from</div>
          <ul className="explain-rows">
            {rows.map((r) => <Row key={r.label} {...r} scale={scale} />)}
          </ul>
          <Takeaway d={d} />
        </>
      ) : d.pace != null ? (
        <p className="explain-lead">
          <Lead d={d} name={name} />
          {d.findings.length === 0 && ' Nothing stands out: shot volume, shot quality, ice time and finishing are all close to normal.'}
        </p>
      ) : (
        <p className="explain-lead">{d.headline}</p>
      )}

      {d.findings.length > 0 && GROUPS.map((g) => {
        const items = d.findings.filter((f) => f.kind === g.kind)
        if (items.length === 0) return null
        return (
          <div className="explain-group" key={g.kind}>
            <h3>{g.title}</h3>
            <p className="explain-blurb">{g.blurb}</p>
            <ul className="findings">
              {items.map((f) => <Finding key={f.key} f={f} games={d.games} />)}
            </ul>
          </div>
        )
      })}

      <details className="howto">
        <summary>How to read this</summary>
        <p>
          <strong>Pace</strong> is the points a player would finish with over a full {d.games}-game season if they keep scoring at this season's rate,
          shown next to last season's total. The change is then split into three parts.
        </p>
        <p>
          <strong>Luck</strong> is scoring above or below what the chances support: a player finishing better than their shots predict, or
          linemates scoring more than <em>their</em> shots predict while the player is on the ice (which adds assists). Luck tends to fade
          (see <Link to="/projections?tab=luck">Luck &amp; regression</Link>).{' '}
          <strong>Real change</strong> is things the player controls or is given: how many shots they take, how good those shots are, how much they play and
          where. It tends to last for as long as the role does.{' '}
          <strong>Everything else</strong> is the part the factors can't account for.
        </p>
        <p>
          {d.early && 'It is early in the season, so a handful of games can swing any of this: treat it as a first read. '}
          The factors overlap a little (more ice time also means more shots), so they won't add up exactly. Injuries, and coaching changes
          that don't show up in ice time, aren't known.
        </p>
      </details>
    </section>
  )
}
