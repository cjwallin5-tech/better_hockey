import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CountryFlag } from '../components/Flag.jsx'
import { ProspectName, draftText, ppg, svp } from '../components/ProspectBits.jsx'
import { useUrlSync } from '../urlState.js'

function useApi(url) {
  const [state, setState] = useState({ url: null, data: null, error: null })
  useEffect(() => {
    let ignore = false
    fetch(url)
      .then(async (r) => (r.ok ? r.json() : Promise.reject(new Error((await r.json().catch(() => ({}))).detail ?? `API returned ${r.status}`))))
      .then((data) => !ignore && setState({ url, data, error: null }))
      .catch((error) => !ignore && setState({ url, data: null, error: error.message }))
    return () => { ignore = true }
  }, [url])
  return state.url === url ? state : { data: null, error: null }
}

const POSITIONS = [['', 'All'], ['F', 'Forwards'], ['D', 'Defensemen'], ['G', 'Goalies']]
const SORTS = [['points_per_game', 'Points per game'], ['points', 'Points'], ['goals', 'Goals'], ['games', 'Games'], ['age', 'Youngest'], ['draft', 'Draft pick'], ['save_pct', 'Save %'], ['name', 'Name']]

function TeamProspects() {
  const initial = new URLSearchParams(window.location.search)
  const [team, setTeam] = useState(initial.get('team') ?? '')
  const [position, setPosition] = useState(initial.get('pos') ?? '')
  const [league, setLeague] = useState(initial.get('league') ?? '')
  const [sort, setSort] = useState(initial.get('sort') ?? 'points_per_game')
  const [q, setQ] = useState('')
  useUrlSync([['tab', 'prospects', 'prospects'], ['team', team, ''], ['pos', position, ''], ['league', league, ''], ['sort', sort, 'points_per_game']])
  const [teams, setTeams] = useState([])
  useEffect(() => {
    fetch('/api/teams').then((r) => r.json()).then((rows) => setTeams([...rows].sort((a, b) => a.name.localeCompare(b.name)))).catch(() => {})
  }, [])
  const url = `/api/prospects?team=${team}&position=${position}&league=${encodeURIComponent(league)}&sort=${sort}&q=${encodeURIComponent(q)}&limit=200`
  const { data, error } = useApi(url)

  return (
    <>
      <div className="h2h-picks">
        <label className="h2h-pick">Team
          <select value={team} onChange={(e) => setTeam(e.target.value)}>
            <option value="">All teams</option>
            {teams.map((t) => <option key={t.abbrev} value={t.abbrev}>{t.name}</option>)}
          </select>
        </label>
        <label className="h2h-pick">Position
          <select value={position} onChange={(e) => setPosition(e.target.value)}>
            {POSITIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="h2h-pick">League
          <select value={league} onChange={(e) => setLeague(e.target.value)}>
            <option value="">All leagues</option>
            {(data?.leagues ?? (league ? [league] : [])).map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </label>
        <label className="h2h-pick">Rank by
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="h2h-pick">Search
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name…" />
        </label>
      </div>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && data.rows.length === 0 && <p className="status">No prospects match. Prospects with fewer than 5 games this season are hidden unless you search by name.</p>}
      {data && data.rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="left">Prospect</th><th className="left">Pos</th><th>Age</th><th className="left">Team</th>
                <th className="left" title="The league and club where they played the most games this season">Playing for</th>
                <th title="Games played">GP</th><th title="Goals">G</th><th title="Assists">A</th><th title="Points">P</th><th title="Points per game">P/GP</th>
                <th title="Save percentage (goalies)">SV%</th><th className="left">Drafted</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((p) => (
                <tr key={p.player_id}>
                  <td className="left"><ProspectName p={p} /></td>
                  <td className="left">{p.position}</td><td>{p.age ?? '–'}</td>
                  <td className="left"><Link to={`/team/${p.team}`}>{p.team}</Link></td>
                  <td className="left">{p.league ? <>{p.league} <span className="muted">{p.club}</span></> : <span className="muted">–</span>}</td>
                  <td>{p.games || '–'}</td><td>{p.goals ?? '–'}</td><td>{p.assists ?? '–'}</td><td>{p.points ?? '–'}</td>
                  <td className="accent">{ppg(p.points_per_game)}</td><td>{svp(p.save_pct)}</td>
                  <td className="left">{draftText(p.draft)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="sub">
        {data ? `${data.total} prospects. ` : ''}Prospects are the players on NHL teams' prospect lists, so someone who has made the NHL
        drops off. Leagues are not comparable: a point a game in the OHL is a different thing from a point a game in the AHL or
        the SHL, so compare players inside a league, and read a small sample lightly. Stats update with the nightly refresh.
      </p>
    </>
  )
}

function DraftClass() {
  const [category, setCategory] = useState(1)
  const [q, setQ] = useState('')
  const { data, error } = useApi(`/api/draft/rankings?category=${category}`)
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return (data?.rows ?? []).filter((r) => !needle || r.name.toLowerCase().includes(needle) || (r.club ?? '').toLowerCase().includes(needle))
  }, [data, q])

  return (
    <>
      <div className="tabs" role="tablist">
        {Object.entries(data?.categories ?? { 1: 'North American skaters', 2: 'International skaters', 3: 'North American goalies', 4: 'International goalies' }).map(([id, name]) => (
          <button key={id} role="tab" aria-selected={category === Number(id)} className={category === Number(id) ? 'on' : ''} onClick={() => setCategory(Number(id))}>{name}</button>
        ))}
      </div>
      <div className="h2h-picks">
        <label className="h2h-pick">Search
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name or club…" />
        </label>
      </div>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data?.already_drafted && (
        <p className="notice">
          The NHL hasn't published rankings for the {data.upcoming_year} draft yet, so this is the {data.draft_year} class, which has already been
          drafted. Those players are on the Team prospects tab with their stats.
        </p>
      )}
      {data && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Rank</th><th className="left">Player</th><th className="left">Pos</th><th>Age</th>
                <th className="left">Club</th><th className="left">League</th><th>Height</th><th>Weight</th>
                <th title="NHL Central Scouting's midterm ranking">Midterm</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.name}-${i}`}>
                  <td className="accent">{r.rank ?? '–'}</td>
                  <td className="left"><CountryFlag code={r.birth_country} /> {r.name}</td>
                  <td className="left">{r.position}</td><td>{r.age ?? '–'}</td>
                  <td className="left">{r.club ?? '–'}</td><td className="left">{r.league ?? '–'}</td>
                  <td>{r.height_in ? `${Math.floor(r.height_in / 12)}'${r.height_in % 12}"` : '–'}</td><td>{r.weight_lb ?? '–'}</td>
                  <td>{r.midterm_rank ?? '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="sub">
        {data ? `${data.draft_year} NHL Draft, ` : ''}NHL Central Scouting's rankings, separate for North American and international
        players. They list each player's last amateur club and league but no player ids, so stats for the draft class aren't linked here;
        a player appears on the team prospects tab after being drafted.
      </p>
    </>
  )
}

export default function Prospects() {
  const initial = new URLSearchParams(window.location.search)
  const [tab, setTab] = useState(initial.get('tab') === 'draft' ? 'draft' : 'prospects')
  return (
    <main>
      <header>
        <h1>Prospects</h1>
        <p>Players who haven't made the NHL yet: the prospects each team holds, with their junior, college, European and minor-league stats, and the upcoming draft class.</p>
      </header>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === 'prospects'} className={tab === 'prospects' ? 'on' : ''} onClick={() => setTab('prospects')}>Team prospects</button>
        <button role="tab" aria-selected={tab === 'draft'} className={tab === 'draft' ? 'on' : ''} onClick={() => setTab('draft')}>Draft class</button>
      </div>
      {tab === 'prospects' ? <TeamProspects /> : <DraftClass />}
    </main>
  )
}
