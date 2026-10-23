import { Link } from 'react-router-dom'
import { CountryFlag } from './Flag.jsx'

export const ppg = (v) => (v == null ? '–' : v.toFixed(2))
export const svp = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))
export const height = (inches) => (inches ? `${Math.floor(inches / 12)}'${inches % 12}"` : '–')

/** "2023 R2 #56 (EDM)" for a drafted prospect, "Undrafted" otherwise. */
export const draftText = (d) => (d ? `${d.year} R${d.round} #${d.overall}${d.team ? ` (${d.team})` : ''}` : 'Undrafted')

/** A prospect's name as a link to their page, with their flag. */
export function ProspectName({ p }) {
  return <><CountryFlag code={p.birth_country} /> <Link to={`/prospect/${p.player_id}`}>{p.name}</Link></>
}

/** The columns of a prospect's current line: skaters show G-A-P and points a game, goalies wins, save % and GAA. */
export function Line({ p }) {
  if (!p.games) return <span className="muted">No games yet</span>
  if (p.position === 'G') return <>{p.games} GP, {p.wins ?? '–'} W, {svp(p.save_pct)} SV%, {p.gaa?.toFixed(2) ?? '–'} GAA</>
  return <>{p.games} GP, {p.goals}-{p.assists}-{p.points} ({ppg(p.points_per_game)} P/GP)</>
}
