import { pkDetail, pkRole } from '../penaltyKill.js'

/** "PK1" or "PK2" for a skater who kills penalties, with the minutes and share in the tooltip. Nothing for everyone else. */
export default function PkTag({ p }) {
  const role = pkRole(p)
  if (!role) return null
  return <span className="role-tag pk" title={pkDetail(role)}>{role.unit}</span>
}
