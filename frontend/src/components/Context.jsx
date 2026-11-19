import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { describe } from '../glossary.js'
import { shortDate as day } from '../format.js'

/**
 * Trade, offseason-move and lineup context, inferred from game rows (the NHL feeds don't publish
 * injuries or transactions). Renders nothing when there's nothing notable to say.
 */
export default function Context({ playerId, goalie = false }) {
  const [result, setResult] = useState({ id: null, data: null })

  useEffect(() => {
    fetch(`/api/${goalie ? 'goalies' : 'skaters'}/${playerId}/context`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setResult({ id: playerId, data }))
      .catch(() => setResult({ id: playerId, data: null }))
  }, [playerId, goalie])

  const d = result.id === playerId ? result.data : null
  if (!d) return null

  const a = d.availability
  const items = []

  if (d.traded) {
    const path = d.stints.map((s) => s.team).join(' → ')
    const last = d.stints[d.stints.length - 1]
    items.push({
      key: 'trade',
      title: 'Changed teams this season',
      body: `${path} — first game with ${last.team} was ${day(last.first_date)}.`,
    })
  }
  if (a) {
    // Skaters get this in the Out block of the What changed card (with who is covering); goalies have no such block.
    if (a.out_streak >= 1 && goalie) {
      items.push({
        key: 'out',
        title: `Not in the lineup for the team's last ${a.out_streak} game${a.out_streak > 1 ? 's' : ''}`,
        body: "The NHL feed doesn't say why (injury, healthy scratch, suspension or a demotion).",
        warn: true,
      })
    }
    // A skater who is out now has their current stretch in the Out block; only misses from before it are listed here.
    const outNow = !goalie && a.out_streak >= 1
    const earlier = a.missed_games - (outNow ? a.out_streak : 0)
    if (earlier > 0) {
      items.push({
        key: 'missed',
        title: `Missed ${earlier} team game${earlier > 1 ? 's' : ''} ${outNow ? 'earlier this season' : 'since their season debut'}`,
      })
    }
  }

  if (items.length === 0) return null

  return (
    <section className="context" aria-label="Trade and lineup context">
      <ul>
        {items.map((i) => (
          <li key={i.key} className={i.warn ? 'warn' : ''}>
            <strong>{i.title}.</strong>{i.body && <> <span>{i.body}</span></>}
          </li>
        ))}
      </ul>
      {d.traded && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="left" title={describe('Team')}>Team</th><th className="left">With team</th><th title={describe('GP')}>GP</th>
                {!goalie && <><th title={describe('G')}>G</th><th title={describe('A')}>A</th><th title={describe('P')}>P</th></>}
              </tr>
            </thead>
            <tbody>
              {d.stints.map((s) => (
                <tr key={`${s.team}-${s.first_date}`}>
                  <td className="left"><Link to={`/team/${s.team}`}>{s.team_name ?? s.team}</Link></td>
                  <td className="left">{day(s.first_date)} – {day(s.last_date)}</td>
                  <td>{s.gp}</td>
                  {!goalie && <><td>{s.goals}</td><td>{s.assists}</td><td>{s.points}</td></>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
