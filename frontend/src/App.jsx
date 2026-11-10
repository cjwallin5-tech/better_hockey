import { lazy, Suspense, useEffect, useLayoutEffect, useState } from 'react'
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
import { usePageTitle } from './pageTitle.js'
import { installTabScroll } from './tabScroll.js'

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
const Schedule = lazy(pages.Schedule)
const Awards = lazy(pages.Awards)
const AdvancedStats = lazy(pages.AdvancedStats)
const Matchups = lazy(pages.Matchups)
const Roles = lazy(pages.Roles)
const Trophy = lazy(pages.Trophy)
const Account = lazy(pages.Account)
const Watchlist = lazy(pages.Watchlist)
const Projections = lazy(pages.Projections)
const Tonight = lazy(pages.Tonight)
const MyTeam = lazy(pages.MyTeam)
const Leagues = lazy(pages.Leagues)
const Accuracy = lazy(pages.Accuracy)
const Absences = lazy(pages.Absences)
const League = lazy(pages.League)
const Prospects = lazy(pages.Prospects)
const Prospect = lazy(pages.Prospect)
const Lottery = lazy(pages.Lottery)
const Fantasy = lazy(pages.Fantasy)
const Standings = lazy(pages.Standings)
const Team = lazy(pages.Team)

/** Old /alltime links: send them to the skater or goalie page, keeping any filters in the query. */
function AllTimeRedirect() {
  const params = new URLSearchParams(useLocation().search)
  const goalie = params.get('kind') === 'goalie'
  params.delete('kind')
  const query = params.toString()
  return <Navigate to={`/alltime/${goalie ? 'goalies' : 'skaters'}${query ? `?${query}` : ''}`} replace />
}

/** An old page's address, sent to its tab on the merged page, keeping any query (a link's filters or players) after the tab. */
function RedirectToTab({ to, tab }) {
  const { search } = useLocation()
  const rest = search.replace(/^\?/, '')
  return <Navigate to={`${to}?tab=${tab}${rest ? `&${rest}` : ''}`} replace />
}

/** The routes, wrapped so a crash on one page shows a message, and moving to another page clears it. */
function Pages() {
  const { pathname } = useLocation()
  usePageTitle()
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
          <Route path="/schedule" element={<Schedule />} />
          <Route path="/schedule-strength" element={<RedirectToTab to="/schedule" tab="strength" />} />
          <Route path="/rest" element={<RedirectToTab to="/schedule" tab="rest" />} />
          <Route path="/advanced-stats" element={<AdvancedStats />} />
          <Route path="/special-teams" element={<RedirectToTab to="/advanced-stats" tab="special-teams" />} />
          <Route path="/score-effects" element={<RedirectToTab to="/advanced-stats" tab="score-effects" />} />
          <Route path="/tracking" element={<RedirectToTab to="/advanced-stats" tab="tracking" />} />
          <Route path="/head-to-head" element={<RedirectToTab to="/compare" tab="head-to-head" />} />
          <Route path="/luck" element={<RedirectToTab to="/projections" tab="luck" />} />
          <Route path="/roles" element={<Roles />} />
          <Route path="/matchups" element={<Matchups />} />
          <Route path="/awards" element={<Awards />} />
          <Route path="/trophy" element={<RedirectToTab to="/awards" tab="winners" />} />
          <Route path="/trophies" element={<Navigate to="/awards" replace />} />
          <Route path="/trophy/:id" element={<Trophy />} />
          <Route path="/account" element={<Account />} />
          <Route path="/fantasy" element={<Fantasy />} />
          <Route path="/lottery" element={<Lottery />} />
          <Route path="/prospects" element={<Prospects />} />
          <Route path="/prospect/:id" element={<Prospect />} />
          <Route path="/projections" element={<Projections />} />
          <Route path="/tonight" element={<Tonight />} />
          <Route path="/my-team" element={<MyTeam />} />
          <Route path="/leagues" element={<Leagues />} />
          <Route path="/accuracy" element={<Accuracy />} />
          <Route path="/absences" element={<Absences />} />
          <Route path="/league/:id" element={<League />} />
          <Route path="/watchlist" element={<Watchlist />} />
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

const MAIN_LINKS = [['/skaters', 'Skaters'], ['/goalies', 'Goalies'], ['/standings', 'Standings'], ['/fantasy', 'Fantasy'], ['/tonight', 'Tonight'], ['/my-team', 'My team']]
// The less-used pages, grouped so the menu reads as four short lists instead of one long one.
const moreGroups = (user) => [
  { title: 'Players', items: [['/compare', 'Compare'], ['/prospects', 'Prospects'], ['/milestones', 'Milestones'], ['/absences', 'Who\u2019s out']] },
  { title: 'Fantasy tools', items: [['/watchlist', 'Watchlist'], ['/leagues', 'Leagues'], ['/projections', 'Projections'], ['/matchups', 'Matchups']] },
  { title: 'League', items: [['/schedule', 'Schedule'], ['/lottery', 'Draft lottery'], ['/advanced-stats', 'Advanced stats'], ['/awards', 'Awards'], ...(user?.admin ? [['/accuracy', 'Accuracy']] : [])] },
]

/** The top bar. Wide screens get the full link row; phones get the logo, search and a menu button that opens every page. */
function TopBar({ dark, toggle, user }) {
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()
  useEffect(() => { setOpen(false) }, [pathname])
  const groups = moreGroups(user)
  const theme = (
    <button className="theme-toggle" onClick={toggle} aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'} title={dark ? 'Switch to light theme' : 'Switch to dark theme'}>
      <Icon name={dark ? 'sun' : 'moon'} /> {dark ? 'Light' : 'Dark'}
    </button>
  )
  return (
    <header className="topbar" onPointerOver={warmLink} onFocus={warmLink}>
      <nav className="topnav">
        <NavLink to="/" end className="brand" aria-label="NHL Stats home">
          <svg className="brand-mark" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="2.6" fill="currentColor" stroke="none" /><path d="M12 1.5v4M12 18.5v4M1.5 12h4M18.5 12h4" strokeLinecap="round" /></svg>
          <span>NHL<b>STATS</b></span>
        </NavLink>
        <div className="nav-wide">
          {MAIN_LINKS.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
          <NavMore groups={groups} />
        </div>
        <GlobalSearch />
        <div className="nav-wide">
          <NavLink to="/account" className="nav-account">{user ? user.email : 'Log in'}</NavLink>
          {theme}
        </div>
        <button type="button" className="nav-menu-btn" aria-expanded={open} aria-label={open ? 'Close menu' : 'Open menu'} onClick={() => setOpen(!open)}>
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
        </button>
      </nav>
      {open && (
        <div className="nav-panel">
          <div className="nav-panel-grid">
            {MAIN_LINKS.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
          </div>
          {groups.map((g) => (
            <div key={g.title}>
              <div className="eyebrow">{g.title}</div>
              <div className="nav-panel-grid small">
                {g.items.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
              </div>
            </div>
          ))}
          <div className="nav-panel-foot">
            <NavLink to="/account" className="nav-account">{user ? user.email : 'Log in'}</NavLink>
            {theme}
          </div>
        </div>
      )}
    </header>
  )
}

export default function App() {
  const { dark, toggle } = useTheme()
  const { user } = useAuth()
  useEffect(initAuth, [])
  useEffect(() => installTabScroll(), [])   // fades and scroll-into-view for tab rows that scroll sideways on a phone
  return (
    <BrowserRouter>
      <TopBar dark={dark} toggle={toggle} user={user} />
      <ScrollToTop />
      <Pages />
      <Freshness />
    </BrowserRouter>
  )
}
