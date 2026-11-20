// One loader per page, shared by the router and by hover prefetching, so a page is only ever downloaded once.
import { getJson } from './lists.js'

export const pages = {
  Players: () => import('./pages/Players.jsx'),
  Leaderboard: () => import('./pages/Leaderboard.jsx'),
  AllTime: () => import('./pages/AllTime.jsx'),
  Compare: () => import('./pages/CompareHub.jsx'),
  Game: () => import('./pages/Game.jsx'),
  Goalie: () => import('./pages/Goalie.jsx'),
  Goalies: () => import('./pages/Goalies.jsx'),
  Glossary: () => import('./pages/Glossary.jsx'),
  Player: () => import('./pages/Player.jsx'),
  ResetPassword: () => import('./pages/ResetPassword.jsx'),
  Awards: () => import('./pages/Awards.jsx'),
  History: () => import('./pages/History.jsx'),
  Roles: () => import('./pages/Roles.jsx'),
  Trophy: () => import('./pages/Trophy.jsx'),
  Account: () => import('./pages/Account.jsx'),
  Tonight: () => import('./pages/Tonight.jsx'),
  MyTeam: () => import('./pages/MyTeam.jsx'),
  League: () => import('./pages/League.jsx'),
  Prospects: () => import('./pages/DraftHub.jsx'),
  Prospect: () => import('./pages/Prospect.jsx'),
  Fantasy: () => import('./pages/FantasyHub.jsx'),
  Standings: () => import('./pages/Standings.jsx'),
  Team: () => import('./pages/Team.jsx'),
  News: () => import('./pages/News.jsx'),
}

const PATHS = {
  '/players': 'Players',
  '/skaters': 'Players',
  '/goalies': 'Players',
  '/glossary': 'Glossary',
  '/alltime/skaters': 'AllTime',
  '/alltime/goalies': 'AllTime',
  '/reset-password': 'ResetPassword',
  '/awards': 'Awards',
  '/history': 'History',
  '/roles': 'Roles',
  '/account': 'Account',
  '/fantasy': 'Fantasy',
  '/prospects': 'Prospects',
  '/games': 'Tonight',
  '/news': 'News',
  '/my-team': 'MyTeam',
  '/compare': 'Compare',
  '/standings': 'Standings',
}

// Pages that open by loading the big lists get them started on hover too.
const SKATERS = '/api/skaters'
const GOALIES = '/api/goalies'
const DATA = {
  '/players': [SKATERS], '/skaters': [SKATERS], '/goalies': [GOALIES], '/fantasy': [SKATERS, GOALIES], '/compare': [SKATERS, GOALIES],
}
const warmed = new Set()

/** Start downloading a page's code and data, for when someone points at a link to it. Harmless if it is never opened. */
export function warm(path) {
  if (warmed.has(path)) return
  warmed.add(path)
  pages[PATHS[path]]?.().catch(() => warmed.delete(path))
  DATA[path]?.forEach((url) => getJson(url).catch(() => {}))
}
