import { useEffect, useState } from 'react'
import HhofMark from '../components/HhofMark.jsx'
import BackLink from '../components/BackLink.jsx'
import { Navigate } from 'react-router-dom'
import Career from '../components/Career.jsx'
import PageTabs from '../components/PageTabs.jsx'
import PlayerBanner from '../components/PlayerBanner.jsx'
import Rankings, { rankNote } from '../components/Rankings.jsx'
import Comparables from '../components/Comparables.jsx'
import DefenseProfile from '../components/DefenseProfile.jsx'
import Awards from '../components/Awards.jsx'
import InternationalMedals from '../components/InternationalMedals.jsx'
import PageSkeleton from '../components/Skeleton.jsx'

const fmtSv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))
const fmt2 = (v) => (v == null ? '–' : v.toFixed(2))

/** First to last NHL season, e.g. "1990–2018", how many seasons that was (a traded season counts once), and the team they played the most games for. */
function careerSpan(seasons) {
  const nhl = (seasons ?? []).filter((x) => x.leagueAbbrev === 'NHL' && x.gameTypeId === 2)
  if (nhl.length === 0) return null
  const years = nhl.map((x) => x.season)
  const games = new Map()
  for (const x of nhl) games.set(x.team, (games.get(x.team) ?? 0) + (x.gamesPlayed ?? 0))
  const main = [...games.entries()].reduce((a, b) => (b[1] > a[1] ? b : a))[0]
  return { from: String(Math.min(...years)).slice(0, 4), to: String(Math.max(...years)).slice(4), count: new Set(years).size, main }
}

/**
 * Page for a player with no games in the current season (retired, or between seasons): bio and
 * career history from the NHL; the all-time ranks sit on the career tiles and in the More rankings table.
 * A current player is sent to their full page instead.
 */
export default function CareerPlayer({ id, goalie }) {
  const [result, setResult] = useState({ id: null, data: null, error: null })
  const [career, setCareer] = useState({ id: null, data: null })
  const [teams, setTeams] = useState([])

  useEffect(() => {
    fetch(`/api/players/${id}/profile`)
      .then((r) => {
        if (r.status === 404) throw new Error('Player not found')
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      })
      .then((data) => setResult({ id, data, error: null }))
      .catch((error) => setResult({ id, data: null, error: error.message }))
  }, [id])
  // The seasons give the years played and the main team (for the banner colour); both are extras, so a failure just leaves them out.
  useEffect(() => {
    fetch(`/api/players/${id}/career`).then((r) => (r.ok ? r.json() : null)).then((d) => setCareer({ id, data: d })).catch(() => setCareer({ id, data: null }))
    fetch('/api/teams').then((r) => (r.ok ? r.json() : [])).then(setTeams).catch(() => {})
  }, [id])

  const { data, error } = result.id === id ? result : { data: null, error: null }
  const back = <BackLink to={goalie ? '/alltime/goalies' : '/alltime/skaters'} />
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!data) return <main>{back}<PageSkeleton /></main>

  // A current player belongs on the full page for their role.
  if (data.current) return <Navigate to={`/${data.kind === 'goalie' ? 'goalie' : 'player'}/${id}`} replace />
  const wrongRoute = (data.kind === 'goalie') !== !!goalie
  if (wrongRoute) return <Navigate to={`/${data.kind === 'goalie' ? 'goalie' : 'player'}/${id}`} replace />

  const reg = data.ranks.regular ?? {}
  const isGoalie = data.kind === 'goalie'
  const status = data.active_season ? 'Not in the lineup this season' : 'Retired or inactive'
  const span = career.id === id && career.data ? careerSpan(career.data.seasons) : null
  const mainTeam = span ? teams.find((t) => t.name === span.main)?.abbrev : null
  const stat = (key, label, fmt = (v) => v.toLocaleString(), big = false) => ({
    label, big, value: reg[key] ? fmt(reg[key].value) : '–', rank: rankNote(reg[key], 'alltime'),
  })

  const meta = (
    <>
      {isGoalie ? 'G' : data.position} · {status}
      {span && ` · ${span.from}–${span.to} · ${span.count} NHL ${span.count === 1 ? 'season' : 'seasons'}`}
      {data.hall_of_fame && <HhofMark size={24} />}
    </>
  )
  const stats = isGoalie
    ? [stat('wins', 'Wins', undefined, true), stat('save_pct', 'Save %', fmtSv, true), stat('gaa', 'GAA', fmt2, true), stat('shutouts', 'Shutouts', undefined, true), stat('games_played', 'GP'), stat('saves', 'Saves')]
    : [stat('points', 'Points', undefined, true), stat('goals', 'Goals', undefined, true), stat('assists', 'Assists', undefined, true), stat('games_played', 'GP', undefined, true), stat('points_per_game', 'Points / game', fmt2), stat('plus_minus', '+/-')]

  return (
    <main>
      {back}
      <PlayerBanner p={{ player_id: id, name: data.name, team: mainTeam }} kind={data.kind} retired meta={meta} stats={stats} />

      <PageTabs
        tabs={[
          {
            id: 'career',
            label: 'Career',
            content: (
              <>
                <p className="sub">No games in the current season, so this page shows career history.</p>
                <Career playerId={id} />
                <Awards playerId={id} />
                <InternationalMedals playerId={id} />
                <Rankings playerId={id} kind={data.kind} careerOnly />
              </>
            ),
          },
          ...(isGoalie ? [] : [{
            id: 'compare',
            label: 'Comparables & defense',
            content: (
              <>
                <Comparables playerId={id} />
                <DefenseProfile playerId={id} />
              </>
            ),
          }]),
        ]}
      />
    </main>
  )
}
