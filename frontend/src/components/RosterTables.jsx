import { Link } from 'react-router-dom'
import Avatar from './Avatar.jsx'
import Spark from './Spark.jsx'
import { LuckBadge } from './Luck.jsx'
import { RoleBadge } from './Roles.jsx'
import { GOALIE_CATS, SKATER_CATS, fantasyPoints } from '../fantasy.js'
import { fmt1, fmtSv as sv } from '../format.js'
import { describe } from '../glossary.js'

const signed = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)
const sum = (rows, key) => rows.reduce((t, r) => t + (r?.[key] ?? 0), 0)
const teamOf = (t) => (t ?? '').split(',').pop().trim()

const VALUE_TIP = 'Worth over the rest of the season, above the best free player at the position, under your league settings'

// What differs between the two tables: the stat columns either side of fantasy points and value, the badges after a name, and how the
// last-10 strip is drawn. `before` columns show a season total and are summed in the footer unless `total` is false.
const stat = (head, key, total = true) => ({ head, key, total })
const KINDS = {
  skater: {
    title: 'Skaters', head: 'Player', cats: SKATER_CATS, route: 'player', luckKey: 'skaters',
    sparkTip: 'Points in each of the last 10 games, oldest on the left',
    spark: (games) => { const v = games.map((g) => g.points); return { values: v, max: 3, label: `Points in the last ${v.length} games, oldest first: ${v.join(', ')} (${v.reduce((t, x) => t + x, 0)} total)` } },
    before: [stat('GP', 'games_played', false), stat('G', 'goals'), stat('A', 'assists'), stat('P', 'points')],
    after: [{
      head: 'Pace', cell: (r) => fmt1(r.point_pace), total: (rows) => fmt1(sum(rows, 'point_pace')),
      title: (r) => `Last 10 games: ${r.recent_points ?? '–'} points, a pace of ${fmt1(r.recent_pace)}`,
    }],
    flags: (p, row, { luck, roles }) => (
      <>
        {row?.traded && <span className="badge">↔ traded</span>}
        {row?.games_out >= 2 && <span className="badge warn" title="Not in the team's last games">out {row.games_out}</span>}
        <RoleBadge row={roles?.[p.id]} />
        <LuckBadge row={luck?.skaters?.[p.id]} />
      </>
    ),
  },
  goalie: {
    title: 'Goalies', head: 'Goalie', cats: GOALIE_CATS, route: 'goalie', luckKey: 'goalies',
    sparkTip: 'Save percentage in each of the last 10 starts, oldest on the left; red is below .900',
    spark: (games) => { const v = games.map((g) => g.save_pct); return { values: v, floor: 0.8, max: 1, bad: (x) => x != null && x < 0.9, label: `Save percentage in the last ${v.length} starts, oldest first: ${v.map(sv).join(', ')}` } },
    before: [stat('GP', 'games_played'), stat('W', 'wins'), stat('L', 'losses')],
    after: [
      { head: 'SV%', cell: (r) => sv(r.save_pct), title: (r) => `Recent save percentage ${sv(r.recent_save_pct)}` },
      { head: 'GAA', cell: (r) => r.gaa?.toFixed(2) },
      { head: 'GSAA', cell: (r) => signed(r.gsaa) },
    ],
    flags: (p, row, { luck }) => <LuckBadge row={luck?.goalies?.[p.id]} goalie />,
  },
}

/** A value with a bar behind it, scaled to the best player on the roster so the strong spots stand out at a glance. */
function ValueCell({ value, top }) {
  if (value == null) return <td>–</td>
  const pct = top > 0 ? Math.max(0, Math.min(100, (value / top) * 100)) : 0
  return (
    <td className="value-cell" title={VALUE_TIP}>
      <span className="vbar" aria-hidden="true"><i style={{ width: `${pct}%` }} /></span>
      <strong>{value.toFixed(1)}</strong>
    </td>
  )
}

/** One table: a row per rostered player of this kind, with a footer total when there is more than one with stats. */
function RosterTable({ kind, rows, ctx }) {
  const k = KINDS[kind]
  const { isCats, scoring, form, valueOf, top, onRemove } = ctx
  const withStats = rows.map((r) => r.row).filter(Boolean)
  const points = (row) => fantasyPoints(row, k.cats, scoring)
  const statCols = k.before.length + (isCats ? 0 : 1) + 1 + k.after.length
  const valueTotal = withStats.reduce((t, r) => t + (valueOf(r.player_id) ?? 0), 0)

  const strip = (id) => {
    const games = form?.[id]?.games
    if (!games) return form ? <span className="muted">–</span> : <span className="spark-wait" aria-hidden="true" />
    return <Spark {...k.spark(games)} />
  }

  return (
    <>
      <h2>{k.title}</h2>
      <div className="table-wrap">
        <table className="roster-table">
          <thead>
            <tr>
              <th className="left">{k.head}</th>
              <th title={k.sparkTip}>Last 10</th>
              {k.before.map((c) => <th key={c.head} title={describe(c.head)}>{c.head}</th>)}
              {!isCats && <th title={describe('Fantasy pts')}>Fantasy pts</th>}
              <th title={VALUE_TIP}>Value</th>
              {k.after.map((c) => <th key={c.head} title={describe(c.head)}>{c.head}</th>)}
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map(({ p, row }) => (
              <tr key={p.id}>
                <td className="left player-cell roster-player">
                  <Avatar playerId={p.id} team={row?.team} name={p.name} size={36} />
                  <span className="roster-name">
                    <Link to={`/${k.route}/${p.id}`}>{p.name}</Link>
                    <small>{row ? <><span className="pos-pill">{kind === 'goalie' ? 'G' : row.position}</span> {teamOf(row.team)}</> : <span className="muted">No games this season</span>}</small>
                  </span>
                  <span className="roster-flags">{k.flags(p, row, ctx)}</span>
                </td>
                <td className="spark-cell">{row ? strip(p.id) : null}</td>
                {row ? (
                  <>
                    {k.before.map((c) => <td key={c.head}>{row[c.key]}</td>)}
                    {!isCats && (
                      <td className="accent" title={row.games_played ? `${(points(row) / row.games_played).toFixed(2)} per game` : undefined}>
                        {points(row).toFixed(1)}
                      </td>
                    )}
                    <ValueCell value={valueOf(p.id)} top={top} />
                    {k.after.map((c) => <td key={c.head} title={c.title?.(row)}>{c.cell(row)}</td>)}
                  </>
                ) : <td colSpan={statCols} />}
                <td><button className="link-button" onClick={() => onRemove(p)}>Remove</button></td>
              </tr>
            ))}
          </tbody>
          {withStats.length > 1 && (
            <tfoot>
              <tr>
                <td className="left">Team total</td><td />
                {k.before.map((c) => <td key={c.head}>{c.total ? sum(withStats, c.key) : ''}</td>)}
                {!isCats && <td className="accent">{withStats.reduce((t, r) => t + points(r), 0).toFixed(1)}</td>}
                <td className="accent">{valueTotal.toFixed(1)}</td>
                {k.after.map((c) => <td key={c.head}>{c.total?.(withStats)}</td>)}
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </>
  )
}

/** Skater and goalie tables for the roster tab: a face, a last-10 strip and a value bar per player instead of a wall of numbers. */
export default function RosterTables({ data, players, values, isCats, scoring, luck, roles, form, onRemove }) {
  const valueOf = (id) => values?.get(id)?.value ?? null
  const ctx = { isCats, scoring, luck, roles, form, valueOf, top: Math.max(0, ...players.map((p) => valueOf(p.id) ?? 0)), onRemove }
  const rowsOf = (kind) => players
    .filter((p) => p.kind === kind)
    .map((p) => ({ p, row: (kind === 'goalie' ? data?.goalies : data?.skaters)?.find((r) => r.player_id === p.id) }))
  const skaters = rowsOf('skater')
  const goalies = rowsOf('goalie')
  return (
    <>
      {skaters.length > 0 && <RosterTable kind="skater" rows={skaters} ctx={ctx} />}
      {goalies.length > 0 && <RosterTable kind="goalie" rows={goalies} ctx={ctx} />}
    </>
  )
}
