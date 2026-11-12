/** A row's place in the current sort: gold, silver and bronze discs for the top three, a quiet number after that.
 *  Rows level on the sorted value share a place and show a T in front of it (T5). */
export default function RankBadge({ n, tied = false }) {
  return (
    <span className={`rank-badge${n <= 3 ? ` medal m${n}` : ''}${tied ? ' tied' : ''}`} title={`${tied ? 'Tied for number' : 'Number'} ${n} in this list`}>
      {tied ? `T${n}` : n}
    </span>
  )
}
