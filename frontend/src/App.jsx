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
import Account from './pages/Account.jsx'
import { initAuth, useAuth } from './auth.js'
import Fantasy from './pages/Fantasy.jsx'
import Standings from './pages/Standings.jsx'
import TrophyRaces from './pages/TrophyRaces.jsx'
import Team from './pages/Team.jsx'
import NavMore from './components/NavMore.jsx'
import Freshness from './components/Freshness.jsx'
import Icon from './components/Icon.jsx'

/** Old /alltime links: send them to the skater or goalie page, keeping any filters in the query. */
function AllTimeRedirect() {
  const params = new URLSearchParams(useLocation().search)
  const goalie = params.get('kind') === 'goalie'
  params.delete('kind')
  const query = params.toString()
  return <Navigate to={`/alltime/${goalie ? 'goalies' : 'skaters'}${query ? `?${query}` : ''}`} replace />
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
        <NavMore items={[['/compare', 'Compare'], ['/milestones', 'Milestones'], ['/trophies', 'Trophy races'], ['/schedule', 'Schedule grid'], ['/head-to-head', 'Head-to-head'], ['/tracking', 'Speed & shots'], ['/luck', 'Luck & regression'], ['/matchups', 'Matchups']]} />
        <NavLink to="/account" className="nav-account">{user ? user.email : 'Log in'}</NavLink>
        <button className="theme-toggle" onClick={toggle} aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'} title={dark ? 'Switch to light theme' : 'Switch to dark theme'}>
          <Icon name={dark ? 'sun' : 'moon'} /> {dark ? 'Light' : 'Dark'}
        </button>
      </nav>
      </header>
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
        <Route path="/roles" element={<Navigate to="/skaters" replace />} />
        <Route path="/matchups" element={<Matchups />} />
        <Route path="/account" element={<Account />} />
        <Route path="/fantasy" element={<Fantasy />} />
        <Route path="/watchlist" element={<Navigate to="/fantasy" replace />} />
        <Route path="/trophies" element={<TrophyRaces />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/standings" element={<Standings />} />
        <Route path="/team/:abbrev" element={<Team />} />
      </Routes>
      <Freshness />
    </BrowserRouter>
  )
}
