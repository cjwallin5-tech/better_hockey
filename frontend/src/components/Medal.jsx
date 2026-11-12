const NAMES = { gold: 'Gold medal', silver: 'Silver medal', bronze: 'Bronze medal' }

/** A small gold, silver or bronze disc. */
export default function Medal({ medal }) {
  if (!medal) return null
  return <span className={`medal-dot ${medal}`} role="img" aria-label={NAMES[medal]} title={NAMES[medal]} />
}
