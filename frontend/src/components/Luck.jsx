import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { seasonLabel } from '../career.js'
import { describe } from '../glossary.js'

const n1 = (v) => (v == null ? '–' : v.toFixed(1))
const signed = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(1)}`)
const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

/** Luck figures for a list of player ids (skaters and goalies), keyed by id. `null` until loaded. */
export function useLuck(ids) {
  const key = [...new Set(ids)].sort((a, b) => a - b).join(',')
  const [state, setState] = useState({ key: null, data: null })
  useEffect(() => {
    if (!key) return undefined
    let ignore = false
    fetch(`/api/luck/players?ids=${key}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setState({ key, data }))
      .catch(() => !ignore && setState({ key, data: null }))
    return () => { ignore = true }
  }, [key])
  return state.key === key ? state.data : null
}

/**
 * The figures a badge or panel shows for one row. Skaters are measured against their own history of finishing when
 * we have it (so a proven elite finisher isn't called lucky for being good); goalies against an average goalie.
 */
function figures(row, goalie) {
  if (goalie) return { flag: row.flag, z: row.z, diff: row.gsax }
  return {
    flag: row.points_flag_adj ?? row.points_flag ?? row.flag_adj ?? row.flag,
    z: row.points_z_adj ?? row.points_z ?? row.z_adj ?? row.z,
    pointsDiff: row.points_diff_adj ?? row.points_diff,
    xpoints: row.xpoints_adj ?? row.xpoints,
    goalsDiff: row.diff_adj ?? row.diff,
  }
}

/** { z, flag, enough } for one luck row, the same figures the badge shows (see tradeIdeas.js). */
export function luckSummary(row, goalie) {
  const { z, flag } = figures(row, goalie)
  return { z, flag, enough: Boolean(row.enough) }
}

/** The row's own flag: points luck for skaters, goals saved above expected for goalies. Null while the sample is small. */
export function luckFlag(row, goalie) {
  if (!row || !row.enough) return null
  const { flag } = figures(row, goalie)
  return flag === 'hot' || flag === 'cold' ? flag : null
}

/** A small "hot" / "cold" badge for a roster table, or nothing when the player is steady or the sample is small. */
export function LuckBadge({ row, goalie }) {
  const flag = luckFlag(row, goalie)
  if (!flag) return null
  const { z } = figures(row, goalie)
  const what = goalie
    ? flag === 'hot' ? 'stopping more than the shots faced should allow' : 'stopping fewer than the shots faced should allow'
    : flag === 'hot' ? 'scoring more than their shots and their own track record predict' : 'scoring less than their shots and their own track record predict'
  return (
    <span className={flag === 'hot' ? 'badge' : 'badge warn'} title={`${flag === 'hot' ? 'Running hot' : 'Running cold'}: ${what} (z ${signed(z)}). Small samples are noisy.`}>
      {flag}
    </span>
  )
}

function Tile({ label, value, note }) {
  return (
    <div className="tile">
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <small className="muted">{note}</small>}
    </div>
  )
}

const STATUS = { hot: 'Running hot', cold: 'Running cold', steady: 'Steady' }

/** Season by season: goals against the xG of a skater's shots, or goals saved above expected for a goalie. */
function History({ playerId, goalie }) {
  const [state, setState] = useState({ id: null, data: null })
  useEffect(() => {
    let ignore = false
    fetch(`/api/luck/history/${playerId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => !ignore && setState({ id: playerId, data }))
      .catch(() => !ignore && setState({ id: playerId, data: null }))
    return () => { ignore = true }
  }, [playerId])
  const data = state.id === playerId ? state.data : null
  if (!data || data.kind !== (goalie ? 'goalie' : 'skater') || data.seasons.length < 2) return null
  const rows = [...data.seasons, { ...data.career, season_id: null }]
  return (
    <>
      <h3>{goalie ? 'Goals saved above expected, by season' : 'Finishing, by season'}</h3>
      <p className="sub">
        {goalie
          ? 'A goalie\'s luck rarely repeats, so a big number in one season says little about the next.'
          : 'Goals against the xG of their shots, season by season. Consistently above zero is skill; a lone big year is luck.'}
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="left">Season</th>
              {goalie ? <><th title={describe('Shots faced')}>Shots faced</th><th title={describe('Goals allowed')}>Goals allowed</th><th title={describe('xGA')}>xGA</th><th title={describe('GSAx')}>GSAx</th></> : <><th title={describe('Attempts')}>Attempts</th><th>Goals</th><th title={describe('xG')}>xG</th><th title={describe('G − xG')}>G − xG</th></>}
              <th title={describe('Z')}>Z</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.season_id ?? 'career'} style={r.season_id == null ? { fontWeight: 600 } : undefined}>
                <td className="left">{r.season_id == null ? 'All stored seasons' : seasonLabel(r.season_id)}</td>
                {goalie
                  ? <><td>{r.faced}</td><td>{r.goals}</td><td>{n1(r.xga)}</td><td className="accent">{signed(r.gsax)}</td></>
                  : <><td>{r.attempts}</td><td>{r.goals}</td><td>{n1(r.xg)}</td><td className="accent">{signed(r.diff)}</td></>}
                <td>{signed(r.z)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

/** Luck & regression for one player this season, on a player or goalie page. */
export default function LuckPanel({ playerId, goalie }) {
  const data = useLuck([playerId])
  const row = data?.[goalie ? 'goalies' : 'skaters']?.[playerId]
  if (!row) return null
  const f = figures(row, goalie)
  return (
    <section>
      <h2>Luck &amp; regression</h2>
      <p className="sub">
        {goalie
          ? 'Goals allowed against the goals an average goalie would allow on the same shots (our expected-goals model).'
          : 'Goals and points against what their shots predict, plus the shots of the teammates they skate with'}
        {!goalie && (row.has_history
          ? `, measured against their own finishing in ${row.prior_seasons} earlier season${row.prior_seasons === 1 ? '' : 's'} (${signed(row.skill * 100)}% vs an average shooter's goals from the same shots).`
          : '. There is no earlier season on file for this player, so this compares them with an average shooter.')}
        {' '}Early in a season a few games swing this a lot.
        {' '}<Link to="/luck">See everyone →</Link>
      </p>
      {!row.enough && (
        <p className="status">Small sample so far ({goalie ? `${row.faced} shots faced` : `${row.attempts} shot attempts`}), so no hot or cold label yet.</p>
      )}
      <div className="tiles">
        {goalie ? (
          <>
            <Tile label="Goals saved above expected" value={signed(row.gsax)} note={`${row.goals} allowed, ${n1(row.xga)} expected`} />
            <Tile label="Save %" value={sv(row.sv_pct)} note={`${sv(row.xsv_pct)} expected`} />
            <Tile label="Per 100 shots" value={signed(row.gsax_per_100)} note={`${row.faced} shots faced`} />
          </>
        ) : (
          <>
            <Tile label="Points" value={row.points ?? '–'} note={f.xpoints == null ? null : `${n1(f.xpoints)} expected (${signed(f.pointsDiff)})`} />
            <Tile label="Goals" value={row.goals} note={`${n1(row.ixg)} xG, ${signed(f.goalsDiff)} vs their norm`} />
            <Tile label="Assist luck" value={signed(row.assist_luck)} note="estimate from teammates' finishing" />
            <Tile label="On-ice luck (5v5)" value={signed(row.onice_diff)} note={row.pdo == null ? null : `PDO ${row.pdo.toFixed(3)}`} />
          </>
        )}
        {row.enough && <Tile label="Status" value={STATUS[f.flag] ?? '–'} note={`z ${signed(f.z)}`} />}
      </div>
      <History playerId={playerId} goalie={goalie} />
    </section>
  )
}
