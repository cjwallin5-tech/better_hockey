import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { seasonLabel } from '../career.js'
import { useUrlSync } from '../urlState.js'
import { describe } from '../glossary.js'

const n1 = (v) => (v == null ? '–' : v.toFixed(1))
const signed = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(1)}`)
const pct = (v) => (v == null ? '–' : `${(v * 100).toFixed(1)}%`)
const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

function useApi(url) {
  const [state, setState] = useState({ url: null, data: null, error: null })
  useEffect(() => {
    let ignore = false
    fetch(url)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`API returned ${r.status}`))))
      .then((data) => !ignore && setState({ url, data, error: null }))
      .catch((error) => !ignore && setState({ url, data: null, error: error.message }))
    return () => { ignore = true }
  }, [url])
  return state.url === url ? state : { data: null, error: null }
}

// Hot and cold are spelled out so the meaning never rests on colour alone.
function Flag({ flag, goalie }) {
  if (flag === 'hot') return <span className="badge">{goalie ? 'Saving more than expected' : 'Running hot'}</span>
  if (flag === 'cold') return <span className="badge warn">{goalie ? 'Saving less than expected' : 'Running cold'}</span>
  return <span className="status">Steady</span>
}

// How much of last year's luck figure carries into this year: the honest answer to "is this skill or luck?".
function Persistence({ goalie }) {
  const { data } = useApi('/api/luck/persistence')
  const p = data?.[goalie ? 'goalies' : 'skaters']
  if (!p || p.r == null) return null
  const word = p.r < 0.15 ? 'almost all luck' : p.r < 0.35 ? 'mostly luck, with some skill' : p.r < 0.6 ? 'a real mix of skill and luck' : 'mostly skill'
  return (
    <p className="sub">
      How much is luck? Across {p.n} {goalie ? 'goalie' : 'skater'} seasons with at least {goalie ? data.min_faced : data.min_attempts}{' '}
      {goalie ? 'shots faced' : 'shot attempts'} in both years, one year's {goalie ? 'goals saved above expected' : 'gap to xG'} predicts
      the next year's with a correlation of {p.r.toFixed(2)} ({word}; 0 would be pure luck, 1 pure skill).
    </p>
  )
}

function SkaterBoard({ dir, rank, setRank, vs, setVs, position, setPosition, min, setMin }) {
  const { data, error } = useApi(`/api/luck/skaters?dir=${dir}&rank=${rank}&vs=${vs}&position=${position}&min_attempts=${min || 0}&limit=50`)
  // vs=own measures each player against their own past seasons' finishing; the plain fields are against an average shooter
  const f = (r, key) => (vs === 'own' ? r[`${key}_adj`] : r[key])
  return (
    <>
      <div className="h2h-picks">
        <label className="h2h-pick">Rank by
          <select value={rank} onChange={(e) => setRank(e.target.value)}>
            <option value="points">Points (goals + assists)</option>
            <option value="goals">Goals only</option>
          </select>
        </label>
        <label className="h2h-pick">Compare to
          <select value={vs} onChange={(e) => setVs(e.target.value)}>
            <option value="own">Their own history</option>
            <option value="average">An average shooter</option>
          </select>
        </label>
        <label className="h2h-pick">Position
          <select value={position} onChange={(e) => setPosition(e.target.value)}>
            {[['', 'All skaters'], ['F', 'Forwards'], ['C', 'Centers'], ['L', 'Left wings'], ['R', 'Right wings'], ['D', 'Defensemen']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="h2h-pick">Min shot attempts
          <input type="number" min="0" max="500" value={min} onChange={(e) => setMin(e.target.value)} style={{ minWidth: 80, width: 80 }} />
        </label>
      </div>
      <p className="sub">
        {dir === 'desc'
          ? 'Scoring far more than their shots predict. Some of this will cool off.'
          : 'Scoring far less than their shots predict. Some of this should bounce back.'}
        {' '}"xG" is what an average shooter would score from the same shots (our own model). "Z" is the gap measured in
        standard deviations of chance: past {data?.z_flag ?? 1.5} is flagged, past 2 is a real outlier for the sample so far.
      </p>
      <p className="sub">
        Points luck = the goal gap plus an estimate of assists gained or lost: when teammates score more (or less) than their
        shots predict while this player is on the ice, they pick up assists at their usual rate. We don't track who assisted
        each shot, so the assist part is a rough estimate and leaves out power-play assists. "xPts" is points minus that luck.
        {vs === 'own'
          ? ' Compared with their own history: a player who has beaten xG for years is measured against that higher bar (past seasons come from the last four years of stored shots), so elite finishers stop looking lucky just for being good.'
          : ' Compared with an average shooter: elite finishers will show as hot even when it is just skill.'}
      </p>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && data.rows.length === 0 && <p className="status">No skaters meet that minimum yet.</p>}
      {data && data.rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th><th className="left">Player</th><th className="left" title={describe('Team')}>Team</th><th className="left" title={describe('Pos')}>Pos</th>
                <th title={describe('GP')}>GP</th><th>Points</th><th title={describe('xPts')}>xPts</th><th title={describe('Pts luck')}>Pts luck</th><th title="Of the points luck, the part from assists">Assist part</th><th title={describe('Pts Z')}>Pts Z</th>
                <th title="Goals minus xG over earlier seasons we have shots for. Positive means a history of finishing above the shots.">Past G − xG</th>
                <th title={describe('Attempts')}>Attempts</th><th>Goals</th><th title={describe('xG')}>xG</th><th title={describe('G − xG')}>G − xG</th><th title={describe('Goals Z')}>Goals Z</th>
                <th title={describe('Sh%')}>Sh%</th><th title={describe('xSh%')}>xSh%</th><th>{data.games}-game pace (G / xG)</th>
                <th title="5v5 goals for minus against, compared with the expected goals for minus against, while on the ice">On-ice luck</th>
                <th title="On-ice shooting % plus save % at 5v5 (NHL figure). 1.000 is average; far above tends to drift back.">PDO</th>
                <th className="left" title={describe('Status')}>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={r.player_id}>
                  <td>{i + 1}</td>
                  <td className="left"><Link to={`/player/${r.player_id}`}>{r.name}</Link></td>
                  <td className="left">{r.team}</td><td className="left">{r.position}</td>
                  <td>{r.games_played}</td><td>{r.points}</td><td>{n1(f(r, 'xpoints'))}</td>
                  <td className={rank === 'points' ? 'accent' : ''}>{signed(f(r, 'points_diff'))}</td><td>{signed(r.assist_luck)}</td><td>{signed(f(r, 'points_z'))}</td>
                  <td>{r.has_history ? `${signed(r.prior_diff)} (${r.prior_seasons}y)` : '–'}</td>
                  <td>{r.attempts}</td><td>{r.goals}</td><td>{n1(r.ixg)}</td>
                  <td className={rank === 'goals' ? 'accent' : ''}>{signed(f(r, 'diff'))}</td><td>{signed(f(r, 'z'))}</td>
                  <td>{pct(r.sh_pct)}</td><td>{pct(r.xsh_pct)}</td>
                  <td>{n1(r.goals_pace)} / {n1(r.xg_pace)}</td>
                  <td>{signed(r.onice_diff)}</td>
                  <td>{r.pdo == null ? '–' : r.pdo.toFixed(3)}</td>
                  <td className="left"><Flag flag={rank === 'points' ? f(r, 'points_flag') : f(r, 'flag')} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function GoalieBoard({ dir, min, setMin }) {
  const { data, error } = useApi(`/api/luck/goalies?dir=${dir}&min_faced=${min || 0}&limit=50`)
  return (
    <>
      <div className="h2h-picks">
        <label className="h2h-pick">Min shots faced
          <input type="number" min="0" max="2000" value={min} onChange={(e) => setMin(e.target.value)} style={{ minWidth: 80, width: 80 }} />
        </label>
      </div>
      <p className="sub">
        {dir === 'desc'
          ? 'Stopping more than the shots they faced should allow. Some of this will cool off.'
          : 'Stopping fewer than the shots they faced should allow. Some of this should bounce back.'}
        {' '}"xGA" is the goals an average goalie would allow on the same shots. Goals saved above expected (GSAx) is xGA minus
        goals allowed.
      </p>
      {error && <p className="status">{error}</p>}
      {!data && !error && <p className="status">Loading…</p>}
      {data && data.rows.length === 0 && <p className="status">No goalies meet that minimum yet.</p>}
      {data && data.rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th><th className="left">Goalie</th><th className="left" title={describe('Team')}>Team</th><th title={describe('GP')}>GP</th><th title={describe('Shots faced')}>Shots faced</th>
                <th title={describe('Goals allowed')}>Goals allowed</th><th title={describe('xGA')}>xGA</th><th title={describe('GSAx')}>GSAx</th><th title={describe('Per 100 shots')}>Per 100 shots</th><th title={describe('Z')}>Z</th><th title={describe('Sv%')}>Sv%</th><th title={describe('xSv%')}>xSv%</th>
                <th className="left" title={describe('Status')}>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r, i) => (
                <tr key={r.player_id}>
                  <td>{i + 1}</td>
                  <td className="left"><Link to={`/goalie/${r.player_id}`}>{r.name}</Link></td>
                  <td className="left">{r.team ?? '–'}</td>
                  <td>{r.games_played}</td><td>{r.faced}</td><td>{r.goals}</td><td>{n1(r.xga)}</td>
                  <td className="accent">{signed(r.gsax)}</td><td>{signed(r.gsax_per_100)}</td><td>{signed(r.z)}</td>
                  <td>{sv(r.sv_pct)}</td><td>{sv(r.xsv_pct)}</td>
                  <td className="left"><Flag flag={r.flag} goalie /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export default function Luck() {
  const initial = new URLSearchParams(window.location.search)
  const [kind, setKind] = useState(initial.get('kind') === 'goalie' ? 'goalie' : 'skater')
  const [dir, setDir] = useState(initial.get('dir') === 'asc' ? 'asc' : 'desc')
  const [rank, setRank] = useState(initial.get('rank') === 'goals' ? 'goals' : 'points')
  const [vs, setVs] = useState(initial.get('vs') === 'average' ? 'average' : 'own')
  const [position, setPosition] = useState(initial.get('pos') ?? '')
  const [attempts, setAttempts] = useState(initial.get('min') ?? '20')
  const [faced, setFaced] = useState(initial.get('faced') ?? '50')
  const [season, setSeason] = useState(null)
  useEffect(() => {
    fetch('/api/meta').then((r) => r.json()).then((m) => setSeason(m.season_id ?? m.season ?? null)).catch(() => {})
  }, [])

  useUrlSync([['kind', kind, 'skater'], ['dir', dir, 'desc'], ['rank', rank, 'points'], ['vs', vs, 'own'], ['pos', position, ''], ['min', attempts, '20'], ['faced', faced, '50']])

  return (
    <main>
      <header>
        <h1>Luck &amp; regression</h1>
        <p>
          Who is scoring or saving more, or less, than their shots say they should{season ? ` in ${seasonLabel(season)}` : ''}. Hot
          streaks built on lucky finishing tend to fade and cold ones tend to recover, so this is a way to spot pickups and
          sell-highs early. It uses our own expected-goals model, which doesn't know who is shooting: elite finishers beat it
          every year, and early in a season a few games can swing everything, so treat these as hints, not verdicts.
        </p>
      </header>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={kind === 'skater'} className={kind === 'skater' ? 'on' : ''} onClick={() => setKind('skater')}>Skaters</button>
        <button role="tab" aria-selected={kind === 'goalie'} className={kind === 'goalie' ? 'on' : ''} onClick={() => setKind('goalie')}>Goalies</button>
      </div>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={dir === 'desc'} className={dir === 'desc' ? 'on' : ''} onClick={() => setDir('desc')}>Running hot</button>
        <button role="tab" aria-selected={dir === 'asc'} className={dir === 'asc' ? 'on' : ''} onClick={() => setDir('asc')}>Running cold</button>
      </div>
      <Persistence goalie={kind === 'goalie'} />
      {kind === 'skater'
        ? <SkaterBoard dir={dir} rank={rank} setRank={setRank} vs={vs} setVs={setVs} position={position} setPosition={setPosition} min={attempts} setMin={setAttempts} />
        : <GoalieBoard dir={dir} min={faced} setMin={setFaced} />}
    </main>
  )
}
