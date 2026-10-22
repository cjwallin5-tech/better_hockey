import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { seasonLabel } from '../career.js'

const signed = (v, d = 2) => (v == null ? '–' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`)
const pct = (v) => (v == null ? '–' : `${Math.round(v * 100)}%`)
const day = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })

function Effect({ title, note, e }) {
  return (
    <div className="tile">
      <span>{title}</span>
      <strong>{signed(e.goal_diff.gap)} goals</strong>
      <small className="muted">{e.win_rate.gap == null ? "–" : signed(e.win_rate.gap * 100, 0)} percentage points of win rate, {e.games} games. {note}</small>
    </div>
  )
}

const km = (n) => `${n.toLocaleString()} km`
const zones = (h) => (h === 0 ? '' : `, ${Math.abs(h)} zone${Math.abs(h) === 1 ? '' : 's'} ${h > 0 ? 'east' : 'west'}`)
const trip = (t) => (t ? `${km(t.km)}${zones(t.hours_east)}` : '–')

function mismatchText(u) {
  if (u.mismatch === 'both') return `${u.away} and ${u.home} both played yesterday`
  const [tired, fresh] = u.mismatch === 'home_tired' ? [u.home, u.away] : [u.away, u.home]
  return `${tired} played yesterday, ${fresh} is rested`
}

/** Back-to-backs: how much the second night costs a team, which games coming up are lopsided on rest, and who has the most left. */
export default function Rest() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [sort, setSort] = useState('left')

  useEffect(() => {
    fetch('/api/rest')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])

  const teams = useMemo(() => {
    if (!data) return []
    const key = {
      left: (t) => -t.back_to_backs_left,
      tired: (t) => -t.tired_left,
      cost: (t) => (t.tired.goal_diff_per_game ?? 0) - (t.normal.goal_diff_per_game ?? 0),
      name: () => 0,
    }[sort]
    return [...data.teams].sort((a, b) => key(a) - key(b) || a.name.localeCompare(b.name))
  }, [data, sort])

  if (error) return <main><p className="status">Couldn't load this: {error}</p></main>
  if (!data) return <main><p className="status">Loading…</p></main>
  const { tired, edge, both } = data.effects
  const lopsided = data.upcoming.filter((u) => u.mismatch)

  return (
    <main>
      <header>
        <h1>Rest and back-to-backs</h1>
        <p>
          A team on the second night of a back-to-back against a rested opponent does worse. This measures how much, using every
          game we store (this season and the previous four), and lists the coming games where one side has the rest edge.
          The <Link to="/schedule">schedule grid</Link> shows how many back-to-backs each team has.
        </p>
      </header>

      <section className="tiles">
        <Effect title="Tired team (back-to-back, opponent rested)" e={tired} note="Per game, against the same team's other games." />
        <Effect title="Rested team (opponent on a back-to-back)" e={edge} note="The other side of the same games." />
        <Effect title="Both teams played yesterday" e={both} note="Cancels out." />
      </section>
      <p className="sub">
        Each figure is the average over the league's teams of the gap between how a team did in those games and how the same
        team did when both sides were rested, so strong teams aren't mistaken for rested ones. We could not detect an effect for
        goalies who started both nights (too few of them, and the gap in save percentage was well within noise). Distance and
        time zones are shown for context, measured from where each team's previous game was played, but they had no detectable
        effect once rest and home ice were accounted for (every estimate was small and inside its margin of error). A team is assumed to travel straight from one
        arena to the next, so a long road trip's flights home are not counted.
      </p>

      <h2>Lopsided games, next 7 days</h2>
      {lopsided.length === 0 ? <p className="status">No game in the next week has a rest mismatch.</p> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th className="left">Date</th><th className="left">Game</th><th className="left">Rest</th><th className="left" title="Distance and time zones from where each team's previous game was played">Travel (away / home)</th></tr></thead>
            <tbody>
              {lopsided.map((u) => (
                <tr key={u.game_id}>
                  <td className="left">{day(u.game_date)}</td>
                  <td className="left"><Link to={`/game/${u.game_id}`}>{u.away} @ {u.home}</Link></td>
                  <td className="left">{mismatchText(u)}</td>
                  <td className="left">{trip(u.away_travel)} / {trip(u.home_travel)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>By team, {seasonLabel(data.season)} remaining and the record on the second night</h2>
      <div className="controls">
        <label className="h2h-pick">Sort by
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="left">Back-to-backs left</option>
            <option value="tired">Tired games left (opponent rested)</option>
            <option value="cost">Biggest drop-off on the second night</option>
            <option value="name">Team</option>
          </select>
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Team</th>
              <th title="Games left that are the second night of a back-to-back">B2B left</th>
              <th title="Games left on the second night of a back-to-back against a rested opponent">Tired left</th>
              <th title="Games played tired (second night, opponent rested)">Tired GP</th>
              <th title="Share of possible points won when tired">Tired pts%</th>
              <th title="Share of possible points won when both teams were rested">Normal pts%</th>
              <th title="Goal difference per game when tired">Tired GD/GP</th>
              <th title="Goal difference per game when both teams were rested">Normal GD/GP</th>
            </tr>
          </thead>
          <tbody>
            {teams.map((t) => (
              <tr key={t.abbrev}>
                <td className="left"><Link to={`/team/${t.abbrev}`}>{t.name}</Link></td>
                <td>{t.back_to_backs_left}</td><td>{t.tired_left}</td><td>{t.tired.games}</td>
                <td>{pct(t.tired.points_pct)}</td><td>{pct(t.normal.points_pct)}</td>
                <td>{signed(t.tired.goal_diff_per_game)}</td><td>{signed(t.normal.goal_diff_per_game)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="sub">One team's record over its tired games is a small sample; the league figures above are the dependable part.</p>
    </main>
  )
}
