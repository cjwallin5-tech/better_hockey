import { useEffect } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import Leaderboard from './pages/Leaderboard.jsx'
import AllTime from './pages/AllTime.jsx'
import { useTheme } from './theme.js'
import Compare from './pages/Compare.jsx'
import Game from './pages/Game.jsx'
import Home from './pages/Home.jsx'
import Goalie from './pages/Goalie.jsx'
import Goalies from './pages/Goalies.jsx'
import Milestones from './pages/Milestones.jsx'
import Player from './pages/Player.jsx'
import ResetPassword from './pages/ResetPassword.jsx'
import ScheduleGrid from './pages/ScheduleGrid.jsx'
import HeadToHead from './pages/HeadToHead.jsx'
import Tracking from './pages/Tracking.jsx'
import Luck from './pages/Luck.jsx'
import Matchups from './pages/Matchups.jsx'
import Roles from './pages/Roles.jsx'
import Trophy from './pages/Trophy.jsx'
import TrophyIndex from './pages/TrophyIndex.jsx'
import Account from './pages/Account.jsx'
import Watchlist from './pages/Watchlist.jsx'
import Projections from './pages/Projections.jsx'
import Tonight from './pages/Tonight.jsx'
import MyTeam from './pages/MyTeam.jsx'
import Leagues from './pages/Leagues.jsx'
import Accuracy from './pages/Accuracy.jsx'
import Absences from './pages/Absences.jsx'
import League from './pages/League.jsx'
import Rest from './pages/Rest.jsx'
import Prospects from './pages/Prospects.jsx'
import Prospect from './pages/Prospect.jsx'
import SpecialTeams from './pages/SpecialTeams.jsx'
import { initAuth, useAuth } from './auth.js'
import Fantasy from './pages/Fantasy.jsx'
import Standings from './pages/Standings.jsx'
import TrophyRaces from './pages/TrophyRaces.jsx'
import Team from './pages/Team.jsx'
import NavMore from './components/NavMore.jsx'
import Freshness from './components/Freshness.jsx'
import Icon from './components/Icon.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import GlobalSearch from './components/GlobalSearch.jsx'

/** Old /alltime links: send them to the skater or goalie page, keeping any filters in the query. */
function AllTimeRedirect() {
  const params = new URLSearchParams(useLocation().search)
  const goalie = params.get('kind') === 'goalie'
  params.delete('kind')
  const query = params.toString()
  return <Navigate to={`/alltime/${goalie ? 'goalies' : 'skaters'}${query ? `?${query}` : ''}`} replace />
}

/** The routes, wrapped so a crash on one page shows a message, and moving to another page clears it. */
function Pages() {
  const { pathname } = useLocation()
  return (
    <ErrorBoundary key={pathname}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/skaters" element={<Leaderboard />} />
        <Route path="/player/:id" element={<Player />} />
        <Route path="/goalies" element={<Goalies />} />
        <Route path="/goalie/:id" element={<Goalie />} />
        <Route path="/milestones" element={<Milestones />} />
        <Route path="/alltime" element={<AllTimeRedirect />} />
        <Route path="/alltime/skaters" element={<AllTime key="skater" kind="skater" />} />
        <Route path="/alltime/goalies" element={<AllTime key="goalie" kind="goalie" />} />
        <Route path="/game/:id" element={<Game />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/schedule" element={<ScheduleGrid />} />
        <Route path="/head-to-head" element={<HeadToHead />} />
        <Route path="/tracking" element={<Tracking />} />
        <Route path="/luck" element={<Luck />} />
        <Route path="/roles" element={<Roles />} />
        <Route path="/matchups" element={<Matchups />} />
        <Route path="/trophy" element={<TrophyIndex />} />
        <Route path="/trophy/:id" element={<Trophy />} />
        <Route path="/account" element={<Account />} />
        <Route path="/fantasy" element={<Fantasy />} />
        <Route path="/special-teams" element={<SpecialTeams />} />
        <Route path="/prospects" element={<Prospects />} />
        <Route path="/prospect/:id" element={<Prospect />} />
        <Route path="/rest" element={<Rest />} />
        <Route path="/projections" element={<Projections />} />
        <Route path="/tonight" element={<Tonight />} />
        <Route path="/my-team" element={<MyTeam />} />
        <Route path="/leagues" element={<Leagues />} />
        <Route path="/accuracy" element={<Accuracy />} />
        <Route path="/absences" element={<Absences />} />
        <Route path="/league/:id" element={<League />} />
        <Route path="/watchlist" element={<Watchlist />} />
        <Route path="/trophies" element={<TrophyRaces />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/standings" element={<Standings />} />
        <Route path="/team/:abbrev" element={<Team />} />
      </Routes>
      </ErrorBoundary>
  )
}

export default function App() {
  const { dark, toggle } = useTheme()
  const { user } = useAuth()
  useEffect(initAuth, [])
  return (
    <BrowserRouter>
      <header className="topbar">
      <nav className="topnav">
        <NavLink to="/" end className="brand" aria-label="NHL Stats home">NHL<b>STATS</b></NavLink>
        <NavLink to="/skaters">Skaters</NavLink>
        <NavLink to="/goalies">Goalies</NavLink>
        <NavLink to="/standings">Standings</NavLink>
        <NavLink to="/fantasy">Fantasy</NavLink>
        <NavLink to="/tonight">Tonight</NavLink>
        <NavLink to="/my-team">My team</NavLink>
        <NavMore items={[...(user?.admin ? [['/accuracy', 'Accuracy']] : []), ['/compare', 'Compare'], ['/absences', 'Who\u2019s out'], ['/prospects', 'Prospects'], ['/leagues', 'Leagues'], ['/watchlist', 'Watchlist'], ['/milestones', 'Milestones'], ['/trophies', 'Trophy races'], ['/trophy', 'Trophy winners'], ['/schedule', 'Schedule grid'], ['/rest', 'Back-to-backs'], ['/special-teams', 'Special teams'], ['/head-to-head', 'Head-to-head'], ['/tracking', 'Speed & shots'], ['/projections', 'Projections'], ['/luck', 'Luck & regression'], ['/matchups', 'Matchups']]} />
        <GlobalSearch />
        <NavLink to="/account" className="nav-account">{user ? user.email : 'Log in'}</NavLink>
        <button className="theme-toggle" onClick={toggle} aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'} title={dark ? 'Switch to light theme' : 'Switch to dark theme'}>
          <Icon name={dark ? 'sun' : 'moon'} /> {dark ? 'Light' : 'Dark'}
        </button>
      </nav>
      </header>
      <Pages />
      <Freshness />
    </BrowserRouter>
  )
}
