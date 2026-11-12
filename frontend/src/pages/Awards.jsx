import PageTabs from '../components/PageTabs.jsx'
import TrophyRaces from './TrophyRaces.jsx'
import TrophyIndex from './TrophyIndex.jsx'
import InternationalAwards from '../components/InternationalAwards.jsx'

/** The trophy pages in one place: who is in the running this season, and every trophy's past winners. */
export default function Awards() {
  return (
    <main>
      <header><h1>Awards</h1></header>
      <PageTabs resetOnSwitch tabs={[
        { id: 'races', label: 'This season\u2019s races', content: <TrophyRaces embedded /> },
        { id: 'winners', label: 'Past winners', content: <TrophyIndex embedded /> },
        { id: 'international', label: 'International', content: <InternationalAwards /> },
      ]} />
    </main>
  )
}
