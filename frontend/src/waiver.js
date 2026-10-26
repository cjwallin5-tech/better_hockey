// Waiver wire: players not on your roster, with the signals a pickup decision rests on. Everything here is plain
// functions so it can be tested; WaiverWire.jsx fetches the data and draws it.
//
// Value is the rest-of-season value over replacement from value.js / categories.js (it already pulls small samples
// toward the player's norm). The other columns say why a player might be worth a look right now: a bigger role, a
// hot stretch, results below what the shots support (likely to rebound), or a heavy week of games.
import { DEFAULT_LEAGUE, GROUPS, cleanLeague } from './value.js'

export const SORTS = [
  { id: 'value', label: 'Best value', hint: 'Value over the rest of the season in your league' },
  { id: 'form', label: 'Hottest', hint: 'Recent point pace (skaters) or goals saved above average (goalies)' },
  { id: 'role', label: 'Rising role', hint: 'Biggest jump in power-play or even-strength ice time' },
  { id: 'buy', label: 'Buy-low', hint: 'Results furthest below what the shots and chances support' },
  { id: 'games', label: 'Most games', hint: 'Games this week, then value' },
]

/** A player 2+ games out is probably hurt or scratched. */
export const HURT_GAMES = 2
/** A recent pace this far above the season pace counts as a hot stretch. */
export const HOT_FORM_RATIO = 1.25

/** Size of a role move for sorting: a power-play share change outweighs ice time, as on the Role changes page. */
export function roleSize(row) {
  if (!row || row.direction !== 'up') return 0
  return (row.pp_share_delta ?? 0) * 10 + (row.ev_delta ?? 0) / 300
}

/**
 * Candidate rows for one kind of player.
 *  values: Map id -> { value, group, groupRank, gp, team }   roles: Map id -> row from /api/roles/changes
 *  luck: Map id -> { z, flag, enough }   schedule: Map team -> { games, ratio } for the coming week
 *  Returns rows { id, name, team, position, group, value, groupRank, owned, hurt, gamesOut, form, pace, role,
 *  roleSize, luck, games, ratio, likelyOwned }, filtered and sorted.
 */
export function waiverRows({ kind, players, values, roles, luck, schedule, roster, league = DEFAULT_LEAGUE, filters = {}, sort = 'value' }) {
  const cfg = cleanLeague(league)
  const { position = 'all', likelyAvailable = false, hideHurt = false, search = '', minGp = 1 } = filters
  const q = search.trim().toLowerCase()
  const rows = []
  for (const p of players ?? []) {
    if (roster.has(p.player_id) || !p.games_played || p.games_played < minGp) continue
    const v = values.get(p.player_id)
    if (!v) continue
    if (position !== 'all' && (position === 'F' ? !['C', 'L', 'R'].includes(v.group) : v.group !== position)) continue
    if (q && !p.name.toLowerCase().includes(q)) continue
    const hurt = (p.games_out ?? 0) >= HURT_GAMES
    if (hideHurt && hurt) continue
    // the best players in each position are probably owned in a league of this size
    const likelyOwned = v.groupRank <= cfg.teams * cfg.slots[v.group]
    if (likelyAvailable && likelyOwned) continue
    const goalie = kind === 'goalie'
    const form = goalie ? p.recent_gsaa ?? null : p.recent_pace ?? null
    const pace = goalie ? null : p.point_pace ?? null
    const role = goalie ? null : roles.get(p.player_id) ?? null
    const l = luck.get(p.player_id)
    const sched = schedule.get(teamAbbrev(p.team))
    rows.push({
      id: p.player_id, name: p.name, team: teamAbbrev(p.team), position: goalie ? 'G' : p.position, group: v.group,
      value: v.value, groupRank: v.groupRank, gp: p.games_played, owned: false, hurt, gamesOut: p.games_out ?? 0,
      form, pace, hot: !goalie && form != null && pace != null && pace > 0 && form >= pace * HOT_FORM_RATIO,
      role, roleSize: roleSize(role),
      luck: l && l.enough ? l : null,
      games: sched?.games ?? null, ratio: sched?.ratio ?? null, likelyOwned,
    })
  }
  const cmp = {
    value: (a, b) => b.value - a.value,
    form: (a, b) => (b.form ?? -Infinity) - (a.form ?? -Infinity) || b.value - a.value,
    role: (a, b) => b.roleSize - a.roleSize || b.value - a.value,
    // lowest z first (furthest below what the shots support), but only players who are still worth owning
    buy: (a, b) => (a.luck?.z ?? Infinity) - (b.luck?.z ?? Infinity) || b.value - a.value,
    games: (a, b) => (b.games ?? -1) - (a.games ?? -1) || b.value - a.value,
  }[sort] ?? ((a, b) => b.value - a.value)
  let out = rows
  if (sort === 'role') out = out.filter((r) => r.roleSize > 0)
  if (sort === 'buy') out = out.filter((r) => r.luck && r.luck.flag === 'cold' && r.value > 0)
  if (sort === 'form') out = out.filter((r) => r.form != null)
  return out.sort((a, b) => cmp(a, b) || a.id - b.id)
}

/** The team a player is with now (a traded player's team is a comma list, latest last). */
export const teamAbbrev = (team) => (team ?? '').split(',').pop().trim()

/** Map team -> { games, ratio } from /api/matchups/schedule: games in the window and the average skater (or goalie) ratio. */
export function scheduleByTeam(schedule, kind = 'skater') {
  const key = kind === 'goalie' ? 'goalie_ratio' : 'skater_ratio'
  const out = new Map()
  for (const t of schedule?.teams ?? []) {
    const ratios = t.games.map((g) => g[key]).filter((x) => x != null)
    out.set(t.team, { games: t.games.length, ratio: ratios.length ? ratios.reduce((a, b) => a + b, 0) / ratios.length : null })
  }
  return out
}

/** Map id -> luck row for both ends of the luck list (the coldest and hottest players). */
export function luckById(...lists) {
  const out = new Map()
  for (const list of lists) for (const r of list?.rows ?? []) out.set(r.player_id, lumpLuck(r))
  return out
}

// Skaters' points luck against their own history when we have it (as the Luck badge does); goalies' goals saved vs expected.
function lumpLuck(r) {
  const z = r.points_z_adj ?? r.points_z ?? r.z_adj ?? r.z
  const flag = r.points_flag_adj ?? r.points_flag ?? r.flag_adj ?? r.flag
  return { z, flag, enough: Boolean(r.enough) }
}

export { GROUPS }
