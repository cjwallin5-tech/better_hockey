// Wording for international tournaments and results.

const FINAL_ONLY = new Set(['worldcup', 'fournations']) // a final and no bronze-medal game: the winner is a champion, the other finalist a runner-up

/** The tournament's name for one year: the World Cup of Hockey replaced the Canada Cup in 1996. */
export function tournamentName(a) {
  if (a.tournament === 'worldcup') return a.year < 1996 ? 'Canada Cup' : 'World Cup of Hockey'
  return a.label
}

/** "Gold", "Silver", "Bronze" for a medal, or "Champion" / "Runner-up" where there are no medals; "Played" for taking part. */
export function resultLabel(a) {
  if (!a.medal) return 'Played'
  if (FINAL_ONLY.has(a.tournament)) return a.medal === 'gold' ? 'Champion' : 'Runner-up'
  return a.medal[0].toUpperCase() + a.medal.slice(1)
}

/** "3 gold, 1 silver" for a { gold, silver, bronze } count, leaving out zeros; '' when there are none. */
export function medalText(m) {
  return ['gold', 'silver', 'bronze'].filter((k) => m[k] > 0).map((k) => `${m[k]} ${k}`).join(', ')
}

/** True when the tournament awards bronze medals. */
export const hasBronze = (tournamentId) => !FINAL_ONLY.has(tournamentId)
