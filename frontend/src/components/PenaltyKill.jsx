import { fmtToi } from '../format.js'
import { pkDetail, pkRole } from '../penaltyKill.js'

const Stat = ({ label, value, note }) => (
  <div className="tile">
    <span>{label}</span>
    <strong>{value}</strong>
    {note && <small className="muted">{note}</small>}
  </div>
)

/** A skater's penalty-kill role and numbers, at the top of the Defense tab: killing penalties is the hardest defensive work, so it frames the rest. */
export default function PenaltyKill({ p }) {
  const role = pkRole(p)
  const pct = p.sh_toi_pct == null ? '–' : `${Math.round(p.sh_toi_pct * 100)}%`
  return (
    <section className="pk-panel">
      <h2>Penalty kill {role && <span className="role-tag pk" title={pkDetail(role)}>{role.unit}</span>}</h2>
      <p className="sub">
        {role
          ? `${pkDetail(role)}. These are the toughest minutes to defend, against the other team's best players, so read the 5v5 numbers on the Defense tab with that in mind.`
          : 'Not a regular penalty killer (under 1:00 a game short-handed, or on the ice for less than a third of the team\'s penalty kill).'}
      </p>
      <section className="tiles usage">
        <Stat label="PK unit" value={role ? role.unit : '–'} note={role ? (role.unit === 'PK1' ? 'top unit' : 'second unit') : undefined} />
        <Stat label="SH TOI" value={fmtToi(p.sh_toi_per_game)} note="short-handed, per game" />
        <Stat label="Share of team PK" value={pct} note="of its short-handed time" />
        <Stat label="PP goals against" value={p.pk_goals_against_per60 == null ? '–' : p.pk_goals_against_per60.toFixed(1)} note="per 60 min short-handed" />
        <Stat label="SH points" value={p.sh_points ?? '–'} />
      </section>
    </section>
  )
}
