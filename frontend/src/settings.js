import { useCallback, useMemo } from 'react'
import { useLeague as usePersonalLeague, useScoring as usePersonalScoring } from './fantasy.js'
import { updateMySettings, useLeagues } from './leagues.js'
import { leagueSettings, withLeague, withScoring } from './settingsSource.js'

// Scoring and league settings (format, slots, teams, categories) with the same shape as the hooks in fantasy.js, but following the
// active league: your own settings for it, else the ones its owner shared, else your account-wide ones (see settingsSource.js).
// Changes made while a league is active are saved for that league only; with none active they go to the account-wide settings.
// Changes are ignored while the leagues load, so an edit can't land on the wrong set.
function useSettings() {
  const ps = usePersonalScoring()
  const pl = usePersonalLeague()
  const leagues = useLeagues()
  const loading = leagues.signedIn && leagues.status !== 'ready' && leagues.status !== 'error'
  const view = leagues.signedIn && leagues.status === 'ready' ? leagues.active : null
  const eff = useMemo(
    () => leagueSettings({ personalScoring: ps.scoring, personalLeague: pl.league, view }),
    [ps.scoring, pl.league, view],
  )
  return { ps, pl, view, eff, loading, personal: { personalScoring: ps.scoring, personalLeague: pl.league } }
}

/** { scoring, setScoring, source, leagueName }: source is 'personal' | 'account' | 'shared' | 'own'. */
export function useScoring() {
  const { ps, view, eff, loading, personal } = useSettings()
  const setScoring = useCallback((next) => {
    if (loading) return
    if (view) updateMySettings((v) => withScoring(leagueSettings({ ...personal, view: v }), v, next))
    else ps.setScoring(next)
  }, [loading, view, ps, personal])
  return { scoring: eff.scoring, setScoring, source: eff.source, leagueName: view?.name ?? null }
}

/** { league, setLeague, source, leagueName }: league is the raw settings object (see value.cleanLeague). */
export function useLeague() {
  const { pl, view, eff, loading, personal } = useSettings()
  const setLeague = useCallback((next) => {
    if (loading) return
    if (view) updateMySettings((v) => withLeague(leagueSettings({ ...personal, view: v }), v, next))
    else pl.setLeague(next)
  }, [loading, view, pl, personal])
  return { league: eff.league, setLeague, source: eff.source, leagueName: view?.name ?? null }
}
