import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import NewsList from '../components/NewsList.jsx'
import PageTabs from '../components/PageTabs.jsx'
import { getJson } from '../lists.js'

export default function News() {
  const [params, setParams] = useSearchParams()
  const [teams, setTeams] = useState([])
  const team = (params.get('team') || '').toUpperCase()

  useEffect(() => {
    let current = true
    getJson('/api/teams')
      .then((t) => current && setTeams([...t].sort((a, b) => a.name.localeCompare(b.name))))
      .catch(() => {})
    return () => { current = false }
  }, [])

  const pick = (abbrev) => {
    const next = new URLSearchParams(params)
    if (abbrev) next.set('team', abbrev)
    else next.delete('team')
    setParams(next, { replace: true })
  }
  const name = teams.find((t) => t.abbrev === team)?.name

  return (
    <main>
      <header>
        <h1>NHL news</h1>
        <p>
          Headlines from ESPN, The Athletic, Yahoo Sports, CBS Sports and the outlets Yahoo carries. Each story is tagged with the teams and
          players it names, so you can follow one team, and links go to the publisher. Top stories are ranked, not just recent: trades, firings
          and retirements rank highest, then signings, waivers and injuries, with a boost for stars, for stories several outlets carry and for
          ESPN's lead stories, and a penalty for game recaps, opinion pieces and non-NHL hockey. Newer stories rank above older ones.
        </p>
      </header>

      <div className="controls">
        <label>
          Team{' '}
          <select value={team} onChange={(e) => pick(e.target.value)}>
            <option value="">All teams</option>
            {teams.map((t) => <option key={t.abbrev} value={t.abbrev}>{t.name}</option>)}
          </select>
        </label>
      </div>

      <PageTabs
        tabs={[
          { id: 'top', label: 'Top stories', content: <NewsList team={team || undefined} top limit={40} empty={`No top stories${name ? ` about the ${name}` : ''} right now.`} /> },
          { id: 'latest', label: 'Latest', content: <NewsList team={team || undefined} limit={60} empty={`No stories${name ? ` about the ${name}` : ''} right now.`} /> },
        ]}
      />
    </main>
  )
}
