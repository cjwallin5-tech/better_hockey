import { Link } from 'react-router-dom'
import FantasyStar from './FantasyStar.jsx'
import Flag from './Flag.jsx'
import Headshot from './Headshot.jsx'
import PlayerBio from './PlayerBio.jsx'
import TeamMark from './TeamMark.jsx'
import WatchButton from './WatchButton.jsx'
import { teamColor } from '../teamColors.js'

/**
 * The top of a skater's or goalie's page: who they are, the actions, and the season line as a strip of numbers. The current team's colour
 * edges the card and its logo sits faintly behind. stats: [{ label, value, rank?, big? }], the first few shown larger.
 */
export default function PlayerBanner({ p, stats, kind = 'skater', retired = false, meta = null }) {
  const teams = (p.team ?? '').split(',').filter(Boolean)
  const current = teams[teams.length - 1]
  const goalie = kind === 'goalie'
  return (
    <header className="player-banner" style={{ '--team': teamColor(current) }}>
      {current && <span className="banner-mark" aria-hidden="true"><TeamMark abbrev={current} size={340} /></span>}
      <div className="banner-id">
        <Headshot playerId={p.player_id} name={p.name} />
        <div className="banner-text">
          <div className="banner-meta">
            {meta ?? <>{teams.map((abbr, i) => <span key={abbr}>{i > 0 && ', '}<Link to={`/team/${abbr}`}>{abbr}</Link></span>)} · {goalie ? `G${p.catches ? ` · catches ${p.catches}` : ''}` : p.position}</>}
          </div>
          <h1><Flag playerId={p.player_id} />{p.name}</h1>
          <PlayerBio playerId={p.player_id} />
          <p className="header-actions">
            {!retired && <FantasyStar player={{ id: p.player_id, kind, name: p.name }} />}
            {!retired && <WatchButton kind="player" refId={p.player_id} name={p.name} />}
            <Link to={`/compare?ids=${p.player_id}`}>{goalie ? 'Compare with other goalies →' : 'Compare with other players →'}</Link>
          </p>
        </div>
      </div>
      <dl className="banner-stats">
        {stats.map((s) => (
          <div key={s.label} className={s.big ? 'big' : ''}>
            <dt>{s.label}</dt>
            <dd>{s.value ?? '–'}</dd>
            {s.rank && <small>{s.rank}</small>}
          </div>
        ))}
      </dl>
    </header>
  )
}
