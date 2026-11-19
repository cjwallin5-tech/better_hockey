import { lazy, Suspense, useEffect, useLayoutEffect, useState } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import Home from './pages/Home.jsx'
import { initAuth, useAuth } from './auth.js'
import NavMore from './components/NavMore.jsx'
import Freshness from './components/Freshness.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import GlobalSearch from './components/GlobalSearch.jsx'
import { pages, warm } from './routes.js'
import PageSkeleton from './components/Skeleton.jsx'
import { usePageTitle } from './pageTitle.js'
import GlossaryTips from './components/GlossaryTips.jsx'
import { installTabScroll } from './tabScroll.js'

// Pages load on demand, so the first visit downloads the shell and the page you opened, not all of the site.
const Players = lazy(pages.Players)
const AllTime = lazy(pages.AllTime)
const Compare = lazy(pages.Compare)
const Game = lazy(pages.Game)
const Goalie = lazy(pages.Goalie)
const Glossary = lazy(pages.Glossary)
const Player = lazy(pages.Player)
const ResetPassword = lazy(pages.ResetPassword)
const Schedule = lazy(pages.Schedule)
const Awards = lazy(pages.Awards)
const History = lazy(pages.History)
const Roles = lazy(pages.Roles)
const Trophy = lazy(pages.Trophy)
const Account = lazy(pages.Account)
const Matchups = lazy(pages.Matchups)
const Tonight = lazy(pages.Tonight)
const MyTeam = lazy(pages.MyTeam)
const League = lazy(pages.League)
const Prospects = lazy(pages.Prospects)
const Prospect = lazy(pages.Prospect)
const Fantasy = lazy(pages.Fantasy)
const Standings = lazy(pages.Standings)
const Team = lazy(pages.Team)
const News = lazy(pages.News)

/** Old /alltime links: send them to the skater or goalie page, keeping any filters in the query. */
function AllTimeRedirect() {
  const params = new URLSearchParams(useLocation().search)
  const goalie = params.get('kind') === 'goalie'
  params.delete('kind')
  const query = params.toString()
  return <Navigate to={`/alltime/${goalie ? 'goalies' : 'skaters'}${query ? `?${query}` : ''}`} replace />
}

/** Old /best-seasons links: the best seasons are now views of the all-time page, so keep the query and map the old view names. */
const OLD_BEST_VIEWS = { scoring: 'bestScoring', adjusted: 'bestAdjusted', defense: 'bestDefense', record: 'bestRecord', saves: 'bestSaves' }
function BestSeasonsRedirect({ goalie }) {
  const params = new URLSearchParams(useLocation().search)
  const old = params.get('v')
  params.set('v', OLD_BEST_VIEWS[old] ?? (goalie ? 'bestRecord' : 'bestScoring'))
  return <Navigate to={`/alltime/${goalie ? 'goalies' : 'skaters'}?${params}`} replace />
}

/** A moved page: send the old address to the new one with its query (a chosen date, say) intact, plus any `set` parameters. */
function RedirectKeepQuery({ to, set }) {
  const params = new URLSearchParams(useLocation().search)
  for (const [key, value] of Object.entries(set ?? {})) params.set(key, value)
  const query = params.toString()
  return <Navigate to={`${to}${query ? `?${query}` : ''}`} replace />
}

/** An old page's address, sent to its tab on the merged page, keeping any query (a link's filters or players) after the tab. */
function RedirectToTab({ to, tab, param = 'tab' }) {
  const { search } = useLocation()
  const rest = search.replace(/^\?/, '')
  return <Navigate to={`${to}?${param}=${tab}${rest ? `&${rest}` : ''}`} replace />
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
          <Route path="/players" element={<Players />} />
          <Route path="/skaters" element={<RedirectKeepQuery to="/players" />} />
          <Route path="/player/:id" element={<Player />} />
          <Route path="/goalies" element={<RedirectKeepQuery to="/players" set={{ kind: 'goalie' }} />} />
          <Route path="/goalie/:id" element={<Goalie />} />
          <Route path="/milestones" element={<RedirectToTab to="/awards" tab="milestones" />} />
          <Route path="/glossary" element={<Glossary />} />
          <Route path="/alltime" element={<AllTimeRedirect />} />
          <Route path="/alltime/skaters" element={<AllTime key="skater" kind="skater" />} />
          <Route path="/alltime/goalies" element={<AllTime key="goalie" kind="goalie" />} />
          <Route path="/best-seasons/skaters" element={<BestSeasonsRedirect />} />
          <Route path="/best-seasons/goalies" element={<BestSeasonsRedirect goalie />} />
          <Route path="/game/:id" element={<Game />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/schedule" element={<Schedule />} />
          <Route path="/schedule-strength" element={<RedirectToTab to="/schedule" tab="strength" />} />
          <Route path="/rest" element={<RedirectToTab to="/schedule" tab="rest" />} />
          <Route path="/advanced-stats" element={<Navigate to="/standings" replace />} />
          <Route path="/special-teams" element={<Navigate to="/standings?stat=pp_xgf60" replace />} />
          <Route path="/score-effects" element={<Navigate to="/standings?stat=xg_pct_adj" replace />} />
          <Route path="/tracking" element={<Navigate to="/players?view=speed" replace />} />
          <Route path="/head-to-head" element={<RedirectToTab to="/compare" tab="head-to-head" />} />
          <Route path="/luck" element={<Navigate to="/players" replace />} />
          <Route path="/roles" element={<Roles />} />
          <Route path="/matchups" element={<Matchups />} />
          <Route path="/awards" element={<Awards />} />
          <Route path="/history" element={<History />} />
          <Route path="/trophy" element={<RedirectToTab to="/awards" tab="winners" />} />
          <Route path="/trophies" element={<Navigate to="/awards" replace />} />
          <Route path="/trophy/:id" element={<Trophy />} />
          <Route path="/account" element={<Account />} />
          <Route path="/fantasy" element={<Fantasy />} />
          <Route path="/lottery" element={<RedirectToTab to="/prospects" tab="lottery" />} />
          <Route path="/prospects" element={<Prospects />} />
          <Route path="/prospect/:id" element={<Prospect />} />
          <Route path="/projections" element={<Navigate to="/players" replace />} />
          <Route path="/games" element={<Tonight />} />
          <Route path="/tonight" element={<RedirectKeepQuery to="/games" />} />
          <Route path="/my-team" element={<MyTeam />} />
          <Route path="/leagues" element={<RedirectToTab to="/fantasy" param="section" tab="leagues" />} />
          <Route path="/absences" element={<Navigate to="/players" replace />} />
          <Route path="/league/:id" element={<League />} />
          <Route path="/watchlist" element={<RedirectToTab to="/fantasy" param="section" tab="watchlist" />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/standings" element={<Standings />} />
          <Route path="/team/:abbrev" element={<Team />} />
          <Route path="/news" element={<News />} />
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

const MAIN_LINKS = [['/players', 'Players'], ['/standings', 'Standings'], ['/fantasy', 'Fantasy'], ['/games', 'Games'], ['/news', 'News'], ['/my-team', 'My team']]
// The less-used pages, in two even columns.
const moreGroups = (user) => [
  { title: 'Players', items: [['/compare', 'Compare'], ['/prospects', 'Prospects & draft'], ['/awards', 'Awards & milestones'], ['/history', 'NHL history']] },
  { title: 'League & stats', items: [['/schedule', 'Schedule'], ['/matchups', 'Matchups'], ['/glossary', 'Glossary']] },
]

/** The top bar. Wide screens get the full link row; phones get the logo, search and a menu button that opens every page. */
function TopBar({ user }) {
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()
  useEffect(() => { setOpen(false) }, [pathname])
  const groups = moreGroups(user)
  return (
    <header className="topbar" onPointerOver={warmLink} onFocus={warmLink}>
      <nav className="topnav">
        <NavLink to="/" end className="brand" aria-label="Faceoff home">
          <svg className="brand-mark" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="2.6" fill="currentColor" stroke="none" /><path d="M12 1.5v4M12 18.5v4M1.5 12h4M18.5 12h4" strokeLinecap="round" /></svg>
          <span>FACE<b>OFF</b></span>
        </NavLink>
        <div className="nav-wide">
          {MAIN_LINKS.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
          <NavMore groups={groups} />
        </div>
        <GlobalSearch />
        <div className="nav-wide">
          <NavLink to="/account" className="nav-account">{user ? user.email : 'Log in'}</NavLink>
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
            </div>
        </div>
      )}
    </header>
  )
}

export default function App() {
  const { user } = useAuth()
  useEffect(initAuth, [])
  useEffect(() => installTabScroll(), [])   // fades and scroll-into-view for tab rows that scroll sideways on a phone
  return (
    <BrowserRouter>
      <TopBar user={user} />
      <ScrollToTop />
      <Pages />
      <GlossaryTips />
      <Freshness />
    </BrowserRouter>
  )
}
