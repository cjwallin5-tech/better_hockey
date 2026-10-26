import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fmtPct } from '../format.js'
import { describe } from '../glossary.js'

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

  const table = (rows, label) => {
    const hasXg = rows.some((l) => l.xg_pct != null)
    return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="left">{label}</th><th title={describe('5v5 TOI')}>5v5 TOI</th><th title={describe('GP')}>GP</th><th title={describe('CF')}>CF</th><th title={describe('CA')}>CA</th><th title={describe('CF%')}>CF%</th>{hasXg && <th title={describe('xGF%')}>xGF%</th>}<th title={describe('GF')}>GF</th><th title={describe('GA')}>GA</th>
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
              <td className="accent">{pct(l.cf_pct)}</td>{hasXg && <td>{pct(l.xg_pct)}</td>}<td>{l.gf}</td><td>{l.ga}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    )
  }

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

const signedPts = (v) => (v == null ? '–' : `${v >= 0 ? '+' : '−'}${Math.abs(v * 100).toFixed(1)}`)
const per60 = (v) => (v == null ? '–' : v.toFixed(2))
const VERDICT_CLASS = { clear: 'badge', slight: 'badge', none: 'muted' }

/** Who a skater plays with, and whether their team gets more of the chances with each of them than without. */
export function Linemates({ playerId }) {
  const data = useJson(`/api/skaters/${playerId}/linemates`)
  if (!data || data.linemates.length === 0) return null
  const minutes = Math.round(data.min_together_sec / 60)
  const hasXg = data.linemates.some((m) => m.basis === 'xg')

  return (
    <section>
      <h2>Linemates &amp; chemistry</h2>
      <p className="sub">
        Most 5v5 time with each teammate. The question is whether this player's team gets a bigger share of the good chances with the teammate
        than it gets when he plays without him: {hasXg ? 'the share of expected goals (xG), our own shot-quality model' : 'the share of shot attempts (Corsi), since expected goals are not stored for these games yet'}.
        The lift is the difference in points of share, and the verdict only speaks after {minutes} minutes together and says how sure the
        data lets it be. The last chemistry column is the same lift from the teammate's side. It can't tell a pairing's effect from usage:
        time apart is usually with other linemates, opponents and zone starts, so treat a verdict as a clue. {NOTE}
      </p>
      {(data.best || data.worst) && (
        <p>
          {data.best && <>Best fit: <Link to={`/player/${data.best.player_id}`}>{data.best.name}</Link>. </>}
          {data.worst && <>Weakest fit: <Link to={`/player/${data.worst.player_id}`}>{data.worst.name}</Link>.</>}
        </p>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Teammate</th><th className="left" title={describe('Pos')}>Pos</th><th title={describe('Together')}>Together</th><th title={describe('GP')}>GP</th>
              <th title="Verdict for this player: a boost or drag only when the lift is big next to how much data there is">Chemistry</th>
              <th title="Share of the chances together minus this player's share apart, in points of share (expected goals where stored, otherwise shot attempts)">Lift</th>
              <th title="Share of the expected goals while the two are on the ice together (50% is even)">xG% together</th>
              <th title="This player's share of the expected goals when he plays without this teammate">xG% apart</th>
              <th title="This player's expected goals for per 60 minutes, together and then without this teammate">xGF/60 tog. / apart</th>
              <th title="Expected goals against per 60 minutes, together and then without this teammate">xGA/60 tog. / apart</th>
              <th title="The same lift from the teammate's side: how the teammate does with this player against without him">Teammate's lift</th>
              <th title={describe('CF% together')}>CF% together</th><th title={describe('CF% player apart')}>CF% player apart</th><th title={describe('CF% teammate apart')}>CF% teammate apart</th><th title={describe('GF–GA')}>GF–GA</th>
            </tr>
          </thead>
          <tbody>
            {data.linemates.map((m) => (
              <tr key={m.player_id}>
                <td className="left"><Link to={`/player/${m.player_id}`}>{m.name}</Link></td>
                <td className="left">{m.position}</td>
                <td>{mins(m.toi_sec)}</td><td>{m.games}</td>
                <td>{m.verdict ? <span className={VERDICT_CLASS[m.strength]} title={m.z != null ? `z ${m.z.toFixed(1)}` : undefined}>{m.verdict}</span> : <span className="muted">too little time</span>}</td>
                <td className="accent">{signedPts(m.lift)}{m.basis === 'corsi' && m.lift != null && <span className="muted"> CF</span>}</td>
                <td>{pct(m.xg_share_together)}</td><td>{pct(m.xg_share_apart)}</td>
                <td>{per60(m.xgf60_together)} / {per60(m.xgf60_apart)}</td><td>{per60(m.xga60_together)} / {per60(m.xga60_apart)}</td>
                <td>{signedPts(m.partner_lift)}{m.partner_verdict && m.partner_verdict !== 'no clear effect' && <span className="muted"> {m.partner_verdict}</span>}</td>
                <td>{pct(m.cf_pct_together)}</td>
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
