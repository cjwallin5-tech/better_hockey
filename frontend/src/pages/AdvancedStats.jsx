import PageTabs from '../components/PageTabs.jsx'
import SpecialTeams from './SpecialTeams.jsx'
import ScoreEffects from './ScoreEffects.jsx'
import Tracking from './Tracking.jsx'

/** The deeper team and player stat pages as tabs of one page. */
export default function AdvancedStats() {
  return (
    <main>
      <header><h1>Advanced stats</h1></header>
      <PageTabs resetOnSwitch tabs={[
        { id: 'special-teams', label: 'Special teams', content: <SpecialTeams embedded /> },
        { id: 'score-effects', label: 'Score effects', content: <ScoreEffects embedded /> },
        { id: 'tracking', label: 'Speed & shots', content: <Tracking embedded /> },
      ]} />
    </main>
  )
}
