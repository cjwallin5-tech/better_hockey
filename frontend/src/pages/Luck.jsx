import { useEffect, useState } from 'react'
import { getJson } from '../lists.js'
import PageShell from '../components/PageShell.jsx'
import { Link } from 'react-router-dom'
import { seasonLabel } from '../career.js'
import { useUrlSync } from '../urlState.js'
import { describe } from '../glossary.js'
import { Skeleton } from '../components/Skeleton.jsx'
import LuckGuide from '../components/LuckGuide.jsx'

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

// One real row from the table, read out loud, so the numbers have a meaning before anyone studies the columns.
function SkaterExample({ row, dir, rank, vs }) {
  const goals = rank === 'goals'
  const adj = vs === 'own'
  const actual = goals ? row.goals : row.points
  const gap = goals ? (adj ? row.diff_adj : row.diff) : (adj ? row.points_diff_adj : row.points_diff)
  if (actual == null || gap == null) return null
  const expected = actual - gap // the table's own xG / xPts, so the sentence always matches the row
  const unit = goals ? 'goals' : 'points'
  return (
    <p className="luck-example">
      <strong>For example:</strong> <Link to={`/player/${row.player_id}`}>{row.name}</Link> has {actual} {unit}, and their shots{goals ? '' : ' and on-ice results'}{' '}
      point to about {n1(expected)}. That is {signed(gap)} {unit} {dir === 'desc' ? 'above' : 'below'} expectation, so {dir === 'desc'
        ? 'expect them to score more slowly from here.'
        : 'expect them to score faster from here.'}
    </p>
  )
}

function GoalieExample({ row, dir }) {
  if (row.xga == null || row.gsax == null) return null
  return (
    <p className="luck-example">
      <strong>For example:</strong> <Link to={`/goalie/${row.player_id}`}>{row.name}</Link> has allowed {row.goals} goals on shots worth about {n1(row.xga)}.
      That is {signed(row.gsax)} goals saved {dir === 'desc' ? 'above' : 'below'} expectation, so {dir === 'desc'
        ? 'expect their save numbers to come back toward average.'
        : 'expect their save numbers to improve.'}
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
        {' '}{vs === 'own'
          ? 'Each player is measured against their own past seasons, so good finishers are not flagged just for being good.'
          : 'Each player is measured against an average shooter, so elite finishers can show as hot even when it is just skill.'}
      </p>
      {data && data.rows.length > 0 && <SkaterExample row={data.rows[0]} dir={dir} rank={rank} vs={vs} />}
      {error && <p className="status">{error}</p>}
      {!data && !error && <Skeleton />}
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
      </p>
      {data && data.rows.length > 0 && <GoalieExample row={data.rows[0]} dir={dir} />}
      {error && <p className="status">{error}</p>}
      {!data && !error && <Skeleton />}
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

export default function Luck({ embedded = false }) {
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
    getJson('/api/meta').then((m) => setSeason(m.season_id ?? m.season ?? null)).catch(() => {})
  }, [])

  useUrlSync([['kind', kind, 'skater'], ['dir', dir, 'desc'], ['rank', rank, 'points'], ['vs', vs, 'own'], ['pos', position, ''], ['min', attempts, '20'], ['faced', faced, '50']])

  return (
    <PageShell embedded={embedded}>
      <header>
        {!embedded && <h1>Luck &amp; regression</h1>}
        <p>
          Who is scoring or saving more, or less, than their shots say they should{season ? ` in ${seasonLabel(season)}` : ''}, and what
          that means for the rest of the season. It is a way to spot sell-highs and pickups early.
        </p>
      </header>
      <LuckGuide goalie={kind === 'goalie'} />
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
    </PageShell>
  )
}
