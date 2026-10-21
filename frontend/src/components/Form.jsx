import { useState } from 'react'
import { RollingChart } from './Charts.jsx'
import { mmss } from './Roles.jsx'
import { useScoring } from '../fantasy.js'
import { goalieForm, missingScoring, rollingMean, rollingRatio, skaterForm, windowsFor } from '../rolling.js'

const TREND_WINDOWS = [3, 5, 10, 20]
const n1 = (v) => (v == null ? '–' : v.toFixed(1))
const n2 = (v) => (v == null ? '–' : v.toFixed(2))
const signed = (v, d = 2) => (v == null ? '–' : `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(v).toFixed(d)}`)
const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

/** The trend-window buttons: only windows that fit in the games played. */
function WindowTabs({ options, value, onChange }) {
  if (options.length < 2) return null
  return (
    <div className="tabs" role="tablist" aria-label="Rolling window">
      {options.map((n) => (
        <button key={n} role="tab" aria-selected={value === n} className={value === n ? 'on' : ''} onClick={() => onChange(n)}>{n}-game</button>
      ))}
    </div>
  )
}

/**
 * Recent form for a skater: the season next to the last 20, 10 and 5 games, and a rolling points-per-game line.
 * `games` is the season's game log, oldest first.
 */
export function SkaterForm({ games }) {
  const { scoring } = useScoring()
  const [w, setW] = useState(5)
  const count = games.length
  if (count === 0) return null
  const season = skaterForm(games, null, scoring)
  const rows = [...windowsFor(count)].reverse().map((n) => ({ label: `Last ${n}`, n, line: skaterForm(games, n, scoring) }))
  const showFantasy = Object.values(scoring).some(Number)
  const missing = missingScoring(scoring)
  const options = TREND_WINDOWS.filter((n) => n <= count)
  const win = options.includes(w) ? w : options[options.length - 1] ?? 5
  const raw = games.map((g) => g.points)
  const roll = rollingMean(games, win, (g) => g.points)

  const row = (label, line, base) => (
    <tr key={label}>
      <td className="left">{label}</td>
      <td>{line.gp}</td><td>{line.goals}</td><td>{line.assists}</td><td>{line.points}</td>
      <td className="accent">{n2(line.ppg)}</td>
      <td>{base ? signed(line.ppg - base.ppg) : ''}</td>
      <td>{n1(line.shots)}</td><td>{line.toi == null ? '–' : mmss(line.toi)}</td><td>{n1(line.hits)}</td>
      <td>{line.plusMinus > 0 ? `+${line.plusMinus}` : line.plusMinus}</td>
      {showFantasy && <td>{n2(line.fpg)}</td>}
    </tr>
  )

  return (
    <section>
      <h2>Recent form</h2>
      <p className="sub">
        The season next to the last {windowsFor(count).length ? windowsFor(count).join(', ') : 'few'} games. "vs season" is how far points per game are
        above or below the season rate. A short window swings a lot, so look at the longer ones for the real trend.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left" />
              <th>GP</th><th>G</th><th>A</th><th>P</th><th>P/GP</th><th title="Points per game minus the season rate">vs season</th>
              <th>S/GP</th><th>TOI</th><th>Hits/GP</th><th>+/-</th>
              {showFantasy && <th title="Fantasy points per game under your league scoring">Fantasy pts/GP</th>}
            </tr>
          </thead>
          <tbody>
            {row('Season', season, null)}
            {rows.map(({ label, line }) => row(label, line, season))}
          </tbody>
        </table>
      </div>
      {showFantasy && missing.length > 0 && (
        <p className="muted">Fantasy points here leave out power-play bonus and game-winning-goal points, which game logs don't carry.</p>
      )}
      {options.length > 0 && (
        <>
          <WindowTabs options={options} value={win} onChange={setW} />
          <RollingChart
            title="Points per game, trending"
            games={games} raw={raw} roll={roll} w={win}
            avg={season.ppg} avgLabel="Season average" rawLabel="Points in the game"
            fmt={(v) => String(+v.toFixed(1))}
            tip={(i) => (
              <>
                <div className="tip-row"><strong>{games[i].points}</strong> points ({games[i].goals} G, {games[i].assists} A)</div>
                {roll[i] != null && <div className="tip-row"><strong>{roll[i].toFixed(2)}</strong> per game over the last {win}</div>}
              </>
            )}
          />
        </>
      )}
    </section>
  )
}

/** Recent form for a goalie: the season next to the last 20, 10 and 5 appearances, and a rolling save % line. */
export function GoalieForm({ games, leagueSvPct }) {
  const [w, setW] = useState(5)
  const count = games.length
  if (count === 0) return null
  const season = goalieForm(games, null, leagueSvPct)
  const rows = [...windowsFor(count)].reverse().map((n) => ({ label: `Last ${n}`, line: goalieForm(games, n, leagueSvPct) }))
  const options = TREND_WINDOWS.filter((n) => n <= count)
  const win = options.includes(w) ? w : options[options.length - 1] ?? 5
  const raw = games.map((g) => (g.shots_against ? g.saves / g.shots_against : null))
  const roll = rollingRatio(games, win, (g) => g.saves, (g) => g.shots_against)
  const vals = [...raw, ...roll, season.svPct, leagueSvPct].filter((v) => v != null)
  const lo = Math.max(0.5, Math.floor((Math.min(...vals, 0.9) - 0.005) * 20) / 20)
  const ticks = []
  for (let v = lo; v <= 1.0001; v += 0.05) ticks.push(+v.toFixed(2))

  const row = (label, line) => (
    <tr key={label}>
      <td className="left">{label}</td>
      <td>{line.gp}</td><td>{line.starts}</td><td>{line.wins}</td>
      <td className="accent">{sv(line.svPct)}</td><td>{n2(line.gaa)}</td><td>{signed(line.gsaa, 1)}</td>
      <td>{line.gp ? n1(line.shots / line.gp) : '–'}</td>
    </tr>
  )

  return (
    <section>
      <h2>Recent form</h2>
      <p className="sub">
        The season next to the last {windowsFor(count).length ? windowsFor(count).join(', ') : 'few'} appearances. GSAA is goals saved above a
        league-average goalie facing the same shots. A few games swing save percentage a lot, so favor the longer windows.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th className="left" /><th>GP</th><th>GS</th><th>W</th><th>SV%</th><th>GAA</th><th>GSAA</th><th>Shots/GP</th></tr>
          </thead>
          <tbody>
            {row('Season', season)}
            {rows.map(({ label, line }) => row(label, line))}
          </tbody>
        </table>
      </div>
      {options.length > 0 && (
        <>
          <WindowTabs options={options} value={win} onChange={setW} />
          <RollingChart
            title="Save percentage, trending"
            games={games} raw={raw} roll={roll} w={win}
            avg={season.svPct} avgLabel="Season SV%" rawLabel="SV% in the game"
            refLine={leagueSvPct == null ? undefined : { value: leagueSvPct, label: 'League average' }}
            domain={[lo, 1]} ticks={ticks} fmt={(v) => v.toFixed(3).replace(/^0/, '')}
            note="below the chart's floor, a game is drawn at the bottom edge"
            tip={(i) => (
              <>
                <div className="tip-row"><strong>{games[i].saves}</strong> saves on {games[i].shots_against} shots{games[i].decision ? ` (${games[i].decision})` : ''}</div>
                {roll[i] != null && <div className="tip-row"><strong>{sv(roll[i])}</strong> over the last {win}</div>}
              </>
            )}
          />
        </>
      )}
    </section>
  )
}
