import PageTabs from '../components/PageTabs.jsx'
import ScheduleGrid from './ScheduleGrid.jsx'
import ScheduleStrength from './ScheduleStrength.jsx'
import Rest from './Rest.jsx'

/** Games per week, how hard each team's remaining games are, and the back-to-back schedule, as three tabs of one page. */
export default function Schedule() {
  return (
    <main>
      <header><h1>Schedule</h1></header>
      <PageTabs resetOnSwitch tabs={[
        { id: 'grid', label: 'Games per week', content: <ScheduleGrid embedded /> },
        { id: 'strength', label: 'Strength of schedule', content: <ScheduleStrength embedded /> },
        { id: 'rest', label: 'Back-to-backs', content: <Rest embedded /> },
      ]} />
    </main>
  )
}
