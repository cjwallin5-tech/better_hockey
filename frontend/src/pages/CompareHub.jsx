import PageTabs from '../components/PageTabs.jsx'
import Compare from './Compare.jsx'
import HeadToHead from './HeadToHead.jsx'

/** Player comparison and team/player head-to-head history as tabs of one page. */
export default function CompareHub() {
  return (
    <main>
      <header><h1>Compare</h1></header>
      <PageTabs resetOnSwitch tabs={[
        { id: 'players', label: 'Players', content: <Compare embedded /> },
        { id: 'head-to-head', label: 'Head-to-head history', content: <HeadToHead embedded /> },
      ]} />
    </main>
  )
}
