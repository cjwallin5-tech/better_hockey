/**
 * A tiny bar strip for a player's last games, oldest on the left. `values` are numbers or null (no data that game).
 * Skaters pass points a game, so a scoreless game shows as a flat tick; goalies pass save percentage with `floor`/`ceil`
 * set so the bars show the spread. `bad` marks the bars that should read as a bad night.
 */
export default function Spark({ values, max, floor = 0, bad, label, width = 84, height = 24 }) {
  if (!values || values.length === 0) return <span className="muted">–</span>
  const top = max ?? Math.max(1, ...values.filter((v) => v != null))
  const gap = 2
  const w = Math.max(3, (width - gap * (values.length - 1)) / values.length)
  return (
    <svg className="spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <title>{label}</title>
      {values.map((v, i) => {
        const h = v == null ? 2 : Math.max(2, ((v - floor) / (top - floor)) * (height - 2))
        const isBad = bad ? bad(v) : false
        return <rect key={i} x={i * (w + gap)} y={height - h} width={w} height={h} rx="1" className={v == null || v <= floor ? 'spark-none' : isBad ? 'spark-bad' : 'spark-on'} />
      })}
    </svg>
  )
}
