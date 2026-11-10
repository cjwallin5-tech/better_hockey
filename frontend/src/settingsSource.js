import { cleanLeague } from './value.js'

// Which scoring and league settings apply when a league is active. In order: the member's own settings for that league
// (league view `my_settings`), the settings the league's owner shared (`settings`), then the account-wide settings. The league's
// team count always applies. Pure, so it can be tested; settings.js is the hook around it.
//   source: 'personal' (no league active) | 'account' (a league is active but nothing is set for it) | 'shared' | 'own'
const has = (o) => !!o && Object.keys(o).length > 0

/** { scoring, league, source }; league is the raw league object the Fantasy page reads (see value.cleanLeague). */
export function leagueSettings({ personalScoring, personalLeague, view }) {
  if (!view) return { scoring: personalScoring, league: personalLeague, source: 'personal' }
  const shared = view.settings ?? {}
  const own = view.my_settings ?? null
  const source = has(own) ? 'own' : has(shared) ? 'shared' : 'account'
  const pick = (s) => Object.fromEntries(['format', 'categories'].filter((k) => s?.[k] != null).map((k) => [k, s[k]]))
  const league = {
    ...personalLeague,
    teams: own?.teams ?? view.teams_allowed,
    ...pick(shared),
    ...pick(own),
    slots: { ...personalLeague?.slots, ...shared.slots, ...own?.slots },
  }
  return { scoring: own?.scoring ?? shared.scoring ?? personalScoring, league, source }
}

// What gets saved as the member's own settings: everything that applies now (so later changes to the account-wide or shared
// settings don't shift this league), with the one edited part replaced.
const snapshot = (eff) => {
  const c = cleanLeague(eff.league)
  return { scoring: eff.scoring, teams: c.teams, format: c.format, slots: c.slots, categories: c.categories }
}

export function withScoring(eff, view, scoring) {
  return { ...(view.my_settings ?? snapshot(eff)), scoring }
}

export function withLeague(eff, view, next) {
  const c = cleanLeague(next)
  return { ...(view.my_settings ?? snapshot(eff)), teams: c.teams, format: c.format, slots: c.slots, categories: c.categories }
}
