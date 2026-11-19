import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import Avatar from './Avatar.jsx'
import { luckSummary } from './Luck.jsx'
import { useLeagueLuck } from './TradeIdeas.jsx'
import { alertPlayers, gamesByDay } from './FantasySummary.jsx'
import { tradeIdeas } from '../tradeIdeas.js'
import { absenceOf, coverText, useAbsences } from '../absences.js'
import { waiverRows } from '../waiver.js'
import { dayName } from '../format.js'


/** One card on the overview: a heading, a few lines, and a button into the tab with the full story. */
function Glance({ title, tab, link, go, children }) {
  return (
    <section className="glance">
      <h3>{title}</h3>
      <div className="glance-body">{children}</div>
      <button type="button" className="glance-link" onClick={() => go(tab)}>{link} →</button>
    </section>
  )
}

/**
 * The first thing on the Fantasy page: what needs doing, drawn from the tools behind the other tabs. Each card shows the
 * top item and links to the tab with everything.
 */
export default function FantasyOverview({ players, data, values, league, taken, info, week, luck, goTab }) {
  const rosterSet = useMemo(() => new Set(players.map((p) => p.id)), [players])
  const leagueLuck = useLeagueLuck()
  const absences = useAbsences()

  const pickups = useMemo(() => {
    if (!values || !data) return null
    const base = { values, roles: new Map(), luck: new Map(), schedule: new Map(), roster: rosterSet, league, taken, sort: 'value', filters: { likelyAvailable: !taken, hideHurt: true, hideTaken: true } }
    return [
      ...waiverRows({ ...base, kind: 'skater', players: data.skaters }).slice(0, 2),
      ...waiverRows({ ...base, kind: 'goalie', players: data.goalies }).slice(0, 1),
    ].sort((a, b) => b.value - a.value)
  }, [values, data, rosterSet, league, taken])

  const idea = useMemo(() => {
    if (!leagueLuck || !values || !luck) return undefined
    const merged = new Map(leagueLuck)
    for (const [kind, goalie] of [['skaters', false], ['goalies', true]]) {
      for (const [id, row] of Object.entries(luck?.[kind] ?? {})) merged.set(Number(id), luckSummary(row, goalie))
    }
    return tradeIdeas({ values, luck: merged, roster: rosterSet, limit: 1 }).sell[0] ?? null
  }, [leagueLuck, values, luck, rosterSet])

  const days = gamesByDay(week, players)
  const peak = Math.max(1, ...days.map((d) => d.count))
  const alerts = alertPlayers(week, players)
  const name = (id) => info.get(id)?.name ?? `#${id}`

  return (
    <div className="glance-grid">
      <Glance title="Needs attention" tab="week" link="Open this week" go={goTab}>
        {!week ? <p className="muted">Checking your lineup…</p> : alerts.length === 0 ? (
          <p className="glance-ok">Everyone on your roster is in their team's lineup.</p>
        ) : (
          <ul className="glance-list">
            {alerts.slice(0, 4).map((p) => {
              const w = week.players[p.id]
              return (
                <li key={p.id}>
                  <Avatar playerId={p.id} team={w.team} name={p.name} size={28} />
                  <span>
                    <Link to={`/${p.kind === 'goalie' ? 'goalie' : 'player'}/${p.id}`}>{p.name}</Link>
                    <small>{[w.games_out >= 1 ? `Out of the last ${w.games_out} ${w.team} ${w.games_out === 1 ? 'game' : 'games'}` : 'Changed teams this season', coverText(absenceOf(absences, p.id))].filter(Boolean).join('. ')}</small>
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </Glance>

      <Glance title="Your week" tab="week" link="See every game" go={goTab}>
        {!week ? <p className="muted">Loading the schedule…</p> : (
          <div className="week-bars" role="img" aria-label={`Roster games per day: ${days.map((d) => `${dayName(d.date)} ${d.count}`).join(', ')}`}>
            {days.map((d) => (
              <div key={d.date} className="week-day">
                <span className="week-count">{d.count}</span>
                <span className="week-bar"><i style={{ height: `${(d.count / peak) * 100}%` }} /></span>
                <span className="week-label">{dayName(d.date)}</span>
              </div>
            ))}
          </div>
        )}
      </Glance>

      <Glance title="Best pickups" tab="pickups" link="Open the waiver wire" go={goTab}>
        {!pickups ? <p className="muted">Ranking free players…</p> : pickups.length === 0 ? <p className="muted">Nobody worth adding right now.</p> : (
          <ul className="glance-list">
            {pickups.map((r) => (
              <li key={r.id}>
                <Avatar playerId={r.id} team={r.team} name={r.name} size={28} />
                <span>
                  <Link to={`/${r.position === 'G' ? 'goalie' : 'player'}/${r.id}`}>{r.name}</Link>
                  <small>{r.team} · {r.position}</small>
                </span>
                <strong className="glance-num" title="Value over replacement for the rest of the season">{r.value.toFixed(1)}</strong>
              </li>
            ))}
          </ul>
        )}
      </Glance>

      <Glance title="Top trade idea" tab="ideas" link="More trade ideas" go={goTab}>
        {idea === undefined ? <p className="muted">Looking for a swap…</p> : idea === null ? (
          <p className="muted">None of your players is running hot enough to sell high.</p>
        ) : (
          <>
            <p className="glance-trade">
              <strong>Sell {name(idea.id)}</strong>, scoring above what their shots support.
              {idea.targets[0] ? <> Swap for <strong>{name(idea.targets[0].id)}</strong>, who is running cold at a similar value.</> : ' No cold player of similar value to swap for yet.'}
            </p>
            {idea.targets[0] && <Link className="glance-cta" to={`/fantasy?tab=trade&give=${idea.id}&get=${idea.targets[0].id}`}>Analyze this trade</Link>}
          </>
        )}
      </Glance>
    </div>
  )
}
