import PageTabs from '../components/PageTabs.jsx'
import Projections from './Projections.jsx'
import Luck from './Luck.jsx'

/** Where each player is headed this season, and who is running hot or cold against their shots. */
export default function ProjectionsHub() {
  return (
    <main>
      <header><h1>Projections</h1></header>
      <PageTabs resetOnSwitch tabs={[
        { id: 'projections', label: 'Season projections', content: <Projections embedded /> },
        { id: 'luck', label: 'Luck & regression', content: <Luck embedded /> },
      ]} />
    </main>
  )
}
