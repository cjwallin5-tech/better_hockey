const BADGE = {
  tired: ['2nd night', 'badge warn', 'Second night of a back-to-back against a rested team: teams score about a quarter of a goal fewer a game in these, and the matchup rating here is lowered to match'],
  edge: ['rest edge', 'badge', 'The opponent is on the second night of a back-to-back and this team is rested: teams score about a quarter of a goal more, and the matchup rating here is raised to match'],
}

/** "2nd night" or "rest edge" for a game's rest situation (kind: 'tired' | 'edge' | anything else for nothing). */
export default function RestBadge({ kind }) {
  const b = BADGE[kind]
  return b ? <span className={b[1]} title={b[2]}>{b[0]}</span> : null
}
