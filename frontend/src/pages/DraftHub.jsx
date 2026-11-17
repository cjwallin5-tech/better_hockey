import PageTabs from '../components/PageTabs.jsx'
import Prospects from './Prospects.jsx'
import Lottery from './Lottery.jsx'

/** The players who are not in the NHL yet, and the lottery that decides where they go. */
export default function DraftHub() {
  return (
    <main>
      <header><h1>Prospects &amp; draft</h1></header>
      <PageTabs resetOnSwitch tabs={[
        { id: 'prospects', label: 'Prospects', content: <Prospects embedded /> },
        { id: 'lottery', label: 'Draft lottery', content: <Lottery embedded /> },
      ]} />
    </main>
  )
}
