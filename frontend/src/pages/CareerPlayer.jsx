import { useEffect, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import Career from '../components/Career.jsx'
import { RankCards } from '../components/Rankings.jsx'
import Comparables from '../components/Comparables.jsx'
import DefenseProfile from '../components/DefenseProfile.jsx'

/**
 * Page for a player with no games in the current season (retired, or between seasons): bio and
 * career history from the NHL, plus where their career ranks among every player in NHL history.
 * A current player is sent to their full page instead.
 */
export default function CareerPlayer({ id, goalie }) {
  const [result, setResult] = useState({ id: null, data: null, error: null })
  const [kind, setKind] = useState('regular')

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

  const { data, error } = result.id === id ? result : { data: null, error: null }
  const back = <Link to="/alltime" className="back">← All-time leaders</Link>
  if (error) return <main>{back}<p className="status">{error}</p></main>
  if (!data) return <main>{back}<p className="status">Loading…</p></main>

  // A current player belongs on the full page for their role.
  if (data.current) return <Navigate to={`/${data.kind === 'goalie' ? 'goalie' : 'player'}/${id}`} replace />
  const wrongRoute = (data.kind === 'goalie') !== !!goalie
  if (wrongRoute) return <Navigate to={`/${data.kind === 'goalie' ? 'goalie' : 'player'}/${id}`} replace />

  const ranks = data.ranks[kind] ?? {}
  const status = data.active_season ? 'Not in the lineup this season' : 'Retired or inactive'

  return (
    <main>
      {back}
      <header>
        <h1>
          {data.name} <span>{data.kind === 'goalie' ? 'G' : data.position}{data.hall_of_fame ? ' · Hockey Hall of Fame' : ''}</span>
        </h1>
        <p>{status}. No games in the current season, so this page shows career history.</p>
        <p><Link to={`/compare?ids=${id}`}>Compare with other players →</Link></p>
      </header>

      <Career playerId={id} />

      <h2>All-time rankings</h2>
      <p className="sub">
        Where this career stands among every {data.kind} in NHL history. Rate stats only count
        players with enough games to be meaningful.
      </p>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={kind === 'regular'} className={kind === 'regular' ? 'on' : ''} onClick={() => setKind('regular')}>Regular season</button>
        {data.ranks.playoffs && (
          <button role="tab" aria-selected={kind === 'playoffs'} className={kind === 'playoffs' ? 'on' : ''} onClick={() => setKind('playoffs')}>Playoffs</button>
        )}
      </div>
      <RankCards ranks={ranks} scope="alltime" />

      {data.kind !== 'goalie' && <DefenseProfile playerId={id} />}

      {data.kind !== 'goalie' && <Comparables playerId={id} />}
    </main>
  )
}
