import { luckFlag } from './Luck.jsx'
import { GOALIE_CATS, SKATER_CATS, fantasyPoints } from '../fantasy.js'
import { dayName } from '../format.js'

/** Games on each day of the coming week for the roster: [{ date, count }], from the /api/fantasy/week payload. */
export function gamesByDay(week, players) {
  if (!week?.from) return []
  const counts = new Map()
  for (const p of players) {
    for (const g of week.players?.[p.id]?.games ?? []) counts.set(g.game_date, (counts.get(g.game_date) ?? 0) + 1)
  }
  const out = []
  for (let d = new Date(`${week.from}T00:00:00Z`); d.toISOString().slice(0, 10) <= week.to; d.setUTCDate(d.getUTCDate() + 1)) {
    const date = d.toISOString().slice(0, 10)
    out.push({ date, count: counts.get(date) ?? 0 })
  }
  return out
}

/** Players who need a look: not in their team's recent games, or traded this season. */
export function alertPlayers(week, players) {
  return players.filter((p) => { const w = week?.players?.[p.id]; return w && (w.games_out >= 1 || w.traded) })
}

/**
 * The strip of big numbers above the Fantasy tabs: what the roster is worth, how busy the week is, who needs attention and who is
 * running hot or cold. Each tile shows a dash rather than a guess while its data is still loading.
 */
export default function FantasySummary({ players, data, values, isCats, scoring, luck, week }) {
  if (players.length === 0) return null
  const skaters = players.map((p) => (p.kind === 'goalie' ? null : data?.skaters.find((s) => s.player_id === p.id))).filter(Boolean)
  const goalies = players.map((p) => (p.kind === 'goalie' ? data?.goalies.find((s) => s.player_id === p.id) : null)).filter(Boolean)
  const total = isCats
    ? players.reduce((t, p) => t + (values?.get(p.id)?.value ?? 0), 0)
    : skaters.reduce((t, r) => t + fantasyPoints(r, SKATER_CATS, scoring), 0) + goalies.reduce((t, r) => t + fantasyPoints(r, GOALIE_CATS, scoring), 0)

  const days = gamesByDay(week, players)
  const games = days.reduce((t, d) => t + d.count, 0)
  const busiest = days.reduce((best, d) => (d.count > (best?.count ?? 0) ? d : best), null)
  const alerts = alertPlayers(week, players)

  const flags = { hot: 0, cold: 0 }
  for (const p of players) {
    const f = luckFlag(luck?.[p.kind === 'goalie' ? 'goalies' : 'skaters']?.[p.id], p.kind === 'goalie')
    if (f) flags[f] += 1
  }

  return (
    <div className="tiles fantasy-summary" aria-label="Your team at a glance">
      <div className="tile">
        <span>{isCats ? 'Roster value' : 'Fantasy points'}</span>
        <strong>{data ? total.toFixed(1) : '–'}</strong>
        <small>{players.length} {players.length === 1 ? 'player' : 'players'}{isCats ? ', above replacement' : ' this season'}</small>
      </div>
      <div className="tile">
        <span>Games this week</span>
        <strong>{week ? games : '–'}</strong>
        <small>{busiest && busiest.count > 0 ? `Busiest day: ${dayName(busiest.date, 'long')} (${busiest.count})` : week ? 'No games scheduled' : 'Loading'}</small>
      </div>
      <div className={`tile${alerts.length ? ' tile-alert' : ''}`}>
        <span>Needs attention</span>
        <strong>{week ? alerts.length : '–'}</strong>
        <small>{!week ? 'Loading' : alerts.length === 0 ? 'Everyone is in the lineup' : alerts.slice(0, 2).map((p) => p.name.split(' ').slice(-1)[0]).join(', ') + (alerts.length > 2 ? ` +${alerts.length - 2}` : '')}</small>
      </div>
      <div className="tile">
        <span>Running hot / cold</span>
        <strong>{luck ? <><span className="good-text">{flags.hot}</span> / <span className="bad-text">{flags.cold}</span></> : '–'}</strong>
        <small>{luck ? 'Results vs what their shots support' : 'Loading'}</small>
      </div>
    </div>
  )
}
