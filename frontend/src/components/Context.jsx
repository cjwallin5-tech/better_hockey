import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { describe } from '../glossary.js'

const day = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

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
  if (d.moved_from) {
    items.push({
      key: 'offseason',
      title: 'New team this season',
      body: `Finished last season with the ${d.moved_from}.`,
    })
  }
  if (d.rookie) items.push({ key: 'rookie', title: 'Rookie', body: 'First NHL season.' })

  if (a) {
    if (a.out_streak >= 1) {
      items.push({
        key: 'out',
        title: `Not in the lineup for the team's last ${a.out_streak} game${a.out_streak > 1 ? 's' : ''}`,
        body: "The NHL feed doesn't say why (injury, healthy scratch, suspension or a demotion).",
        warn: true,
      })
    }
    if (a.missed_games > 0) {
      items.push({
        key: 'missed',
        title: `Missed ${a.missed_games} team game${a.missed_games > 1 ? 's' : ''} since their season debut`,
        body: a.missed
          .map((m) => `${day(m.game_date)} vs ${m.opponent}`)
          .join(', ')
          .concat(a.missed_games > a.missed.length ? ', …' : ''),
      })
    }
    if (a.debut_after_team_games > 0) {
      items.push({
        key: 'debut',
        title: 'Season debut after the team had played',
        body: `${a.debut_after_team_games} game${a.debut_after_team_games > 1 ? 's' : ''} (not in the lineup, or in the minors).`,
      })
    }
  }

  if (items.length === 0) return null

  return (
    <section className="context" aria-label="Trade and lineup context">
      <ul>
        {items.map((i) => (
          <li key={i.key} className={i.warn ? 'warn' : ''}>
            <strong>{i.title}.</strong> <span>{i.body}</span>
          </li>
        ))}
      </ul>
      {a && (a.missed_games > 0 || a.out_streak > 0) && (
        <p className="context-note">
          Lineup gaps are inferred from games the player's team played without them; the NHL
          doesn't publish the reason.
        </p>
      )}
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
