/** A row's place in the current sort: gold, silver and bronze discs for the top three, a quiet number after that. */
export default function RankBadge({ n }) {
  return <span className={`rank-badge${n <= 3 ? ` medal m${n}` : ''}`} title={`Number ${n} in this list`}>{n}</span>
}
