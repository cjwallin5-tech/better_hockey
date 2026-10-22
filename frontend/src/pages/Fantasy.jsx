import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import PageTabs from '../components/PageTabs.jsx'
import FantasyWeek from '../components/FantasyWeek.jsx'
import GoalieStarts from '../components/GoalieStarts.jsx'
import Pickups from '../components/Pickups.jsx'
import { useAuth } from '../auth.js'
import RosterTools from '../components/RosterTools.jsx'
import { LuckBadge, useLuck } from '../components/Luck.jsx'
import { RoleBadge, useRoles } from '../components/Roles.jsx'
import { GOALIE_CATS, SCORING_PRESETS, SKATER_CATS, fantasyPoints, useFantasy, useLeague, useScoring } from '../fantasy.js'
import PlayerValues from '../components/PlayerValues.jsx'
import TradeAnalyzer from '../components/TradeAnalyzer.jsx'
import TradeIdeas from '../components/TradeIdeas.jsx'
import StreamingGoalies from '../components/StreamingGoalies.jsx'
import { GROUPS, cleanLeague, playerValues } from '../value.js'
import { categoryValues } from '../categories.js'
import { CATEGORY_PRESETS, GOALIE_CATEGORIES, SKATER_CATEGORIES } from '../categoryDefs.js'
import { fmt1 } from '../format.js'
import { describe } from '../glossary.js'

const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))
const signed = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)
const sum = (rows, key) => rows.reduce((t, r) => t + (r?.[key] ?? 0), 0)

const fp = (v) => v.toFixed(1)

function ScoringSettings({ scoring, setScoring }) {
  const setCat = (key, value) => {
    const next = { ...scoring }
    if (value === '' || Number.isNaN(Number(value))) delete next[key]
    else next[key] = Number(value)
    setScoring(next)
  }
  const field = ([key, label]) => (
    <label key={key} className="scoring-field">
      <input type="number" step="any" value={scoring[key] ?? ''} placeholder="0" onChange={(e) => setCat(key, e.target.value)} />
      <span>{label}</span>
    </label>
  )
  return (
    <details className="scoring" open>
      <summary>League scoring</summary>
      <p className="muted">Points per stat, to match your league's rules. Leave a stat blank to ignore it. Negative values work (e.g. goals against).</p>
      <div className="tabs" role="group" aria-label="Scoring presets">
        {Object.entries(SCORING_PRESETS).map(([name, preset]) => (
          <button key={name} onClick={() => setScoring(preset)}>{name}</button>
        ))}
      </div>
      <h3>Skaters</h3>
      <div className="scoring-grid">{SKATER_CATS.map(field)}</div>
      <h3>Goalies</h3>
      <div className="scoring-grid">{GOALIE_CATS.map(field)}</div>
    </details>
  )
}

function LeagueSettings({ league, setLeague }) {
  const cfg = cleanLeague(league)
  const set = (patch) => setLeague({ ...cfg, ...patch })
  const toggle = (kind, key) => {
    const list = cfg.categories[kind]
    set({ categories: { ...cfg.categories, [kind]: list.includes(key) ? list.filter((k) => k !== key) : [...list, key] } })
  }
  const checks = (kind, defs) => (
    <div className="scoring-grid">
      {defs.map((d) => (
        <label key={d.key} className="scoring-field">
          <input type="checkbox" checked={cfg.categories[kind].includes(d.key)} onChange={() => toggle(kind, d.key)} />
          <span>{d.label}{d.sign < 0 ? ' (lower is better)' : ''}</span>
        </label>
      ))}
    </div>
  )
  return (
    <details className="scoring" open>
      <summary>League format and size</summary>
      <p className="muted">
        Used for player values and the trade analyzer. Replacement level is the best player at a position who wouldn't be
        starting in your league (teams × starting slots). Saved in this browser only.
      </p>
      <div className="tabs" role="group" aria-label="League format">
        <button className={cfg.format === 'points' ? 'on' : ''} onClick={() => set({ format: 'points' })}>Points league</button>
        <button className={cfg.format === 'categories' ? 'on' : ''} onClick={() => set({ format: 'categories' })}>Category league (head-to-head or roto)</button>
      </div>
      <div className="scoring-grid">
        <label className="scoring-field">
          <input type="number" min="2" max="32" value={cfg.teams} onChange={(e) => set({ teams: e.target.value })} />
          <span>Teams</span>
        </label>
        {GROUPS.map((g) => (
          <label key={g} className="scoring-field">
            <input type="number" min="0" max="10" value={cfg.slots[g]} onChange={(e) => set({ slots: { ...cfg.slots, [g]: e.target.value } })} />
            <span>{{ C: 'Center slots', L: 'Left wing slots', R: 'Right wing slots', D: 'Defense slots', G: 'Goalie slots' }[g]}</span>
          </label>
        ))}
      </div>
      {cfg.format === 'categories' && (
        <>
          <h3>Categories your league counts</h3>
          <p className="muted">
            Players are valued by how far above the rostered pool they are in each category you pick, added up (z-scores), over the
            rest of the season. Points-per-stat scoring doesn't apply in a category league.
          </p>
          <div className="tabs" role="group" aria-label="Category presets">
            {Object.entries(CATEGORY_PRESETS).map(([name, preset]) => (
              <button key={name} onClick={() => set({ categories: preset })}>{name}</button>
            ))}
          </div>
          <h3>Skaters</h3>
          {checks('skater', SKATER_CATEGORIES)}
          <h3>Goalies</h3>
          {checks('goalie', GOALIE_CATEGORIES)}
        </>
      )}
    </details>
  )
}

export default function Fantasy() {
  const { list, togglePlayer, replacePlayers } = useFantasy()
  const [params, setParams] = useSearchParams()
  const { user, sync } = useAuth()
  const { scoring, setScoring } = useScoring()
  const { league, setLeague } = useLeague()
  const [extras, setExtras] = useState(null) // games left per team and each skater's record, for player values
  const [data, setData] = useState(null)
  const [kind, setKind] = useState('skater')
  const [query, setQuery] = useState('')
  const luck = useLuck(list.players.map((p) => p.id))
  const roles = useRoles(list.players.filter((p) => p.kind === 'skater').map((p) => p.id))

  useEffect(() => {
    Promise.all([fetch('/api/skaters').then((r) => r.json()), fetch('/api/goalies').then((r) => r.json())])
      .then(([skaters, goalies]) => setData({ skaters, goalies: goalies.goalies }))
      .catch(() => setData({ skaters: [], goalies: [] }))
  }, [])

  useEffect(() => {
    Promise.all([fetch('/api/fantasy/games-left').then((r) => r.json()), fetch('/api/fantasy/priors').then((r) => r.json())])
      .then(([gl, pri]) => setExtras({ gamesLeft: gl.teams, gamesPerSeason: gl.games_per_season, priors: pri.players }))
      .catch(() => setExtras({ gamesLeft: {}, gamesPerSeason: 84, priors: {} })) // values still work, with rougher estimates
  }, [])

  // Value over replacement for every player, under your scoring and league (see value.js)
  const leagueCfg = useMemo(() => cleanLeague(league), [league])
  const isCats = leagueCfg.format === 'categories'
  const values = useMemo(() => {
    if (!data || !extras) return null
    const args = { skaters: data.skaters, goalies: data.goalies, league, ...extras }
    return isCats ? categoryValues(args) : playerValues({ ...args, scoring })
  }, [data, extras, scoring, league, isCats])
  const valueText = (id) => { const v = values?.get(id); return v ? v.value.toFixed(1) : '–' }

  const taken = useMemo(() => new Set(list.players.map((p) => p.id)), [list])
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q || !data) return []
    const pool = kind === 'goalie' ? data.goalies : data.skaters
    return pool.filter((r) => r.name.toLowerCase().includes(q) && !taken.has(r.player_id)).slice(0, 8)
  }, [query, kind, data, taken])

  const loadRoster = ({ players, scoring: sc }) => {
    replacePlayers(players)
    if (sc && Object.keys(sc).length) setScoring(sc)
    if (params.has('roster')) setParams({}, { replace: true }) // the link has done its job
  }

  const add = (r) => {
    togglePlayer({ id: r.player_id, kind, name: r.name })
    setQuery('')
  }
  const addValued = (r, k) => togglePlayer({ id: r.player_id, kind: k, name: r.name })

  const skaterRows = list.players.filter((p) => p.kind === 'skater').map((p) => ({ p, row: data?.skaters.find((s) => s.player_id === p.id) }))
  const goalieRows = list.players.filter((p) => p.kind === 'goalie').map((p) => ({ p, row: data?.goalies.find((g) => g.player_id === p.id) }))
  const skaterTotals = skaterRows.map((r) => r.row).filter(Boolean)
  const goalieTotals = goalieRows.map((r) => r.row).filter(Boolean)

  return (
    <main>
      <header>
        <h1>Your fantasy team</h1>
        <p>Track your fantasy players under your league's scoring. {user ? <>Synced to your account ({user.email}).</> : <>The roster is saved in this browser only. <Link to="/account">Log in</Link> to sync it across devices.</>}</p>
      </header>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={kind === 'skater'} className={kind === 'skater' ? 'on' : ''} onClick={() => setKind('skater')}>Skaters</button>
        <button role="tab" aria-selected={kind === 'goalie'} className={kind === 'goalie' ? 'on' : ''} onClick={() => setKind('goalie')}>Goalies</button>
      </div>
      <div className="picker">
        <div className="search-box">
          <input
            type="search"
            placeholder={`Add a ${kind}…`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {matches.length > 0 && (
            <ul className="results">
              {matches.map((m) => (
                <li key={m.player_id}>
                  <button onClick={() => add(m)}>
                    {m.name} <span>{m.team} · {kind === 'goalie' ? 'G' : m.position}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {sync === 'conflict' && <p className="notice">Your account has a different roster than this browser. <Link to="/account">Choose which to keep →</Link></p>}

      <RosterTools only="banner" shared={params.get('roster')} onLoad={loadRoster} />

      <PageTabs
        tabs={[
          {
            id: 'roster',
            label: `Roster${list.players.length ? ` (${list.players.length})` : ''}`,
            content: (
              <>
              {list.players.length === 0 && (
                <p className="status">No players yet. Search above, or press Add to team on a <Link to="/skaters">player</Link> or <Link to="/goalies">goalie</Link> page.</p>
              )}
              {list.players.length > 0 && !data && <p className="status">Loading…</p>}

              {data && skaterRows.length > 0 && (
                <>
                  <h2>Skaters</h2>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr><th className="left">Player</th><th className="left" title={describe('Team')}>Team</th><th title={describe('GP')}>GP</th><th title={describe('G')}>G</th><th title={describe('A')}>A</th><th title={describe('P')}>P</th>{isCats ? <th title="Value over the rest of the season in your categories (z-scores above replacement)">Value</th> : <><th title={describe('Fantasy pts')}>Fantasy pts</th><th title={describe('Per GP')}>Per GP</th></>}<th title={describe('Pace')}>Pace</th><th title={describe('L10 P')}>L10 P</th><th title={describe('L10 pace')}>L10 pace</th><th /></tr>
                      </thead>
                      <tbody>
                        {skaterRows.map(({ p, row }) => (
                          <tr key={p.id}>
                            <td className="left">
                              <Link to={`/player/${p.id}`}>{p.name}</Link>
                              {row?.traded && <span className="badge">↔ traded</span>}
                              {row?.games_out >= 2 && <span className="badge warn" title="Not in the team's last games">out {row.games_out}</span>}
                              <RoleBadge row={roles?.[p.id]} />
                              <LuckBadge row={luck?.skaters?.[p.id]} />
                            </td>
                            {row ? (
                              <>
                                <td className="left">{row.team}</td><td>{row.games_played}</td><td>{row.goals}</td><td>{row.assists}</td>
                                <td>{row.points}</td>
                                {isCats ? <td className="accent">{valueText(p.id)}</td> : (
                                  <>
                                    <td className="accent">{fp(fantasyPoints(row, SKATER_CATS, scoring))}</td>
                                    <td>{row.games_played ? (fantasyPoints(row, SKATER_CATS, scoring) / row.games_played).toFixed(2) : '–'}</td>
                                  </>
                                )}
                                <td>{fmt1(row.point_pace)}</td>
                                <td>{row.recent_points ?? '–'}</td><td>{fmt1(row.recent_pace)}</td>
                              </>
                            ) : (
                              <td className="left" colSpan={isCats ? 9 : 10}><span className="muted">No games this season</span></td>
                            )}
                            <td><button className="link-button" onClick={() => togglePlayer(p)}>Remove</button></td>
                          </tr>
                        ))}
                      </tbody>
                      {skaterTotals.length > 1 && (
                        <tfoot>
                          <tr>
                            <td className="left">Team total</td><td />
                            <td /><td>{sum(skaterTotals, 'goals')}</td><td>{sum(skaterTotals, 'assists')}</td>
                            <td>{sum(skaterTotals, 'points')}</td>
                            {isCats
                              ? <td className="accent">{skaterTotals.reduce((t, r) => t + (values?.get(r.player_id)?.value ?? 0), 0).toFixed(1)}</td>
                              : <><td className="accent">{fp(skaterTotals.reduce((t, r) => t + fantasyPoints(r, SKATER_CATS, scoring), 0))}</td><td /></>}
                            <td>{fmt1(sum(skaterTotals, 'point_pace'))}</td>
                            <td>{sum(skaterTotals, 'recent_points')}</td><td>{fmt1(sum(skaterTotals, 'recent_pace'))}</td><td />
                          </tr>
                        </tfoot>
                      )}
                    </table>
                  </div>
                </>
              )}

              {data && goalieRows.length > 0 && (
                <>
                  <h2>Goalies</h2>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr><th className="left">Goalie</th><th className="left" title={describe('Team')}>Team</th><th title={describe('GP')}>GP</th><th title={describe('W')}>W</th><th title={describe('L')}>L</th>{isCats ? <th title="Value over the rest of the season in your categories (z-scores above replacement)">Value</th> : <><th title={describe('Fantasy pts')}>Fantasy pts</th><th title={describe('Per GP')}>Per GP</th></>}<th title={describe('SV%')}>SV%</th><th title={describe('GAA')}>GAA</th><th title={describe('GSAA')}>GSAA</th><th title={describe('Recent SV%')}>Recent SV%</th><th /></tr>
                      </thead>
                      <tbody>
                        {goalieRows.map(({ p, row }) => (
                          <tr key={p.id}>
                            <td className="left">
                              <Link to={`/goalie/${p.id}`}>{p.name}</Link>
                              <LuckBadge row={luck?.goalies?.[p.id]} goalie />
                            </td>
                            {row ? (
                              <>
                                <td className="left">{row.team}</td><td>{row.games_played}</td><td>{row.wins}</td><td>{row.losses}</td>
                                {isCats ? <td className="accent">{valueText(p.id)}</td> : (
                                  <>
                                    <td className="accent">{fp(fantasyPoints(row, GOALIE_CATS, scoring))}</td>
                                    <td>{row.games_played ? (fantasyPoints(row, GOALIE_CATS, scoring) / row.games_played).toFixed(2) : '–'}</td>
                                  </>
                                )}
                                <td>{sv(row.save_pct)}</td><td>{row.gaa?.toFixed(2)}</td><td>{signed(row.gsaa)}</td><td>{sv(row.recent_save_pct)}</td>
                              </>
                            ) : (
                              <td className="left" colSpan={isCats ? 9 : 10}><span className="muted">No games this season</span></td>
                            )}
                            <td><button className="link-button" onClick={() => togglePlayer(p)}>Remove</button></td>
                          </tr>
                        ))}
                      </tbody>
                      {goalieTotals.length > 1 && (
                        <tfoot>
                          <tr>
                            <td className="left">Team total</td><td /><td>{sum(goalieTotals, 'games_played')}</td>
                            <td>{sum(goalieTotals, 'wins')}</td><td>{sum(goalieTotals, 'losses')}</td>
                            {isCats
                              ? <><td className="accent">{goalieTotals.reduce((t, r) => t + (values?.get(r.player_id)?.value ?? 0), 0).toFixed(1)}</td><td /><td /><td /><td /><td /></>
                              : <><td className="accent">{fp(goalieTotals.reduce((t, r) => t + fantasyPoints(r, GOALIE_CATS, scoring), 0))}</td><td /><td /><td /><td /><td /><td /></>}
                          </tr>
                        </tfoot>
                      )}
                    </table>
                  </div>
                </>
              )}
              {list.players.length > 1 && (
                <p><Link to={`/compare?ids=${list.players.filter((p) => p.kind === (skaterRows.length ? 'skater' : 'goalie')).slice(0, 3).map((p) => p.id).join(',')}`}>Compare your players →</Link></p>
              )}
              </>
            ),
          },
          {
            id: 'week',
            label: 'This week',
            content: list.players.length > 0 ? <><GoalieStarts players={list.players} /><FantasyWeek players={list.players} /></> : <p className="status">Add players to see their games this week.</p>,
          },
          {
            id: 'pickups',
            label: 'Pickup ideas',
            content: data ? (
              <>
                <div className="tabs" role="tablist">
                  <button role="tab" aria-selected={kind === 'skater'} className={kind === 'skater' ? 'on' : ''} onClick={() => setKind('skater')}>Skaters</button>
                  <button role="tab" aria-selected={kind === 'goalie'} className={kind === 'goalie' ? 'on' : ''} onClick={() => setKind('goalie')}>Goalies</button>
                </div>
                <Pickups data={data} kind={kind} rosterIds={taken} scoring={scoring} values={isCats ? values : null} onAdd={add} />
              </>
            ) : <p className="status">Loading…</p>,
          },
          {
            id: 'stream',
            label: 'Streaming goalies',
            content: <StreamingGoalies scoring={scoring} categories={isCats ? leagueCfg.categories : null} rosterIds={taken} onAdd={addValued} />,
          },
          {
            id: 'values',
            label: 'Player values',
            content: values ? <PlayerValues data={data} values={values} rosterIds={taken} onAdd={addValued} categories={isCats ? leagueCfg.categories : null} /> : <p className="status">Loading…</p>,
          },
          {
            id: 'ideas',
            label: 'Trade ideas',
            content: values ? <TradeIdeas data={data} values={values} roster={list.players} /> : <p className="status">Loading…</p>,
          },
          {
            id: 'trade',
            label: 'Trade analyzer',
            content: values ? <TradeAnalyzer data={data} values={values} roster={list.players} categories={isCats ? leagueCfg.categories : null} /> : <p className="status">Loading…</p>,
          },
          {
            id: 'settings',
            label: 'Scoring & backup',
            content: (
              <>
                {isCats ? <p className="notice">Your league counts categories, so points-per-stat scoring doesn't apply. Switch to a points league below to use it.</p> : <ScoringSettings scoring={scoring} setScoring={setScoring} />}
                <LeagueSettings league={league} setLeague={setLeague} />
                <RosterTools only="buttons" players={list.players} scoring={scoring} onLoad={loadRoster} />
              </>
            ),
          },
        ]}
      />
    </main>
  )
}
