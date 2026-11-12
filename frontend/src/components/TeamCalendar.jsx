import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { defaultMonth, monthShort, monthTitle, monthsOf, monthWeeks, recordOf, recordText, resultText, todayIso } from '../calendar.js'
import { getJson } from '../lists.js'
import { Skeleton } from './Skeleton.jsx'
import TeamMark from './TeamMark.jsx'

const WEEKDAYS = [['S', 'Sunday'], ['M', 'Monday'], ['T', 'Tuesday'], ['W', 'Wednesday'], ['T', 'Thursday'], ['F', 'Friday'], ['S', 'Saturday']]
const timeOf = (iso) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }) : '')

/** What a screen reader says for a game's cell: "Home against CGY, won 4-2". */
function describeGame(g) {
  const where = g.home ? `Home against ${g.opponent}` : `Away at ${g.opponent}`
  if (g.result) return `${where}, ${g.result === 'W' ? 'won' : g.result === 'L' ? 'lost' : 'lost in overtime or a shootout'} ${g.us} to ${g.them}`
  if (g.state === 'LIVE') return `${where}, in progress`
  return `${where}${g.start_time ? `, ${timeOf(g.start_time)}` : ''}`
}

function Cell({ cell, today }) {
  if (!cell) return <td className="cal-blank" />
  const g = cell.game
  const cls = ['cal-day']
  if (g) cls.push('has-game', g.home ? 'home' : 'away', g.result ? g.result.toLowerCase() : g.state === 'LIVE' ? 'live' : 'next')
  if (cell.date === today) cls.push('today')
  return (
    <td className={cls.join(' ')}>
      <span className="cal-date">{cell.day}</span>
      {g && (
        <>
          <Link className="cal-game" to={`/game/${g.game_id}`} aria-label={describeGame(g)}>
            <TeamMark abbrev={g.opponent} size={22} />
            <span className="cal-vs">{g.home ? 'vs' : '@'} {g.opponent}</span>
            <span className="cal-res">{g.result ? resultText(g) : g.state === 'LIVE' ? 'Live' : timeOf(g.start_time)}</span>
          </Link>
          {g.back_to_back && <span className="cal-b2b" title="Second game in two nights">B2B</span>}
        </>
      )}
    </td>
  )
}

/** A team's season as a calendar, one month at a time: every game with its opponent, home or away, the result or start time, and back-to-backs.
 *  Opens on the current month; the month in view is kept in ?month= so a link or a reload comes back to it. */
export default function TeamCalendar({ abbrev }) {
  const [state, setState] = useState({ abbrev: null, data: null, error: null })
  const [params, setParams] = useSearchParams()
  useEffect(() => {
    let current = true
    getJson(`/api/teams/${abbrev}/calendar`)
      .then((data) => current && setState({ abbrev, data, error: null }))
      .catch((e) => current && setState({ abbrev, data: null, error: e.message }))
    return () => { current = false }
  }, [abbrev])
  const { data, error } = state.abbrev === abbrev ? state : { data: null, error: null }

  const byDate = useMemo(() => new Map((data?.games ?? []).map((g) => [g.date, g])), [data])
  const months = useMemo(() => monthsOf(data?.games ?? []), [data])
  if (error) return <p className="status">Couldn't load the calendar: {error}</p>
  if (!data) return <Skeleton rows={8} />
  if (data.games.length === 0) return <p className="status">No schedule has been published for {data.team.name} yet.</p>

  const s = data.summary
  const today = todayIso()
  const asked = params.get('month')
  const month = months.includes(asked) ? asked : defaultMonth(months, today)
  const at = months.indexOf(month)
  const show = (m) => {
    const next = new URLSearchParams(params)
    next.set('month', m)
    setParams(next, { replace: true })
  }
  const record = recordText(recordOf(data.games.filter((g) => g.date.startsWith(month))))
  return (
    <>
      <p className="sub">
        {s.games} games: {s.home} at home and {s.away} on the road, with {s.back_to_backs} back-to-backs.
        {s.played > 0 && <> {s.played} played ({s.wins}-{s.losses}-{s.ot_losses}), {s.remaining} to go.</>}
      </p>
      <div className="tabs cal-months" role="tablist" aria-label="Month">
        {months.map((m) => (
          <button key={m} type="button" role="tab" aria-selected={m === month} className={m === month ? 'on' : ''} onClick={() => show(m)}>{monthShort(m)}</button>
        ))}
      </div>
      <section className="cal-month" aria-label={monthTitle(month)}>
        <div className="cal-head">
          <button type="button" className="cal-step" onClick={() => show(months[at - 1])} disabled={at <= 0} aria-label="Previous month">&lsaquo;</button>
          <h3>{monthTitle(month)}{record && <small>{record}</small>}</h3>
          <button type="button" className="cal-step" onClick={() => show(months[at + 1])} disabled={at >= months.length - 1} aria-label="Next month">&rsaquo;</button>
        </div>
        <table className="cal">
          <thead>
            <tr>{WEEKDAYS.map(([short, full], i) => <th key={i} scope="col" abbr={full}>{short}</th>)}</tr>
          </thead>
          <tbody>
            {monthWeeks(month, byDate).map((week, i) => (
              <tr key={i}>{week.map((cell, j) => <Cell key={j} cell={cell} today={today} />)}</tr>
            ))}
          </tbody>
        </table>
      </section>
      <div className="cal-tools">
        <a className="link-button" href={`/api/teams/${abbrev}/calendar.ics`} download title="A file you can open in Apple Calendar, Google Calendar or Outlook">
          Add the whole season to your calendar (.ics)
        </a>
        <span className="cal-legend">Wins and overtime losses are shaded. Home games have a darker border. B2B marks the second game in two nights.</span>
      </div>
    </>
  )
}
