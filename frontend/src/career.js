// Helpers shared by the career section and the comparison page.
export const seasonLabel = (s) => `${String(s).slice(0, 4)}-${String(s).slice(6)}`

/** NHL regular-season totals per season (traded players' team rows summed), oldest first. */
export function nhlSeasons(seasons) {
  const byYear = new Map()
  for (const s of seasons) {
    if (s.leagueAbbrev !== 'NHL' || s.gameTypeId !== 2) continue
    const acc = byYear.get(s.season) ?? { season: s.season, teams: [], gp: 0, g: 0, a: 0, p: 0, w: 0, gs: 0, so: 0, sa: 0, ga: 0, toi: 0 }
    acc.teams.push(s.team)
    acc.gp += s.gamesPlayed ?? 0
    acc.g += s.goals ?? 0
    acc.a += s.assists ?? 0
    acc.p += s.points ?? 0
    acc.w += s.wins ?? 0
    acc.gs += s.gamesStarted ?? 0
    acc.so += s.shutouts ?? 0
    acc.sa += s.shotsAgainst ?? 0
    acc.ga += s.goalsAgainst ?? 0
    if (typeof s.timeOnIce === 'string' && s.timeOnIce.includes(':')) {
      const [m, sec] = s.timeOnIce.split(':').map(Number)
      acc.toi += m + sec / 60 // minutes
    }
    byYear.set(s.season, acc)
  }
  return [...byYear.values()].sort((x, y) => x.season - y.season)
}

/** Age at the start of a season (October 1 of its first year), from an ISO birth date. */
export function ageInSeason(birthDate, season) {
  if (!birthDate) return null
  const start = new Date(Math.floor(season / 10000), 9, 1)
  return Math.floor((start - new Date(`${birthDate}T00:00:00`)) / (365.25 * 24 * 3600 * 1000))
}

/** Save % and goals-against average for a (possibly multi-team) goalie season; null if unknown. */
export const seasonSvPct = (s) => (s.sa > 0 ? 1 - s.ga / s.sa : null)
export const seasonGaa = (s) => (s.toi > 0 ? (s.ga * 60) / s.toi : null)
