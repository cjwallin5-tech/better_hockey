// One loader per page, shared by the router and by hover prefetching, so a page is only ever downloaded once.
import { getJson } from './lists.js'

export const pages = {
  Leaderboard: () => import('./pages/Leaderboard.jsx'),
  AllTime: () => import('./pages/AllTime.jsx'),
  Compare: () => import('./pages/CompareHub.jsx'),
  AdvancedStats: () => import('./pages/AdvancedStats.jsx'),
  Game: () => import('./pages/Game.jsx'),
  Goalie: () => import('./pages/Goalie.jsx'),
  Goalies: () => import('./pages/Goalies.jsx'),
  Milestones: () => import('./pages/Milestones.jsx'),
  Player: () => import('./pages/Player.jsx'),
  ResetPassword: () => import('./pages/ResetPassword.jsx'),
  Schedule: () => import('./pages/Schedule.jsx'),
  Awards: () => import('./pages/Awards.jsx'),
  Matchups: () => import('./pages/Matchups.jsx'),
  Roles: () => import('./pages/Roles.jsx'),
  Trophy: () => import('./pages/Trophy.jsx'),
  Account: () => import('./pages/Account.jsx'),
  Watchlist: () => import('./pages/Watchlist.jsx'),
  Projections: () => import('./pages/ProjectionsHub.jsx'),
  Tonight: () => import('./pages/Tonight.jsx'),
  MyTeam: () => import('./pages/MyTeam.jsx'),
  Leagues: () => import('./pages/Leagues.jsx'),
  Accuracy: () => import('./pages/Accuracy.jsx'),
  Absences: () => import('./pages/Absences.jsx'),
  League: () => import('./pages/League.jsx'),
  Prospects: () => import('./pages/Prospects.jsx'),
  Prospect: () => import('./pages/Prospect.jsx'),
  Lottery: () => import('./pages/Lottery.jsx'),
  Fantasy: () => import('./pages/Fantasy.jsx'),
  Standings: () => import('./pages/Standings.jsx'),
  Team: () => import('./pages/Team.jsx'),
}

const PATHS = {
  '/skaters': 'Leaderboard',
  '/goalies': 'Goalies',
  '/milestones': 'Milestones',
  '/alltime/skaters': 'AllTime',
  '/alltime/goalies': 'AllTime',
  '/reset-password': 'ResetPassword',
  '/schedule': 'Schedule',
  '/awards': 'Awards',
  '/advanced-stats': 'AdvancedStats',
  '/roles': 'Roles',
  '/matchups': 'Matchups',
  '/account': 'Account',
  '/fantasy': 'Fantasy',
  '/lottery': 'Lottery',
  '/prospects': 'Prospects',
  '/projections': 'Projections',
  '/tonight': 'Tonight',
  '/my-team': 'MyTeam',
  '/leagues': 'Leagues',
  '/accuracy': 'Accuracy',
  '/absences': 'Absences',
  '/watchlist': 'Watchlist',
  '/compare': 'Compare',
  '/standings': 'Standings',
}

// Pages that open by loading the big lists get them started on hover too.
const SKATERS = '/api/skaters'
const GOALIES = '/api/goalies'
const DATA = {
  '/skaters': [SKATERS], '/goalies': [GOALIES], '/fantasy': [SKATERS, GOALIES], '/compare': [SKATERS, GOALIES],
  '/watchlist': [SKATERS, GOALIES], '/schedule': [SKATERS, GOALIES], '/leagues': [SKATERS, GOALIES],
}
const warmed = new Set()

/** Start downloading a page's code and data, for when someone points at a link to it. Harmless if it is never opened. */
export function warm(path) {
  if (warmed.has(path)) return
  warmed.add(path)
  pages[PATHS[path]]?.().catch(() => warmed.delete(path))
  DATA[path]?.forEach((url) => getJson(url).catch(() => {}))
}
