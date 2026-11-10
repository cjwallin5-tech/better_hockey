/**
 * Search results with who owns each player in the active league. `taken` is leagues.takenByOthers(league): a Map of player id to the
 * name of the team holding him, or null with no league. Each row gets `ownedBy` (a team name or null), and players nobody holds come
 * first (order otherwise kept), so a league-mate's star can't push the available players out of a short list.
 */
export function markOwners(rows, taken) {
  if (!taken) return rows
  const marked = rows.map((r) => ({ ...r, ownedBy: taken.get(r.player_id) ?? null }))
  return [...marked.filter((r) => !r.ownedBy), ...marked.filter((r) => r.ownedBy)]
}
