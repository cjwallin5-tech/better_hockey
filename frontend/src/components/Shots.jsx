import { useEffect, useState } from 'react'
import ShotMap from './ShotMap.jsx'

function useJson(url) {
  const [state, setState] = useState({ url: null, data: null })
  useEffect(() => {
    let ignore = false
    fetch(url)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setState({ url, data }))
      .catch(() => !ignore && setState({ url, data: null }))
    return () => { ignore = true }
  }, [url])
  return state.url === url ? state.data : null
}

const signed = (v, d = 1) => `${v > 0 ? '+' : ''}${v.toFixed(d)}`

const NOTE =
  'Expected goals (xG) come from our own model: each unblocked attempt gets a goal probability from its distance, angle, shot type, rebound and strength, trained on last season. Empty-net shots are excluded.'

function Tile({ label, value, hint }) {
  return (
    <div className="tile" title={hint}>
      <span>{label}</span>
      <strong>{value ?? '–'}</strong>
    </div>
  )
}

export function SkaterShots({ playerId }) {
  const data = useJson(`/api/skaters/${playerId}/shots`)
  if (!data || data.shots.length === 0) return null
  const s = data.summary, o = data.onice
  const goalsVsXg = s.model_goals - s.ixg
  const xgfPct = o.xgf + o.xga > 0 ? (100 * o.xgf) / (o.xgf + o.xga) : null
  return (
    <section>
      <h2>Shot map &amp; expected goals</h2>
      <p className="sub">{NOTE}</p>
      <div className="tiles">
        <Tile label="Individual xG" value={s.ixg.toFixed(1)} />
        <Tile label="Goals (non-empty-net)" value={s.model_goals} />
        <Tile label="Goals − xG" value={signed(goalsVsXg)} hint="Positive means finishing above what the chances suggested" />
        <Tile label="Shots on goal" value={s.on_goal} />
        <Tile label="Avg shot distance" value={s.avg_distance ? `${s.avg_distance.toFixed(0)} ft` : null} />
        <Tile label="On-ice xGF% (5v5)" value={xgfPct == null ? null : xgfPct.toFixed(1)} hint="Share of expected goals while on the ice at 5v5" />
      </div>
      <ShotMap shots={data.shots} caption="This season's shots" />
    </section>
  )
}

export function TeamShots({ abbrev }) {
  const data = useJson(`/api/teams/${abbrev}/shots`)
  const [side, setSide] = useState('for')
  if (!data || (data.for.length === 0 && data.against.length === 0)) return null
  const t = data.totals
  return (
    <section>
      <h2>Shot maps</h2>
      <p className="sub">{NOTE}</p>
      <div className="tiles">
        <Tile label="xG for" value={t.xgf?.toFixed(1)} />
        <Tile label="xG against" value={t.xga?.toFixed(1)} />
        <Tile label="xG difference" value={t.xgf != null ? signed(t.xgf - t.xga) : null} />
        <Tile label="Goals for / against" value={`${t.gf} / ${t.ga}`} hint="Includes empty-net goals the model doesn't score" />
      </div>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={side === 'for'} className={side === 'for' ? 'on' : ''} onClick={() => setSide('for')}>Shots taken</button>
        <button role="tab" aria-selected={side === 'against'} className={side === 'against' ? 'on' : ''} onClick={() => setSide('against')}>Shots allowed</button>
      </div>
      <ShotMap key={side} shots={data[side]} caption={side === 'for' ? `${abbrev} shots taken` : `${abbrev} shots allowed`} />
    </section>
  )
}

export function GoalieShots({ playerId }) {
  const data = useJson(`/api/goalies/${playerId}/shots`)
  if (!data || data.shots.length === 0) return null
  const s = data.summary
  const gsax = s.xga - s.model_goals
  return (
    <section>
      <h2>Shots faced &amp; goals saved above expected</h2>
      <p className="sub">{NOTE} Goals saved above expected (GSAx) is the xG of the shots faced minus the goals allowed on them, with xG scaled so the league's expected goals on shots on goal match its actual goals.</p>
      <div className="tiles">
        <Tile label="Shots faced" value={s.faced} />
        <Tile label="xG faced" value={s.xga.toFixed(1)} />
        <Tile label="Goals allowed (non-empty-net)" value={s.model_goals} />
        <Tile label="GSAx" value={signed(gsax)} hint="Positive means fewer goals than the shots' quality suggested" />
      </div>
      <ShotMap shots={data.shots} caption="Shots faced this season" />
    </section>
  )
}
