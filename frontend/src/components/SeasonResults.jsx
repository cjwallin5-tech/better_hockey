import { seasonLabel } from '../career.js'
import { signed } from '../goalieZones.js'

const shortYears = (sid) => seasonLabel(Number(sid)).replace(/^20/, '').replace('-20', '-')

/** A zone's result in each season ("22-23 +2.1  23-24 -0.4"), as separate items that wrap inside the cell instead of one long line. */
export default function SeasonResults({ bySeason }) {
  const rows = Object.entries(bySeason ?? {})
  return (
    <>
      {rows.map(([sid, v]) => (
        <span key={sid} className="season-result"><span>{shortYears(sid)}</span> {signed(v)}</span>
      ))}
    </>
  )
}
