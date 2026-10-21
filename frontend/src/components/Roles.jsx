import { useEffect, useState } from 'react'

/** m:ss for a number of seconds. */
export const mmss = (s) => (s == null ? '–' : `${Math.floor(Math.round(s) / 60)}:${String(Math.round(s) % 60).padStart(2, '0')}`)
/** +m:ss or −m:ss for a change in seconds. */
export const signedMmss = (s) => (s == null ? '–' : `${s < 0 ? '−' : '+'}${mmss(Math.abs(s))}`)
const unitName = (u) => u ?? 'no PP'

/** Role-change figures for a list of skater ids, keyed by id (an object), or null until loaded. */
export function useRoles(ids, window = 5) {
  const key = [...new Set(ids)].sort((a, b) => a - b).join(',')
  const [state, setState] = useState({ key: null, data: null })
  useEffect(() => {
    if (!key) return undefined
    let ignore = false
    fetch(`/api/roles/players?ids=${key}&window=${window}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setState({ key: `${key}|${window}`, data }))
      .catch(() => !ignore && setState({ key: `${key}|${window}`, data: null }))
    return () => { ignore = true }
  }, [key, window])
  return state.key === `${key}|${window}` ? state.data?.players ?? null : null
}

/** A short badge and a sentence for one skater's role change, or null when nothing moved. */
export function roleSummary(row) {
  if (!row || !row.direction) return null
  const n = row.window
  const parts = []
  if (row.pp_change) {
    parts.push(`${row.pp_label}: ${unitName(row.unit_base)} → ${unitName(row.unit)} (${mmss(row.pp_base)} → ${mmss(row.pp)} of power play a game, last ${n} games vs earlier)`)
  }
  if (row.ev_change) {
    parts.push(`${row.ev_change === 'up' ? 'More' : 'Less'} even-strength time (${mmss(row.ev_base)} → ${mmss(row.ev)} a game)`)
  }
  const arrow = row.direction === 'up' ? '↑' : row.direction === 'down' ? '↓' : '↕'
  const short = row.pp_change ? `${arrow} ${row.pp_change === 'up' ? (row.unit ?? 'PP') : row.unit ? row.unit : 'PP'}` : `${arrow} TOI`
  return { direction: row.direction, short, title: parts.join('. ') }
}

/** A small badge for a roster table: the power-play move if there is one, otherwise the ice-time change. */
export function RoleBadge({ row }) {
  const s = roleSummary(row)
  if (!s) return null
  return <span className={s.direction === 'down' ? 'badge warn' : 'badge'} title={s.title}>{s.short}</span>
}

/** One skater's role on the player page: power-play unit and ice time, last few games vs earlier. Null until there is enough to compare. */
export function RolePanel({ playerId, window = 5 }) {
  const row = useRoles([playerId], window)?.[playerId]
  if (!row) return null
  const s = roleSummary(row)
  const tile = (label, base, now) => (
    <div className="tile">
      <span>{label}</span>
      <strong>{mmss(now)}</strong>
      <span>was {mmss(base)}</span>
    </div>
  )
  return (
    <section>
      <h2>Role</h2>
      <p className="sub">
        Last {row.window} games against earlier this season. {s ? s.title + '.' : 'No real change in power-play unit or ice time.'}
      </p>
      <div className="tiles">
        <div className="tile">
          <span>Power-play unit</span>
          <strong>{unitName(row.unit)}</strong>
          <span>was {unitName(row.unit_base)}</span>
        </div>
        {tile('PP time / game', row.pp_base, row.pp)}
        {tile('Even strength / game', row.ev_base, row.ev)}
        {tile('Total / game', row.total_base, row.total)}
      </div>
    </section>
  )
}
