import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { binLabel, calibrationSentence, miscalibrated, verdictFor } from '../accuracy.js'

const pct = (v, d = 0) => (v == null ? '–' : `${(v * 100).toFixed(d)}%`)
const n3 = (v) => (v == null ? '–' : v.toFixed(3))
const day = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '')
const READING = { better: 'model is better', worse: 'model is worse', unclear: "can't tell apart yet" }

function Calibration({ bins, what, label }) {
  if (!bins || bins.length === 0) return null
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th className="left" title="What the model said">{label}</th>
            <th title="How many predictions fell in this range">Games</th>
            <th title="The average chance the model gave">Said</th>
            <th title="How often it actually happened">Happened</th>
          </tr>
        </thead>
        <tbody>
          {bins.map((b) => (
            <tr key={b.lo}>
              <td className="left">{binLabel(b)}</td><td>{b.n}</td><td>{pct(b.mean_p)}</td><td className="accent">{pct(b.rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">{what}</p>
    </div>
  )
}

function WinSection({ w }) {
  if (!w || w.games === 0) return <p className="status">Not enough games yet.</p>
  const m = w.models
  const vsCoin = verdictFor(w.vs.coin)
  return (
    <>
      <p>
        Over <strong>{w.games}</strong> games ({day(w.from)} to {day(w.to)}), the on-paper win chance on the <Link to="/tonight">Tonight page</Link> scored a Brier of{' '}
        <strong>{n3(m.model.brier)}</strong> against {n3(m.coin.brier)} for a coin flip, and picked the winner {pct(m.model.accuracy)} of the time.{' '}
        Next to a coin flip the model is {READING[vsCoin]}. Home teams won {pct(w.home_win_rate)} of these games, and the model has no home-ice term.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Predictor</th>
              <th title="Mean squared miss of the win chance: a coin flip scores 0.25, lower is better">Brier</th>
              <th title="Like Brier but punishes confident misses harder: a coin flip scores 0.693, lower is better">Log loss</th>
              <th title="Share of games where the side with the higher chance won">Picked winner</th>
              <th title="The model minus this predictor in Brier, with a 95% range; below zero favors the model">Model minus this</th>
              <th className="left" title="Whether the range excludes zero">Reading</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(m).map(([key, row]) => {
              const diff = w.vs[key]
              return (
                <tr key={key}>
                  <td className="left">{row.label}</td><td className={key === 'model' ? 'accent' : ''}>{n3(row.brier)}</td><td>{n3(row.log_loss)}</td><td>{pct(row.accuracy)}</td>
                  <td>{diff ? `${diff.mean.toFixed(4)} (${diff.low.toFixed(4)} to ${diff.high.toFixed(4)})` : '–'}</td>
                  <td className="left">{diff ? READING[verdictFor(diff)] : <span className="muted">the model</span>}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <h3>When it says 55%, does it happen 55% of the time?</h3>
      <Calibration bins={w.calibration} label="Home win chance" what="Said is the model's average home win chance in the range; Happened is how often the home team won." />
      <p className="muted">
        A season so far is a small sample and hockey games are mostly luck, so a good model is only a little better than a coin flip: the "can't tell
        apart yet" readings will sharpen as games are played. The goals-based predictor uses the same idea with goals instead of expected goals,
        which is the test of whether expected goals add anything.
      </p>
    </>
  )
}

function GoalieSection({ g }) {
  if (!g || g.games === 0) return <p className="status">Not enough games yet.</p>
  const off = miscalibrated(g.calibration)
  const row = (label, p) => (
    <tr key={label}>
      <td className="left">{label}</td><td>{p.n}</td><td className="accent">{pct(p.top_correct)}</td><td>{pct(p.mean_p_actual)}</td>
      <td>{pct(p.same_as_last)}</td><td>{pct(p.most_started)}</td>
    </tr>
  )
  return (
    <>
      <p>
        Over <strong>{g.games}</strong> team games ({day(g.from)} to {day(g.to)}), the starter model's top pick was right{' '}
        <strong>{pct(g.all.top_correct)}</strong> of the time, and it gave the goalie who actually played an average of {pct(g.all.mean_p_actual)}.
        Each prediction uses only the team's earlier starts and what is known the day before, so these are day-of calls; the model is on the
        Fantasy page's goalie tabs and Home.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Situation</th><th title="Team games predicted">Games</th>
              <th title="How often the model's top pick started">Top pick right</th>
              <th title="The average chance the model gave the goalie who started">Chance given</th>
              <th title="Baseline: guess the same goalie as the team's last game">Same as last game</th>
              <th title="Baseline: guess the goalie who has started the most this season">Most starts</th>
            </tr>
          </thead>
          <tbody>
            {row('Every game', g.all)}
            {row('Second night of a back-to-back', g.back_to_back)}
            {row('Rested', g.rested)}
          </tbody>
        </table>
      </div>
      <h3>When it is confident, is it right that often?</h3>
      <Calibration bins={g.calibration} label="Top pick's chance" what="Said is the average chance the model gave its top pick in the range; Happened is how often that goalie started." />
      {off.length > 0 && (
        <ul className="roster-alerts">
          {off.map((b) => (
            <li key={b.lo} className="warn">
              {calibrationSentence(b, 'the top pick started')} That is {b.direction === 'over' ? 'more' : 'less'} confident than the results support.
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

function LiveSection({ live }) {
  if (!live || live.logged === 0) return <p className="status">Nothing logged yet. Predictions are stored each morning after the nightly ingest.</p>
  const w = live.win
  const g = live.goalie
  const vs = verdictFor(w.vs_coin)
  return (
    <>
      <p>
        Logged since <strong>{day(live.since)}</strong>: {live.logged} predictions, made before the games and never changed. Graded so far:{' '}
        <strong>{w.games}</strong> game win chances and <strong>{g.games}</strong> team starters.
      </p>
      {w.games > 0 && (
        <p>
          Win chances: Brier <strong>{n3(w.model.brier)}</strong> against {n3(w.coin.brier)} for a coin flip, picked the winner {pct(w.model.accuracy)} of the time;
          next to a coin flip the model is {READING[vs]}. Home teams won {pct(w.model.rate)}, and the model's average home win chance was {pct(w.model.mean_p)}.
        </p>
      )}
      {g.games > 0 && (
        <p>
          Starters: the top pick was right <strong>{pct(g.top_correct)}</strong> of {g.games} team games
          {g.unconfirmed > 0 && <>; {pct(g.top_correct_unconfirmed)} of the {g.unconfirmed} made before the NHL confirmed the goalie</>}.
        </p>
      )}
      <Calibration bins={w.calibration} label="Home win chance" what="Logged home win chances against how often the home team won." />
      <Calibration bins={g.calibration} label="Top pick's chance" what="Starter picks made before confirmation, against how often that goalie started." />
    </>
  )
}

/** How well the site's predictions did so far this season, replayed game by game with only what was known beforehand. */
export default function Accuracy() {
  const [state, setState] = useState({ data: null, error: null })
  useEffect(() => {
    let ignore = false
    fetch('/api/accuracy')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status === 404 ? 'Page not found.' : `API returned ${r.status}`))))
      .then((data) => !ignore && setState({ data, error: null }))
      .catch((error) => !ignore && setState({ data: null, error: error.message }))
    return () => { ignore = true }
  }, [])
  const { data, error } = state

  return (
    <main>
      <header>
        <h1>How accurate are the predictions?</h1>
        <p>
          Owner only. The first section grades predictions the site stored before each game; the replay sections below it rebuild the past.
        </p>
        <p>
          Each prediction here is graded fairly: the season is replayed in date order, and before each day's games the model is rebuilt from
          only the games played earlier, so nothing sees its own result. This covers the win chances on the Tonight page and the probable-goalie
          model, over this season only (expected goals are stored game by game just for this season). The skater projections are documented on
          the Projections page.
        </p>
      </header>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && (
        <>
          <section><h2>Logged before the games</h2><LiveSection live={data.live} /></section>
          <section><h2>Game win chances (season replay)</h2><WinSection w={data.win} /></section>
          <section><h2>Probable goalies (season replay)</h2><GoalieSection g={data.goalie} /></section>
        </>
      )}
    </main>
  )
}
