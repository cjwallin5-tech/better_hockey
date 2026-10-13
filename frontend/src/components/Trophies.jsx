import { useEffect, useState } from 'react'

const ordinal = (n) => {
  const v = n % 100
  if (v >= 11 && v <= 13) return `${n}th`
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`
}
const STAT_LABEL = { points: 'points', goals: 'goals', gsaa: 'GSAA' }
const fmtValue = (stat, v) => (stat === 'gsaa' ? `${v > 0 ? '+' : ''}${v.toFixed(1)}` : v)

/** Trophies this player is in the running for, judged on the stat that decides each one. */
export default function Trophies({ playerId }) {
  const [result, setResult] = useState({ id: null, list: null })

  useEffect(() => {
    fetch('/api/trophies')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setResult({ id: playerId, list: d?.players?.[playerId] ?? [], size: d?.size }))
      .catch(() => setResult({ id: playerId, list: null }))
  }, [playerId])

  const list = result.id === playerId ? result.list : null
  if (!list || list.length === 0) return null

  return (
    <section className="context" aria-label="Trophy contention">
      <ul>
        {list.map((t) => (
          <li key={t.trophy}>
            <strong>🏆 In the {t.trophy} race.</strong>{' '}
            <span>
              {ordinal(t.rank)} of {t.of} in {STAT_LABEL[t.stat]} ({fmtValue(t.stat, t.value)}), {t.basis}.
            </span>
          </li>
        ))}
      </ul>
      <p className="context-note">
        Contention here means a top-{result.size} spot in the stat that decides the award, so it moves a lot
        early in the season. Voted awards like the Hart and Selke aren't covered.
      </p>
    </section>
  )
}
