import { lazy, Suspense } from 'react'
import { useSearchParams } from 'react-router-dom'
import PageSkeleton from '../components/Skeleton.jsx'
import KindSwitch from '../components/KindSwitch.jsx'
import { pages } from '../routes.js'

// Each board is its own page with its own columns, filters and views; this page only picks which one is showing.
const SkaterBoard = lazy(pages.Leaderboard)
const GoalieBoard = lazy(pages.Goalies)

/** Every player in one place: a Skaters / Goalies switch over the two leaderboards. The choice lives in ?kind= so a link reopens it. */
export default function Players() {
  const [params, setParams] = useSearchParams()
  const kind = params.get('kind') === 'goalie' ? 'goalie' : 'skater'
  // The two boards have different filters, so leaving one drops its settings rather than carrying them over.
  const pick = (id) => setParams(id === 'goalie' ? { kind: 'goalie' } : {})
  return (
    <main>
      <KindSwitch kind={kind} onPick={pick} />
      <Suspense fallback={<PageSkeleton />}>
        {kind === 'goalie' ? <GoalieBoard key="goalie" embedded /> : <SkaterBoard key="skater" embedded />}
      </Suspense>
    </main>
  )
}
