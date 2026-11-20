import PageTabs from '../components/PageTabs.jsx'
import Fantasy from './Fantasy.jsx'
import Watchlist from './Watchlist.jsx'
import Leagues from './Leagues.jsx'
import Matchups from './Matchups.jsx'

/** Everything fantasy in one place: your team (which has its own tabs), the watchlist, your leagues and the matchup ratings for deciding who to start. */
export default function FantasyHub() {
  return (
    <main>
      <header><h1>Fantasy</h1></header>
      <PageTabs param="section" resetOnSwitch tabs={[
        { id: 'team', label: 'My team', content: <Fantasy embedded /> },
        { id: 'watchlist', label: 'Watchlist', content: <Watchlist embedded /> },
        { id: 'matchups', label: 'Matchups', content: <Matchups embedded /> },
        { id: 'leagues', label: 'Leagues', content: <Leagues embedded /> },
      ]} />
    </main>
  )
}
