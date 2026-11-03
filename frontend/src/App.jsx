import { lazy, Suspense, useEffect, useLayoutEffect } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { useTheme } from './theme.js'
import Home from './pages/Home.jsx'
import { initAuth, useAuth } from './auth.js'
import NavMore from './components/NavMore.jsx'
import Freshness from './components/Freshness.jsx'
import Icon from './components/Icon.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import GlobalSearch from './components/GlobalSearch.jsx'
import { pages, warm } from './routes.js'
import PageSkeleton from './components/Skeleton.jsx'

// Pages load on demand, so the first visit downloads the shell and the page you opened, not all of the site.
const Leaderboard = lazy(pages.Leaderboard)
const AllTime = lazy(pages.AllTime)
const Compare = lazy(pages.Compare)
const Game = lazy(pages.Game)
const Goalie = lazy(pages.Goalie)
const Goalies = lazy(pages.Goalies)
const Milestones = lazy(pages.Milestones)
const Player = lazy(pages.Player)
const ResetPassword = lazy(pages.ResetPassword)
const ScheduleGrid = lazy(pages.ScheduleGrid)
const HeadToHead = lazy(pages.HeadToHead)
const Tracking = lazy(pages.Tracking)
const Luck = lazy(pages.Luck)
const Matchups = lazy(pages.Matchups)
const Roles = lazy(pages.Roles)
const Trophy = lazy(pages.Trophy)
const TrophyIndex = lazy(pages.TrophyIndex)
const Account = lazy(pages.Account)
const Watchlist = lazy(pages.Watchlist)
const Projections = lazy(pages.Projections)
const Tonight = lazy(pages.Tonight)
const MyTeam = lazy(pages.MyTeam)
const Leagues = lazy(pages.Leagues)
const Accuracy = lazy(pages.Accuracy)
const Absences = lazy(pages.Absences)
const League = lazy(pages.League)
const Rest = lazy(pages.Rest)
const Prospects = lazy(pages.Prospects)
const Prospect = lazy(pages.Prospect)
const SpecialTeams = lazy(pages.SpecialTeams)
const ScoreEffects = lazy(pages.ScoreEffects)
const ScheduleStrength = lazy(pages.ScheduleStrength)
const Lottery = lazy(pages.Lottery)
const Fantasy = lazy(pages.Fantasy)
const Standings = lazy(pages.Standings)
const TrophyRaces = lazy(pages.TrophyRaces)
const Team = lazy(pages.Team)

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
      <Suspense fallback={<main><PageSkeleton /></main>}>
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
        <Route path="/score-effects" element={<ScoreEffects />} />
        <Route path="/schedule-strength" element={<ScheduleStrength />} />
        <Route path="/lottery" element={<Lottery />} />
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
      </Suspense>
      </ErrorBoundary>
  )
}

// A new page opens at its top. Only the path counts: changing a tab or a filter (the query string) on the same page keeps your place.
function ScrollToTop() {
  const { pathname } = useLocation()
  useLayoutEffect(() => { window.scrollTo(0, 0) }, [pathname])
  return null
}

// Pointing at (or tabbing to) a link in the top bar starts loading its page.
function warmLink(e) {
  const a = e.target.closest?.('a[href^="/"]')
  if (a) warm(new URL(a.href).pathname)
}

export default function App() {
  const { dark, toggle } = useTheme()
  const { user } = useAuth()
  useEffect(initAuth, [])
  return (
    <BrowserRouter>
      <header className="topbar" onPointerOver={warmLink} onFocus={warmLink}>
      <nav className="topnav">
        <NavLink to="/" end className="brand" aria-label="NHL Stats home">NHL<b>STATS</b></NavLink>
        <NavLink to="/skaters">Skaters</NavLink>
        <NavLink to="/goalies">Goalies</NavLink>
        <NavLink to="/standings">Standings</NavLink>
        <NavLink to="/fantasy">Fantasy</NavLink>
        <NavLink to="/tonight">Tonight</NavLink>
        <NavLink to="/my-team">My team</NavLink>
        <NavMore items={[...(user?.admin ? [['/accuracy', 'Accuracy']] : []), ['/compare', 'Compare'], ['/absences', 'Who\u2019s out'], ['/prospects', 'Prospects'], ['/leagues', 'Leagues'], ['/watchlist', 'Watchlist'], ['/milestones', 'Milestones'], ['/trophies', 'Trophy races'], ['/trophy', 'Trophy winners'], ['/schedule', 'Schedule grid'], ['/schedule-strength', 'Schedule strength'], ['/lottery', 'Draft lottery'], ['/rest', 'Back-to-backs'], ['/special-teams', 'Special teams'], ['/score-effects', 'Score effects'], ['/head-to-head', 'Head-to-head'], ['/tracking', 'Speed & shots'], ['/projections', 'Projections'], ['/luck', 'Luck & regression'], ['/matchups', 'Matchups']]} />
        <GlobalSearch />
        <NavLink to="/account" className="nav-account">{user ? user.email : 'Log in'}</NavLink>
        <button className="theme-toggle" onClick={toggle} aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'} title={dark ? 'Switch to light theme' : 'Switch to dark theme'}>
          <Icon name={dark ? 'sun' : 'moon'} /> {dark ? 'Light' : 'Dark'}
        </button>
      </nav>
      </header>
      <ScrollToTop />
      <Pages />
      <Freshness />
    </BrowserRouter>
  )
}
