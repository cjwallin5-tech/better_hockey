import FavoriteButton from './FavoriteButton.jsx'
import TeamLogo from './TeamLogo.jsx'
import WatchButton from './WatchButton.jsx'
import { teamColor } from '../teamColors.js'

/**
 * The top of a team's page: logo, name, division and conference, the actions, and the standings as a strip of numbers. Shares the
 * player banner's look. stats: [{ label, value, note?, big?, dim? }]; `dim` greys a number that rests on a small sample.
 */
export default function TeamBanner({ team: t, stats }) {
  return (
    <header className="player-banner team-banner" style={{ '--team': teamColor(t.abbrev) }}>
      <div className="banner-id">
        <span className="banner-logo"><TeamLogo team={t} size={132} /></span>
        <div className="banner-text">
          <div className="banner-meta">{t.division} Division · {t.conference} Conference</div>
          <h1>{t.name}</h1>
          <p className="header-actions"><WatchButton kind="team" refId={t.abbrev} name={t.name} /> <FavoriteButton abbrev={t.abbrev} /></p>
        </div>
      </div>
      <dl className="banner-stats">
        {stats.map((s) => (
          <div key={s.label} className={s.big ? 'big' : ''} title={s.dim ? 'Small sample: treat this pace with caution' : undefined}>
            <dt>{s.label}</dt>
            <dd style={s.dim ? { opacity: 0.45 } : undefined}>{s.value ?? '–'}</dd>
            {s.note && <small>{s.note}</small>}
          </div>
        ))}
      </dl>
    </header>
  )
}
