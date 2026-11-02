import { useEffect, useState } from 'react'
import { STATE_LABEL, clutchVerdict, signed } from '../scoreState.js'
import { seasonLabel } from '../career.js'
import { describe } from '../glossary.js'

function useScoreState(id, span) {
  const key = `${id}/${span}`
  const [result, setResult] = useState({ key: null, data: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/skaters/${id}/score-state?span=${span}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setResult({ key, data }))
      .catch(() => !ignore && setResult({ key, data: null }))
    return () => { ignore = true }
  }, [id, span, key])
  return result.key === key ? result.data : null
}

function Row({ label, f }) {
  return (
    <tr>
      <td className="left">{label}</td>
      <td>{f.attempts}</td><td>{f.goals}</td><td>{f.xg.toFixed(1)}</td><td className="accent">{signed(f.gsax)}</td>
    </tr>
  )
}

const HEAD = (first) => (
  <thead>
    <tr>
      <th className="left">{first}</th><th title="Shot attempts that were on goal, missed, or scored, with an expected-goal figure">Attempts</th>
      <th>Goals</th><th title="Expected goals from the quality of those shots">xG</th><th title={describe('GSAx')}>Goals vs xG</th>
    </tr>
  </thead>
)

/** Player-page panel: finishing in close, late moments against the rest of his shots, and by score state. */
export default function ScoreState({ playerId }) {
  const [span, setSpan] = useState('all')
  const data = useScoreState(playerId, span)
  if (!data) return null
  if (data.close_late.attempts + data.other.attempts === 0) return null
  const bt = data.backtest
  const seasons = data.seasons
  return (
    <section>
      <h2>Close games and clutch</h2>
      <p className="sub">
        Finishing in close, late moments (third period, the score within one goal) against his own finishing in all his other
        shots{seasons.length ? `, ${seasons.length === 1 ? seasonLabel(seasons[0]) : `${seasons.length} seasons`}` : ''}. Goals are rare,
        so a few of them either way move these figures a lot.
      </p>
      <div className="controls">
        <label>Show{' '}
          <select value={span} onChange={(e) => setSpan(e.target.value)} aria-label="Seasons">
            <option value="all">All seasons with shot times</option>
            <option value="current">This season only</option>
          </select>
        </label>
      </div>
      <div className="table-wrap">
        <table>
          {HEAD('Situation')}
          <tbody>
            <Row label="Close and late" f={data.close_late} />
            <Row label="Everything else" f={data.other} />
          </tbody>
        </table>
      </div>
      <p>
        {data.expected_goals != null && (
          <>His finishing everywhere else predicts {data.expected_goals.toFixed(1)} goals on his close-and-late shots; he has {data.close_late.goals}. </>
        )}
        <strong>{clutchVerdict(data.z)}</strong>
      </p>

      <div className="table-wrap">
        <table>
          {HEAD('By score state')}
          <tbody>
            {['trailing', 'tied', 'leading'].map((g) => <Row key={g} label={`${g[0].toUpperCase()}${g.slice(1)}`} f={data.states[g]} />)}
          </tbody>
        </table>
      </div>
      <p className="def-foot">
        By score state counts even-strength shots in regulation only. Trailing and leading include {STATE_LABEL.trail1.toLowerCase()} and
        {' '}{STATE_LABEL.trail2.toLowerCase()}, and the same for leads.
        {bt && bt.r_clutch != null && (
          <>
            {' '}Does clutch repeat? Across {bt.pairs} consecutive-season pairs of players with at least {bt.min_attempts} close-and-late shots
            in each, the correlation of the two seasons' clutch scores was {bt.r_clutch.toFixed(2)}
            {bt.r_finishing != null && <> (finishing in general: {bt.r_finishing.toFixed(2)})</>}; {(bt.share_beyond_2 * 100).toFixed(0)}% of
            player-seasons were beyond two standard deviations, against about {(bt.expected_beyond_2 * 100).toFixed(0)}% by chance alone.
          </>
        )}
      </p>
    </section>
  )
}
