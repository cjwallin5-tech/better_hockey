// The categories a category league (head-to-head or roto) can count. Kept apart from the maths so the league settings and the
// valuation agree on the names. `sign: -1` means lower is better. `rate` marks goalie ratios, which are valued by how many
// goals or saves they are worth over the season rather than as a total.
//
// `prior` is how many games' worth of average play to blend into an early-season rate for that stat. Goals, assists and points
// are handled separately (pulled toward a player's own record, backtested). The rest are NOT backtested (past seasons keep
// only goals and assists); they come from how noisy each stat is: a rate built from few games is mostly noise when the event
// is rare or driven by luck and teammates (shutouts, game-winning goals, plus/minus, wins), and steadier when it is a volume
// the player controls (shots, hits, blocks, and a goalie's saves, which follow his team's shots against).
export const SKATER_CATEGORIES = [
  { key: 'goals', label: 'Goals', short: 'G', sign: 1 },
  { key: 'assists', label: 'Assists', short: 'A', sign: 1 },
  { key: 'points', label: 'Points', short: 'P', sign: 1 },
  { key: 'plus_minus', label: 'Plus/minus', short: '+/-', sign: 1, prior: 30 },
  { key: 'pim', label: 'Penalty minutes', short: 'PIM', sign: 1, prior: 20 },
  { key: 'pp_points', label: 'Power-play points', short: 'PPP', sign: 1, prior: 25 },
  { key: 'sh_points', label: 'Short-handed points', short: 'SHP', sign: 1, prior: 60 },
  { key: 'game_winning_goals', label: 'Game-winning goals', short: 'GWG', sign: 1, prior: 100 },
  { key: 'shots', label: 'Shots on goal', short: 'SOG', sign: 1, prior: 8 },
  { key: 'hits', label: 'Hits', short: 'HIT', sign: 1, prior: 8 },
  { key: 'blocked_shots', label: 'Blocked shots', short: 'BLK', sign: 1, prior: 8 },
  { key: 'takeaways', label: 'Takeaways', short: 'TK', sign: 1, prior: 12 },
  { key: 'giveaways', label: 'Giveaways', short: 'GV', sign: -1, prior: 12 },
]

export const GOALIE_CATEGORIES = [
  { key: 'wins', label: 'Wins', short: 'W', sign: 1, prior: 60 },
  { key: 'saves', label: 'Saves', short: 'SV', sign: 1, prior: 8 },
  { key: 'shutouts', label: 'Shutouts', short: 'SO', sign: 1, prior: 150 },
  { key: 'losses', label: 'Losses', short: 'L', sign: -1, prior: 60 },
  { key: 'goals_against', label: 'Goals against', short: 'GA', sign: -1, prior: 8 },
  { key: 'gaa', label: 'Goals-against average', short: 'GAA', sign: -1, rate: true, prior: 8 },
  { key: 'save_pct', label: 'Save percentage', short: 'SV%', sign: 1, rate: true },
]

export const CATEGORY_PRESETS = {
  'Yahoo-style': {
    skater: ['goals', 'assists', 'plus_minus', 'pim', 'pp_points', 'shots', 'hits', 'blocked_shots'],
    goalie: ['wins', 'gaa', 'save_pct', 'shutouts'],
  },
  'Offense only': {
    skater: ['goals', 'assists', 'pp_points', 'shots'],
    goalie: ['wins', 'gaa', 'save_pct'],
  },
}

const known = (defs) => new Set(defs.map((d) => d.key))
const SKATER_KEYS = known(SKATER_CATEGORIES)
const GOALIE_KEYS = known(GOALIE_CATEGORIES)

/** { skater: [keys], goalie: [keys] } with only known categories, in the order the definitions list them. */
export function cleanCategories(raw) {
  const pick = (list, defs, keys) => (Array.isArray(list) ? defs.filter((d) => keys.has(d.key) && list.includes(d.key)).map((d) => d.key) : null)
  return {
    skater: pick(raw?.skater, SKATER_CATEGORIES, SKATER_KEYS) ?? [...CATEGORY_PRESETS['Yahoo-style'].skater],
    goalie: pick(raw?.goalie, GOALIE_CATEGORIES, GOALIE_KEYS) ?? [...CATEGORY_PRESETS['Yahoo-style'].goalie],
  }
}
