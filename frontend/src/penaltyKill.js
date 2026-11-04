import { fmtToi } from './format.js'

// A skater's penalty-kill role, from the NHL's short-handed ice time: the share of the team's penalty-kill minutes the player is on the
// ice for (a top unit kills about half or more of them, a second unit about a third), and minutes a game as a floor so a handful of
// shifts is not called a role. Same idea as the power-play units in roles.py.
export const PK1_SHARE = 0.5
export const PK2_SHARE = 0.3
export const MIN_PK_SEC = 60   // short-handed seconds a game for it to count
export const MIN_PK_GAMES = 5

/** { unit: 'PK1' | 'PK2', share, perGame } for a skater who kills penalties, or null. p needs sh_toi_pct, sh_toi_per_game and games_played. */
export function pkRole(p) {
  if (!p || p.sh_toi_pct == null || p.sh_toi_per_game == null) return null
  if ((p.games_played ?? 0) < MIN_PK_GAMES || p.sh_toi_per_game < MIN_PK_SEC) return null
  const unit = p.sh_toi_pct >= PK1_SHARE ? 'PK1' : p.sh_toi_pct >= PK2_SHARE ? 'PK2' : null
  return unit && { unit, share: p.sh_toi_pct, perGame: p.sh_toi_per_game }
}

/** The sentence for a tag's tooltip, e.g. "Top penalty-kill unit: 3:42 a game, on the ice for 60% of the team's penalty kill". */
export function pkDetail(role) {
  const lead = role.unit === 'PK1' ? 'Top penalty-kill unit' : 'Second penalty-kill unit'
  return `${lead}: ${fmtToi(role.perGame)} a game, on the ice for ${Math.round(role.share * 100)}% of the team's penalty kill`
}
