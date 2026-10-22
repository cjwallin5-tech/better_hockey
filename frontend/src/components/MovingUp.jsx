import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { mmss } from './Roles.jsx'

const WINDOW = 5
const LIMIT = 10

/** One line on what changed for a skater: the power-play move if there is one, otherwise the ice-time rise. */
function changeText(r) {
  if (r.pp_change) return `${r.pp_label} · ${mmss(r.pp_base)} → ${mmss(r.pp)} of power play a game`
  if (r.ev_change) return `More even-strength time · ${mmss(r.ev_base)} → ${mmss(r.ev)} a game`
  return ''
}

/** Home-page card: skaters whose role has grown over their last few games. */
export default function MovingUp() {
  const [rows, setRows] = useState(null)
  useEffect(() => {
    let ignore = false
    fetch(`/api/roles/changes?dir=up&window=${WINDOW}&limit=${LIMIT}`)
      .then((r) => (r.ok ? r.json() : { rows: [] }))
      .then((d) => !ignore && setRows(d.rows))
      .catch(() => !ignore && setRows([]))
    return () => { ignore = true }
  }, [])

  return (
    <section className="card">
      <h2>Moving up</h2>
      <p className="muted small">
        Power-play promotions and rising ice time over the last {WINDOW} games compared with earlier this season. Ice time is the
        earliest sign of a new role, before the points show up.
      </p>
      {rows === null && <p className="status">Loading…</p>}
      {rows && rows.length === 0 && <p className="status">Nobody has moved up enough yet.</p>}
      {rows && rows.length > 0 && (
        <table className="mini">
          <tbody>
            {rows.map((r) => (
              <tr key={r.player_id}>
                <td>
                  <Link to={`/player/${r.player_id}`}>{r.name}</Link> <span className="muted">{r.team} · {r.position}</span>
                </td>
                <td>{changeText(r)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="muted small"><Link to="/roles">See everyone, including who is moving down →</Link></p>
    </section>
  )
}
