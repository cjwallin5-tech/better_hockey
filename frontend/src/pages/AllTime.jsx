import Avatar from '../components/Avatar.jsx'
import { useEffect, useState } from 'react'
import HhofMark from '../components/HhofMark.jsx'
import { Link } from 'react-router-dom'
import { seasonLabel } from '../career.js'
import { downloadText, toCsv } from '../csv.js'
import { useUrlSync } from '../urlState.js'
import SavedViews from '../components/SavedViews.jsx'
import { describe } from '../glossary.js'
import SeasonSwitch from '../components/SeasonSwitch.jsx'
import RankBadge from '../components/RankBadge.jsx'
import RankBy from '../components/RankBy.jsx'
import GameRecords from '../components/GameRecords.jsx'
import ViewMenu from '../components/ViewMenu.jsx'
import FilterPanel from '../components/FilterPanel.jsx'

const PAGE_SIZE = 50

const int = (v) => (v == null ? '–' : v.toLocaleString())
const round = (v) => (v == null ? '–' : Math.round(v).toLocaleString())
const dec = (v, d = 2) => (v == null ? '–' : v.toFixed(d))
const pct = (v) => (v == null || v === 0 ? '–' : (v * 100).toFixed(1))
const sv = (v) => (v == null ? '–' : v.toFixed(3).replace(/^0/, ''))

const COLUMNS = {
  skater: [
    { key: 'season_id', label: 'Season', fmt: seasonLabel, asc: true }, // best single seasons only
    { key: 'team', label: 'Team', text: true },
    { key: 'first_season', label: 'Debut', fmt: seasonLabel, asc: true },
    { key: 'games_played', label: 'GP', fmt: int },
    { key: 'goals', label: 'G', fmt: int },
    { key: 'assists', label: 'A', fmt: int },
    { key: 'points', label: 'P', fmt: int, accent: true },
    { key: 'goals_per_game', label: 'G/GP', fmt: dec, rate: true },
    { key: 'assists_per_game', label: 'A/GP', fmt: dec, rate: true },
    { key: 'points_per_game', label: 'P/GP', fmt: dec, rate: true },
    { key: 'plus_minus', label: '+/-', fmt: int },
    { key: 'pim', label: 'PIM', fmt: int },
    { key: 'pp_goals', label: 'PPG', fmt: int },
    { key: 'pp_points', label: 'PPP', fmt: int },
    { key: 'sh_goals', label: 'SHG', fmt: int },
    { key: 'game_winning_goals', label: 'GWG', fmt: int },
    { key: 'ot_goals', label: 'OTG', fmt: int },
    { key: 'shots', label: 'Shots', fmt: int },
    { key: 'shooting_pct', label: 'S%', fmt: pct, rate: true },
    { key: 'fo_win_pct', label: 'FO%', fmt: pct, rate: true },
    { key: 'hits', label: 'Hits', fmt: int, tracked: true },
    { key: 'blocked_shots', label: 'Blocks', fmt: int, tracked: true },
    { key: 'takeaways', label: 'Takeaways', fmt: int, tracked: true },
    { key: 'giveaways', label: 'Giveaways', fmt: int, tracked: true },
    { key: 'missed_shots', label: 'Missed shots', fmt: int, tracked: true },
    { key: 'shot_attempts', label: 'Shot attempts', fmt: int, tracked: true },
    { key: 'empty_net_goals', label: 'ENG', fmt: int },
    { key: 'first_goals', label: 'First goals', fmt: int },
    { key: 'adj_goals', label: 'Adj G', fmt: round },
    { key: 'adj_assists', label: 'Adj A', fmt: round },
    { key: 'adj_points', label: 'Adj P', fmt: round, accent: true },
    { key: 'adj_points_per_game', label: 'Adj P/GP', fmt: dec, rate: true },
    { key: 'hat_tricks', label: 'Hat tricks', fmt: int, accent: true },
    { key: 'four_goal_games', label: '4-goal games', fmt: int },
    { key: 'five_goal_games', label: '5-goal games', fmt: int },
    { key: 'three_assist_games', label: '3-assist games', fmt: int },
    { key: 'four_point_games', label: '4-point games', fmt: int },
    { key: 'five_point_games', label: '5-point games', fmt: int },
    { key: 'seasons_played', label: 'Seasons', fmt: int },
    { key: 'seasons_100p', label: '100-pt seasons', fmt: int, accent: true },
    { key: 'seasons_90p', label: '90-pt', fmt: int },
    { key: 'seasons_80p', label: '80-pt', fmt: int },
    { key: 'seasons_60p', label: '60-pt', fmt: int },
    { key: 'seasons_60a', label: '60-assist', fmt: int },
    { key: 'seasons_50a', label: '50-assist', fmt: int },
    { key: 'seasons_40a', label: '40-assist', fmt: int },
    { key: 'seasons_50g', label: '50-goal seasons', fmt: int, accent: true },
    { key: 'seasons_40g', label: '40-goal', fmt: int },
    { key: 'seasons_30g', label: '30-goal', fmt: int },
    { key: 'seasons_20g', label: '20-goal', fmt: int },
    { key: 'best_points', label: 'Best season P', fmt: int },
    { key: 'best_goals', label: 'Best season G', fmt: int },
    { key: 'best_assists', label: 'Best season A', fmt: int },
    { key: 'rookie_season', label: 'Rookie season', fmt: seasonLabel, asc: true },
    { key: 'rookie_gp', label: 'Rookie GP', fmt: int },
    { key: 'rookie_goals', label: 'Rookie G', fmt: int },
    { key: 'rookie_assists', label: 'Rookie A', fmt: int },
    { key: 'rookie_points', label: 'Rookie P', fmt: int, accent: true },
    { key: 'rookie_points_per_game', label: 'Rookie P/GP', fmt: dec },
  ],
  goalie: [
    { key: 'season_id', label: 'Season', fmt: seasonLabel, asc: true },
    { key: 'team', label: 'Team', text: true },
    { key: 'first_season', label: 'Debut', fmt: seasonLabel, asc: true },
    { key: 'games_played', label: 'GP', fmt: int },
    { key: 'games_started', label: 'GS', fmt: int },
    { key: 'wins', label: 'W', fmt: int, accent: true },
    { key: 'losses', label: 'L', fmt: int },
    { key: 'ties', label: 'T', fmt: int },
    { key: 'ot_losses', label: 'OTL', fmt: int },
    { key: 'save_pct', label: 'SV%', fmt: sv, rate: true, accent: true },
    { key: 'gaa', label: 'GAA', fmt: dec, rate: true, asc: true },
    { key: 'shutouts', label: 'SO', fmt: int },
    { key: 'saves', label: 'Saves', fmt: int },
    { key: 'shots_against', label: 'SA', fmt: int },
    { key: 'goals_against', label: 'GA', fmt: int },
    { key: 'toi_sec', label: 'Minutes', fmt: (v) => (v == null ? '–' : Math.round(v / 60).toLocaleString()) },
  ],
}
// Every view of the page, grouped in the dropdown: each lists its columns and the stat it sorts by when picked.
// `season: true` views are the best single seasons (one row per player per season, from /api/best-seasons); the rest are careers.
const CAREER = 'Career totals', RECORDS = 'Career records', BEST = 'Best single seasons'
const VIEWS = {
  skater: [
    { id: 'scoring', group: CAREER, label: 'Scoring', sort: 'points',
      keys: ['first_season', 'games_played', 'goals', 'assists', 'points', 'goals_per_game', 'assists_per_game', 'points_per_game', 'plus_minus', 'pim'] },
    { id: 'special', group: CAREER, label: 'Special teams & goals', sort: 'pp_points', keys: ['games_played', 'pp_goals', 'pp_points', 'sh_goals', 'game_winning_goals', 'ot_goals', 'empty_net_goals', 'first_goals'] },
    { id: 'shooting', group: CAREER, label: 'Shooting', sort: 'shots', keys: ['games_played', 'shots', 'shooting_pct', 'shot_attempts', 'missed_shots', 'fo_win_pct'] },
    { id: 'defense', group: CAREER, label: 'Hits & giveaways', sort: 'hits', keys: ['games_played', 'hits', 'blocked_shots', 'takeaways', 'giveaways'] },
    { id: 'adjusted', group: CAREER, label: 'Era-adjusted', sort: 'adj_points', regularOnly: true,
      keys: ['first_season', 'games_played', 'goals', 'points', 'adj_goals', 'adj_assists', 'adj_points', 'adj_points_per_game'] },
    { id: 'bigGames', group: RECORDS, label: 'Hat tricks & big games', sort: 'hat_tricks', has: 'sort',
      keys: ['first_season', 'games_played', 'hat_tricks', 'four_goal_games', 'five_goal_games', 'three_assist_games', 'four_point_games', 'five_point_games'] },
    { id: 'pointSeasons', group: RECORDS, label: 'Point & assist seasons', sort: 'seasons_100p', has: 'sort', regularOnly: true,
      keys: ['first_season', 'seasons_played', 'seasons_100p', 'seasons_90p', 'seasons_80p', 'seasons_60p', 'seasons_60a', 'seasons_50a', 'seasons_40a', 'best_points', 'best_assists'] },
    { id: 'goalSeasons', group: RECORDS, label: 'Goal seasons', sort: 'seasons_50g', has: 'sort', regularOnly: true,
      keys: ['first_season', 'seasons_played', 'seasons_50g', 'seasons_40g', 'seasons_30g', 'seasons_20g', 'best_goals'] },
    { id: 'rookies', group: RECORDS, label: 'Rookies', sort: 'rookie_points', has: 'rookie_gp', regularOnly: true,
      keys: ['rookie_season', 'rookie_gp', 'rookie_goals', 'rookie_assists', 'rookie_points', 'rookie_points_per_game'] },
    { id: 'singleGame', group: RECORDS, label: 'Single game', sort: 'goals', games: true, keys: [] },
    { id: 'bestScoring', group: BEST, label: 'Best seasons: Scoring', sort: 'points', season: true, regularOnly: true,
      keys: ['season_id', 'team', 'games_played', 'goals', 'assists', 'points', 'points_per_game'] },
    { id: 'bestAdjusted', group: BEST, label: 'Best seasons: Era-adjusted', sort: 'adj_points', season: true, regularOnly: true,
      keys: ['season_id', 'games_played', 'points', 'adj_goals', 'adj_assists', 'adj_points', 'adj_points_per_game'] },
    { id: 'bestDefense', group: BEST, label: 'Best seasons: Hits & giveaways', sort: 'hits', season: true, regularOnly: true,
      keys: ['season_id', 'team', 'games_played', 'hits', 'blocked_shots', 'takeaways', 'giveaways'] },
  ],
  goalie: [
    { id: 'record', group: CAREER, label: 'Record', sort: 'wins', keys: ['first_season', 'games_played', 'games_started', 'wins', 'losses', 'ties', 'ot_losses', 'shutouts'] },
    { id: 'saves', group: CAREER, label: 'Saves', sort: 'save_pct', keys: ['games_played', 'save_pct', 'gaa', 'saves', 'shots_against', 'goals_against', 'toi_sec'] },
    { id: 'bestRecord', group: BEST, label: 'Best seasons: Record', sort: 'wins', season: true, regularOnly: true,
      keys: ['season_id', 'team', 'games_played', 'games_started', 'wins', 'losses', 'ot_losses', 'shutouts'] },
    { id: 'bestSaves', group: BEST, label: 'Best seasons: Saves', sort: 'save_pct', season: true, regularOnly: true,
      keys: ['season_id', 'team', 'games_played', 'save_pct', 'gaa', 'saves', 'shots_against', 'goals_against'] },
  ],
}
// "Rank by" quick picks for each view, like the season leaderboard's (only the ones whose column is in the view are shown).
const QUICK_RANK = {
  scoring: [['points', 'Points'], ['goals', 'Goals'], ['assists', 'Assists'], ['points_per_game', 'P/GP'], ['goals_per_game', 'G/GP'],
    ['assists_per_game', 'A/GP'], ['plus_minus', '+/-']],
  bigGames: [['hat_tricks', 'Hat tricks'], ['four_goal_games', '4-goal games'], ['five_goal_games', '5-goal games'],
    ['three_assist_games', '3-assist games'], ['four_point_games', '4-point games'], ['five_point_games', '5-point games']],
  pointSeasons: [['seasons_100p', '100-point seasons'], ['seasons_90p', '90-point'], ['seasons_80p', '80-point'], ['seasons_60p', '60-point'],
    ['seasons_60a', '60-assist'], ['seasons_50a', '50-assist'], ['seasons_40a', '40-assist'], ['best_points', 'Best season'], ['seasons_played', 'Seasons']],
  goalSeasons: [['seasons_50g', '50-goal seasons'], ['seasons_40g', '40-goal'], ['seasons_30g', '30-goal'], ['seasons_20g', '20-goal'],
    ['best_goals', 'Best season'], ['seasons_played', 'Seasons']],
  rookies: [['rookie_points', 'Points'], ['rookie_goals', 'Goals'], ['rookie_assists', 'Assists'], ['rookie_points_per_game', 'P/GP']],
  singleGame: [['goals', 'Goals'], ['assists', 'Assists'], ['points', 'Points']],
  special: [['pp_points', 'PP points'], ['pp_goals', 'PP goals'], ['game_winning_goals', 'GWG'], ['sh_goals', 'SH goals']],
  shooting: [['shots', 'Shots'], ['shooting_pct', 'S%'], ['shot_attempts', 'Shot attempts']],
  defense: [['hits', 'Hits'], ['blocked_shots', 'Blocks'], ['takeaways', 'Takeaways'], ['giveaways', 'Giveaways']],
  adjusted: [['adj_points', 'Adj points'], ['adj_goals', 'Adj goals'], ['adj_points_per_game', 'Adj P/GP']],
  bestScoring: [['points', 'Points'], ['goals', 'Goals'], ['assists', 'Assists'], ['points_per_game', 'P/GP']],
  bestAdjusted: [['adj_points', 'Adj points'], ['adj_goals', 'Adj goals'], ['adj_assists', 'Adj assists'], ['adj_points_per_game', 'Adj P/GP']],
  bestDefense: [['hits', 'Hits'], ['blocked_shots', 'Blocks'], ['takeaways', 'Takeaways'], ['giveaways', 'Giveaways']],
  bestRecord: [['wins', 'Wins'], ['shutouts', 'Shutouts'], ['games_started', 'Starts']],
  bestSaves: [['save_pct', 'SV%'], ['gaa', 'GAA'], ['saves', 'Saves']],
  record: [['wins', 'Wins'], ['shutouts', 'Shutouts'], ['games_played', 'Games']],
  saves: [['save_pct', 'SV%'], ['gaa', 'GAA'], ['saves', 'Saves']],
}
// Rate stats are meaningless over a handful of games, so sorting by them applies a minimum.
const AUTO_MIN_GP = { skater: 300, goalie: 150 }

/** All-time leaders for one kind of player ('skater' or 'goalie'), each on its own page. */
export default function AllTime({ kind }) {
  const initial = new URLSearchParams(window.location.search)
  const [gameType, setGameType] = useState(initial.get('gt') === '3' ? 3 : 2)
  const [search, setSearch] = useState(() => initial.get('q') ?? '')
  const [debouncedSearch, setDebouncedSearch] = useState(() => initial.get('q') ?? '')
  const [position, setPosition] = useState(() => initial.get('pos') ?? '')
  const [country, setCountry] = useState(() => initial.get('country') ?? '')
  const [activeOnly, setActiveOnly] = useState(() => initial.get('active') === '1')
  const [hofOnly, setHofOnly] = useState(() => initial.get('hof') === '1')
  const [debutFrom, setDebutFrom] = useState(() => initial.get('from') ?? '')
  const [debutTo, setDebutTo] = useState(() => initial.get('to') ?? '')
  const [minGpInput, setMinGpInput] = useState(() => initial.get('min_gp') ?? '')
  // The tab a link opens on: the one named by v, else the first that has the sorted column, else the first.
  const initialView = VIEWS[kind].find((v) => v.id === initial.get('v')) ?? VIEWS[kind].find((v) => v.keys.includes(initial.get('sort'))) ?? VIEWS[kind][0]
  const [sort, setSort] = useState(() => ({
    key: initial.get('sort') ?? initialView.sort, // a link to a tab without a sort ranks by that tab's main stat
    dir: initial.get('dir') ?? 'desc',
  }))
  const [viewId, setViewId] = useState(initialView.id)
  const [page, setPage] = useState(() => Math.max(0, Number(initial.get('page') ?? 1) - 1))
  const [countries, setCountries] = useState([])
  const [result, setResult] = useState({ key: '', data: null, error: null })

  useUrlSync([
    ['gt', gameType, 2], ['sort', sort.key, kind === 'skater' ? 'points' : 'wins'], ['dir', sort.dir, 'desc'],
    ['q', search, ''], ['pos', position, ''], ['country', country, ''], ['active', activeOnly, false], ['hof', hofOnly, false],
    ['from', debutFrom, ''], ['to', debutTo, ''], ['min_gp', minGpInput, ''], ['page', page + 1, 1], ['v', viewId, VIEWS[kind][0].id],
  ])

  useEffect(() => {
    fetch(`/api/alltime/${kind}/countries`).then((r) => r.json()).then(setCountries).catch(() => setCountries([]))
  }, [kind])
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  const allColumns = COLUMNS[kind]
  const visibleViews = VIEWS[kind].filter((v) => !(v.regularOnly && gameType === 3)) // adjusted totals are regular season only
  const view = visibleViews.find((v) => v.id === viewId) ?? visibleViews[0]
  const columns = view.keys.map((k) => allColumns.find((c) => c.key === k))
  const sortCol = allColumns.find((c) => c.key === sort.key)
  const autoMin = sortCol?.rate && !view.season ? AUTO_MIN_GP[kind] : 0 // best seasons apply their own cutoff on the server
  const minGp = minGpInput === '' ? autoMin : Number(minGpInput)
  const hasParam = view.has === 'sort' ? sort.key : (view.has ?? '') // a stat that must be above zero: counts and rookie lines leave out players with none

  // Best single seasons come from their own endpoint (one row per player per season) and take season filters instead of debut ones.
  const seasonBoard = !!view.season
  const api = seasonBoard ? `/api/best-seasons/${kind}` : `/api/alltime/${kind}`
  const p = new URLSearchParams({ sort: sort.key, dir: sort.dir, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
  if (!seasonBoard) p.set('game_type', gameType)
  if (debouncedSearch.trim()) p.set('q', debouncedSearch.trim())
  if (kind === 'skater' && position) p.set('position', position)
  if (country && !seasonBoard) p.set('country', country)
  if (activeOnly) p.set('active', 'true')
  if (hofOnly) p.set('hof', 'true')
  if (minGp > 0) p.set('min_gp', minGp)
  if (debutFrom) p.set(seasonBoard ? 'season_from' : 'debut_from', debutFrom)
  if (debutTo) p.set(seasonBoard ? 'season_to' : 'debut_to', debutTo)
  if (hasParam) p.set('has', hasParam)
  const query = p.toString()

  const exportAll = async () => {
    const p = new URLSearchParams(query)
    p.set('export', 'true'); p.set('limit', '10000'); p.set('offset', '0')
    const r = await fetch(`${api}?${p}`)
    if (!r.ok) return
    const { rows } = await r.json()
    const cols = seasonBoard
      ? [{ key: 'name', label: 'Player' }, ...(kind === 'skater' ? [{ key: 'position', label: 'Pos' }] : []), ...allColumns.filter((c) => c.key !== 'first_season')]
      : [
        { key: 'name', label: 'Player' }, ...(kind === 'skater' ? [{ key: 'position', label: 'Pos' }] : []),
        { key: 'birth_country', label: 'Country' }, { key: 'first_season', label: 'Debut season' },
        ...allColumns.filter((c) => c.key !== 'first_season' && c.key !== 'season_id' && !c.text),
      ]
    downloadText(seasonBoard ? `best-${kind}-seasons.csv` : `all-time-${kind}s-${gameType === 3 ? 'playoffs' : 'regular-season'}.csv`, toCsv(cols, rows))
  }


  useEffect(() => {
    if (view.games) return undefined // the single-game list loads itself (GameRecords)
    let ignore = false // a newer query supersedes this one
    fetch(`${api}?${query}`)
      .then((r) => {
        if (!r.ok) throw new Error(`API returned ${r.status}`)
        return r.json()
      })
      .then((data) => !ignore && setResult({ key: `${api}?${query}`, data, error: null }))
      .catch((error) => !ignore && setResult({ key: `${api}?${query}`, data: null, error: error.message }))
    return () => { ignore = true }
  }, [api, kind, query, view.games])

  // Changing any filter returns to the first page.
  const reset = (setter) => (value) => { setter(value); setPage(0) }

  const switchView = (v) => {
    setViewId(v.id)
    setSort({ key: v.sort, dir: 'desc' })
    setPage(0)
  }

  const onSort = (col) => {
    setSort((s) => (s.key === col.key ? { key: col.key, dir: s.dir === 'desc' ? 'asc' : 'desc' } : { key: col.key, dir: col.asc ? 'asc' : 'desc' }))
    setPage(0)
  }

  const { data, error } = result
  const loading = !view.games && result.key !== `${api}?${query}`
  const total = data?.total ?? 0
  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1)
  const from = total ? page * PAGE_SIZE + 1 : 0
  const to = Math.min(total, (page + 1) * PAGE_SIZE)

  const positionSelect = (
    <select value={position} onChange={(e) => reset(setPosition)(e.target.value)} aria-label="Position">
      <option value="">All positions</option>
      <option value="F">Forwards</option>
      <option value="C">Centers</option>
      <option value="L">Left wings</option>
      <option value="R">Right wings</option>
      <option value="D">Defense</option>
    </select>
  )

  const route = kind === 'goalie' ? 'goalie' : 'player'

  return (
    <main>
      <SeasonSwitch kind={kind} active="alltime" />
      <header>
        <h1>{kind === 'skater' ? 'Skater' : 'Goalie'} Stats <span>All-time</span></h1>
        <p>
          {kind === 'skater'
            ? 'Career totals and records for every skater in NHL history: use the menu for hat tricks, milestone seasons, rookies, single games and the best single seasons ever. Early eras have blank stats.'
            : 'Career totals and the best single seasons for every goalie in NHL history. Early eras have blank stats.'}
        </p>
      </header>
      <SavedViews path={`/alltime/${kind}s`} />

      <ViewMenu
        groups={[...new Set(visibleViews.map((v) => v.group))].map((g) => ({ label: g, views: visibleViews.filter((v) => v.group === g) }))}
        activeId={view.id}
        onSelect={(id) => switchView(visibleViews.find((v) => v.id === id))}
      />

      <RankBy
        options={(QUICK_RANK[view.id] ?? []).filter(([key]) => view.games || columns.some((c) => c.key === key)).map(([key, label]) => ({ key, label }))}
        sort={sort}
        onPick={(key) => (view.games ? (setSort({ key, dir: 'desc' }), setPage(0)) : onSort(columns.find((c) => c.key === key)))}
      />

      <FilterPanel
        count={(position && kind === 'skater' ? 1 : 0) + (country && !seasonBoard ? 1 : 0) + (activeOnly ? 1 : 0) + (hofOnly ? 1 : 0) + (debutFrom || debutTo ? 1 : 0) + (minGpInput !== '' ? 1 : 0)}
        onClear={() => { setPosition(''); setCountry(''); setActiveOnly(false); setHofOnly(false); setDebutFrom(''); setDebutTo(''); setMinGpInput(''); setPage(0) }}
        main={<>
          <input type="search" placeholder="Search by name" value={search} onChange={(e) => reset(setSearch)(e.target.value)} />
          {kind === 'skater' && view.games && positionSelect}
          {!seasonBoard && <select
            value={gameType}
            onChange={(e) => { const t = Number(e.target.value); reset(setGameType)(t); if (t === 3 && view.regularOnly) switchView(VIEWS[kind][0]) }}
            aria-label="Regular season or playoffs"
          >
            <option value={2}>Regular season</option>
            <option value={3}>Playoffs</option>
          </select>}
        </>}
        extra={view.games ? null : <>
          {kind === 'skater' && positionSelect}
          {!seasonBoard && (
            <select value={country} onChange={(e) => reset(setCountry)(e.target.value)} aria-label="Country">
              <option value="">All countries</option>
              {countries.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          )}
          <label>
            {seasonBoard ? 'Seasons' : 'Debuted'}
            <input type="number" placeholder="from" min="1917" value={debutFrom} onChange={(e) => reset(setDebutFrom)(e.target.value)} />
            –
            <input type="number" placeholder="to" min="1917" value={debutTo} onChange={(e) => reset(setDebutTo)(e.target.value)} />
          </label>
          <label className="inline-check">
            <input type="checkbox" checked={activeOnly} onChange={(e) => reset(setActiveOnly)(e.target.checked)} /> Active
          </label>
          <label className="inline-check">
            <input type="checkbox" checked={hofOnly} onChange={(e) => reset(setHofOnly)(e.target.checked)} /> Hall of Famers
          </label>
          <label>
            Min GP
            <input type="number" min="0" placeholder={seasonBoard ? 'auto' : String(autoMin)} value={minGpInput} onChange={(e) => reset(setMinGpInput)(e.target.value)} />
          </label>
        </>}
        tail={!view.games && <>
          <button className="link-button" onClick={exportAll} title="Download every player matching the filters (up to 10,000)">Download CSV</button>
          <span className="count">{loading ? 'Loading…' : `${from.toLocaleString()}–${to.toLocaleString()} of ${total.toLocaleString()}`}</span>
        </>}
      />
      {!view.games && autoMin > 0 && minGpInput === '' && (
        <p className="view-note">Sorting by a rate stat: showing players with at least {autoMin} games. Change Min GP to adjust.</p>
      )}

      {view.games ? (
        <GameRecords stat={sort.key} gameType={gameType} q={debouncedSearch} position={position} page={page} setPage={setPage} />
      ) : error ? (
        <p className="status">Couldn't load the board: {error}</p>
      ) : (
        <div className="table-wrap" style={loading ? { opacity: 0.6 } : undefined}>
          <table>
            <thead>
              <tr>
                <th className="left" title="Sort by name" onClick={() => onSort({ key: 'name', asc: true })} aria-sort={sort.key === 'name' ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                  Player{sort.key === 'name' && <i>{sort.dir === 'asc' ? ' ▲' : ' ▼'}</i>}
                </th>
                {kind === 'skater' && <th title={describe('Pos')}>Pos</th>}
                {columns.map((c) => (
                  <th key={c.key} className={c.text ? 'left' : ''} title={describe(c.label)} onClick={c.text ? undefined : () => onSort(c)} aria-sort={c.text ? undefined : sort.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    {c.label}{sort.key === c.key && <i>{sort.dir === 'asc' ? ' ▲' : ' ▼'}</i>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data?.rows ?? []).map((r) => (
                <tr key={seasonBoard ? `${r.player_id}-${r.season_id}` : r.player_id}>
                  <td className={'left ' + (sort.key === 'name' ? 'sorted' : '')}>
                    <span className="player-cell">
                      <RankBadge n={r.place} tied={r.tied} />
                      <Avatar playerId={r.player_id} team={seasonBoard ? r.team : r.last_team} season={seasonBoard ? r.season_id : r.last_season} name={r.name} retired={!(seasonBoard ? r.active : r.active_season)} />
                      <Link to={`/${route}/${r.player_id}`}>{r.name}</Link>
                      {r.hall_of_fame === 'Y' && <HhofMark size={18} />}
                      {(seasonBoard ? r.active : r.active_season) && <span className="badge">active</span>}
                    </span>
                  </td>
                  {kind === 'skater' && <td>{r.position}</td>}
                  {columns.map((c) => (
                    <td key={c.key} className={(c.text ? 'left ' : '') + (c.accent ? 'accent ' : '') + (sort.key === c.key ? 'sorted' : '')}>{c.text ? (r[c.key] ?? '–') : c.fmt(r[c.key])}</td>
                  ))}
                </tr>
              ))}
              {data && data.rows.length === 0 && (
                <tr><td className="left" colSpan={columns.length + 2}>No players match these filters.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {kind === 'skater' && (view.id === 'adjusted' || view.id === 'bestAdjusted') && (
        <p className="sub">
          Adjusted totals rescale each season's goals and assists to today's scoring level (the last five completed
          seasons), separately for forwards and defensemen, because the league averaged about 4 goals per team game in
          the early 1980s and under 3 in the mid-2000s. Games played are unchanged. It does not correct for ice time,
          power-play share, expansion or schedule length, so treat it as a fairer comparison, not a ruling.
          {view.id === 'adjusted' && ` Rate sorting (Adj P/GP) shows players with at least ${AUTO_MIN_GP.skater} games.`}
        </p>
      )}

      {kind === 'skater' && view.id === 'bestDefense' && (
        <p className="sub">Hits, blocks, takeaways and giveaways have only been recorded since 2005-06, so earlier seasons don't appear here.</p>
      )}

      {kind === 'skater' && ['defense', 'shooting'].includes(view.id) && (
        <p className="sub">
          Hits, blocks, takeaways, giveaways, missed shots and shot attempts have only been recorded since
          2005-06. Players who finished before then show – , and careers that straddle it only count the
          tracked seasons.
        </p>
      )}

      {seasonBoard && (
        <p className="sub">
          One row per player per season{kind === 'skater' ? ', back to 1917-18' : ', from 2005-06 (earlier goalie seasons aren\'t loaded)'}; the season in progress isn't
          included.{['points_per_game', 'adj_points_per_game', 'save_pct', 'gaa'].includes(sort.key) && minGpInput === '' && ' Per-game and percentage stats count only players with at least half the games of the busiest player that season; set Min GP to use your own cutoff.'}
          {kind === 'goalie' && ' Lower is better for GAA, so it sorts low to high first.'}
        </p>
      )}

      {kind === 'skater' && view.id === 'bigGames' && (
        <p className="sub">
          A hat trick is three or more goals in one game; the other columns count games with at least that many goals, assists or
          points, so every 4-goal game is also a hat trick. Game-by-game records go back to 1917-18. Switch to Playoffs to count
          postseason games instead.
        </p>
      )}
      {kind === 'skater' && ['pointSeasons', 'goalSeasons'].includes(view.id) && (
        <p className="sub">
          Counts the regular seasons in which a player reached the mark (a 100-point season is 100 or more points, whatever the
          schedule length of the time). Best season is the most in any one regular season. Playoff totals don't have seasons to count.
        </p>
      )}
      {kind === 'skater' && view.id === 'rookies' && (
        <p className="sub">
          A player's rookie season is his first season with more than 25 NHL games, provided he was under 26 when it started
          (the Calder Trophy's rules). The NHL's second test, fewer than six games in each of two earlier seasons, isn't applied,
          so a few players can differ from the official list. Sort by P/GP to rank rookies by pace instead of total.
        </p>
      )}

      {!view.games && <div className="pager">
        <button disabled={page === 0 || loading} onClick={() => setPage(0)}>« First</button>
        <button disabled={page === 0 || loading} onClick={() => setPage((p) => p - 1)}>‹ Prev</button>
        <span>Page {(page + 1).toLocaleString()} of {(lastPage + 1).toLocaleString()}</span>
        <button disabled={page >= lastPage || loading} onClick={() => setPage((p) => p + 1)}>Next ›</button>
        <button disabled={page >= lastPage || loading} onClick={() => setPage(lastPage)}>Last »</button>
      </div>}
    </main>
  )
}
