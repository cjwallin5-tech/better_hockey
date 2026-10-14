import { useEffect } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom'
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
import Account from './pages/Account.jsx'
import { initAuth, useAuth } from './auth.js'
import Fantasy from './pages/Fantasy.jsx'
import Standings from './pages/Standings.jsx'
import TrophyRaces from './pages/TrophyRaces.jsx'
import Team from './pages/Team.jsx'
import NavMore from './components/NavMore.jsx'
import Freshness from './components/Freshness.jsx'

export default function App() {
  const { dark, toggle } = useTheme()
  const { user } = useAuth()
  useEffect(initAuth, [])
  return (
    <BrowserRouter>
      <nav className="topnav">
        <NavLink to="/" end>Home</NavLink>
        <NavLink to="/skaters">Skaters</NavLink>
        <NavLink to="/goalies">Goalies</NavLink>
        <NavLink to="/standings">Standings</NavLink>
        <NavLink to="/alltime">All-time</NavLink>
        <NavLink to="/milestones">Milestones</NavLink>
        <NavLink to="/trophies">Trophies</NavLink>
        <NavLink to="/compare">Compare</NavLink>
        <NavMore items={[['/milestones', 'Milestones'], ['/trophies', 'Trophy races'], ['/schedule', 'Schedule grid']]} />
        <NavLink to="/fantasy">★ Fantasy team</NavLink>
        <NavLink to="/account">{user ? user.email : 'Log in'}</NavLink>
        <button className="theme-toggle" onClick={toggle} aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'} title={dark ? 'Switch to light theme' : 'Switch to dark theme'}>
          {dark ? '☀ Light' : '☾ Dark'}
        </button>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/skaters" element={<Leaderboard />} />
        <Route path="/player/:id" element={<Player />} />
        <Route path="/goalies" element={<Goalies />} />
        <Route path="/goalie/:id" element={<Goalie />} />
        <Route path="/milestones" element={<Milestones />} />
        <Route path="/alltime" element={<AllTime />} />
        <Route path="/game/:id" element={<Game />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/schedule" element={<ScheduleGrid />} />
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
