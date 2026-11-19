import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import Avatar from './Avatar.jsx'
import Info from './Info.jsx'
import { MIN_OUT, absenceOf, coverFor, gainingFrom, signedTime, useAbsences } from '../absences.js'
import { lastName, shortDate } from '../format.js'

/** One line of how a teammate's ice time changes: even strength, plus the power play when it moved. */
function GainLine({ gain }) {
  return (
    <>
      <strong>{signedTime(gain.total)}</strong> a game
      {Math.abs(gain.pp) >= 15 && <small> ({signedTime(gain.pp)} on the power play)</small>}
    </>
  )
}

const basis = (g) => (g.observed
  ? `What they have actually played over the ${g.games} games missed so far, against their usual.`
  : 'The average for a teammate in this spot (too few games missed to go by what has happened).')

/**
 * What a player's page says about the lineup, for the "What changed" card. `gamesOut` is the live count from the skaters table (the one
 * source that is up to date the day a player returns). Returns { has, isOut, out, cover, gaining }: `out` is the player's own absence
 * (who is covering for them), `gaining` the absences they are picking up minutes from.
 */
export function useCoverage(playerId, gamesOut = 0) {
  const absences = useAbsences()
  return useMemo(() => {
    const isOut = gamesOut >= MIN_OUT
    const out = isOut ? absenceOf(absences, playerId) : null
    const gaining = gainingFrom(absences, playerId).slice(0, 2)
    return { has: isOut || gaining.length > 0, isOut, out, cover: out ? coverFor(out) : [], gaining }
  }, [absences, playerId, gamesOut])
}

/** The "Out" block (who is out, who is covering) and the "Picking up minutes" lines, from useCoverage. */
export default function Covering({ coverage, name, team, gamesOut = 0, lastGame = null }) {
  const { isOut, out, cover, gaining } = coverage
  return (
    <div className="covering">
      {isOut && (
        <div className="cover-block">
          <h3>Out</h3>
          <p>
            <strong>{name}</strong> {lastGame ? <>hasn't played since {shortDate(lastGame)}, missing {team}'s last {gamesOut} games.</> : <>hasn't played in {team}'s last {gamesOut} games.</>}
          </p>
          {cover.length > 0 && (
            <>
              <h4>
                Who is covering
                <Info label="Who is covering">
                  Extra ice time each teammate gets a game while {name} is out: what they have played so far, or the average for their spot when
                  too few games have passed. It is spread over the group, so expect noise.
                  {out.role === 'PP1' && ' The power-play units get reshuffled too.'}
                </Info>
              </h4>
              <ul className="cover-list">
                {cover.map((m) => (
                  <li key={m.player_id} title={basis(m.gain)}>
                    <Avatar playerId={m.player_id} team={out.team} name={m.name} size={30} />
                    <span><Link to={`/player/${m.player_id}`}>{m.name}</Link></span>
                    <span className="cover-gain"><GainLine gain={m.gain} /></span>
                    <span className="cover-basis">{m.gain.observed ? `over ${m.gain.games} games` : 'typical'}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
      {gaining.map(({ absence, gain }) => (
        <div className="cover-block" key={absence.player_id}>
          <h3>Picking up minutes</h3>
          <p>
            With <Link to={`/player/${absence.player_id}`}>{absence.name}</Link> out ({absence.games_out} games), {lastName(name)} is getting about{' '}
            <GainLine gain={gain} />.
            <Info label="Picking up minutes">{basis(gain)} It is spread over the group, so expect noise.</Info>
          </p>
        </div>
      ))}
    </div>
  )
}
