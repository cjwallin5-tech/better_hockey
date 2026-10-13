import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fmtPct } from '../format.js'

const mins = (sec) => `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`
const pct = (v) => (v == null ? '–' : fmtPct(v))

function useJson(url) {
  const [state, setState] = useState({ url: null, data: null })
  useEffect(() => {
    let ignore = false
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setState({ url, data }))
      .catch(() => !ignore && setState({ url, data: null }))
    return () => { ignore = true }
  }, [url])
  return state.url === url ? state.data : null
}

const NOTE = '5v5 time is approximated from shift charts (within about 30 seconds a game for most players).'

/** A team's most-used forward lines and defense pairs. */
export function TeamLines({ abbrev }) {
  const data = useJson(`/api/teams/${abbrev}/lines`)
  if (!data || (data.forwards.length === 0 && data.defense.length === 0)) return null

  const table = (rows, label) => (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="left">{label}</th><th>5v5 TOI</th><th>GP</th><th>CF</th><th>CA</th><th>CF%</th><th>GF</th><th>GA</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((l) => (
            <tr key={l.players.map((p) => p.player_id).join('-')}>
              <td className="left">
                {l.players.map((p, i) => (
                  <span key={p.player_id}>{i > 0 && ' – '}<Link to={`/player/${p.player_id}`}>{p.name}</Link></span>
                ))}
              </td>
              <td>{mins(l.toi_sec)}</td><td>{l.games}</td><td>{l.cf}</td><td>{l.ca}</td>
              <td className="accent">{pct(l.cf_pct)}</td><td>{l.gf}</td><td>{l.ga}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )

  return (
    <section>
      <h2>Lines &amp; pairings</h2>
      <p className="sub">Most-used 5v5 combinations this season. CF% is the share of shot attempts while that group is on the ice. {NOTE}</p>
      <h3 className="career-table-title">Forward lines</h3>
      {table(data.forwards, 'Line')}
      <h3 className="career-table-title">Defense pairs</h3>
      {table(data.defense, 'Pair')}
    </section>
  )
}

/** Who a skater plays with, and how each of them does together vs apart. */
export function Linemates({ playerId }) {
  const data = useJson(`/api/skaters/${playerId}/linemates`)
  if (!data || data.linemates.length === 0) return null

  return (
    <section>
      <h2>Linemates</h2>
      <p className="sub">
        Most 5v5 time with each teammate, and the shot-attempt share (CF%) when they share the ice
        versus when each plays without the other. Both columns higher than "apart" suggests a
        good fit. {NOTE}
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Teammate</th><th className="left">Pos</th><th>Together</th><th>GP</th>
              <th>CF% together</th><th>CF% player apart</th><th>CF% teammate apart</th><th>GF–GA</th>
            </tr>
          </thead>
          <tbody>
            {data.linemates.map((m) => (
              <tr key={m.player_id}>
                <td className="left"><Link to={`/player/${m.player_id}`}>{m.name}</Link></td>
                <td className="left">{m.position}</td>
                <td>{mins(m.toi_sec)}</td><td>{m.games}</td>
                <td className="accent">{pct(m.cf_pct_together)}</td>
                <td>{pct(m.cf_pct_player_apart)}</td>
                <td>{pct(m.cf_pct_partner_apart)}</td>
                <td>{m.gf}–{m.ga}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
