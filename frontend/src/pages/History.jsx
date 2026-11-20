import { Link, useSearchParams } from 'react-router-dom'
import PageIntro from '../components/PageIntro.jsx'
import PageTabs from '../components/PageTabs.jsx'
import PageSkeleton from '../components/Skeleton.jsx'
import Info from '../components/Info.jsx'
import { seasonLabel } from '../career.js'
import { useJson } from '../lists.js'

const FIRST_SEASON = 19171918

const profile = (p) => `/${p.kind === 'goalie' ? 'goalie' : 'player'}/${p.player_id}`
const int = (v) => (v == null ? '–' : v.toLocaleString())

/** One list of players for a season; `lastCol` is the other end of their career (their last season for a debut, their first for a final one). */
function PlayerList({ title, rows, other, otherLabel, note }) {
  return (
    <div>
      <h2>{title} <span className="count">{rows.length}</span>{note && <Info label={title}>{note}</Info>}</h2>
      {rows.length === 0 ? <p className="status">None.</p> : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="left">Player</th><th className="left">Pos</th><th className="left">Team</th>
                <th title="Games played that season">GP</th><th title="Career regular-season games">Career GP</th>
                <th title="Career points for a skater, career wins for a goalie">Pts / W</th>
                <th className="left">{otherLabel}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.player_id}>
                  <td className="left"><Link to={profile(p)}>{p.name}</Link></td>
                  <td className="left">{p.position}</td>
                  <td className="left">{p.team ?? '–'}</td>
                  <td>{int(p.gp)}</td>
                  <td>{int(p.career_gp)}</td>
                  <td>{p.kind === 'goalie' ? `${int(p.career_wins)} W` : int(p.career_points)}</td>
                  <td className="left">{other(p)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function seasonOptions(current) {
  const out = []
  for (let s = current; s >= FIRST_SEASON; s -= 10001) out.push(s)
  return out
}

/** Debuts and final seasons for any season since 1917-18. */
function Careers({ current }) {
  const [params, setParams] = useSearchParams()
  const season = Number(params.get('season')) || current - 10001
  const data = useJson(`/api/history/season/${season}`)
  const pick = (e) => { const next = new URLSearchParams(params); next.set('season', e.target.value); setParams(next, { replace: true }) }
  return (
    <>
      <div className="controls">
        <label>Season{' '}
          <select value={season} onChange={pick}>
            {seasonOptions(current).map((s) => <option key={s} value={s}>{seasonLabel(s)}</option>)}
          </select>
        </label>
      </div>
      {!data ? <PageSkeleton /> : (
        <div className="split-tables">
          <PlayerList title="Debuts" rows={data.debuts} otherLabel="Last season" note="Players whose first NHL regular season was this one. Anyone still playing shows Active."
            other={(p) => (p.active_season ? 'Active' : seasonLabel(p.last_season))} />
          <PlayerList title="Final seasons" rows={data.finals} otherLabel="Debut"
            note="Players whose last NHL season to date was this one (anyone with games this season or last is counted as still active). Goalies before 2005-06 come from the team rosters."
            other={(p) => seasonLabel(p.first_season)} />
        </div>
      )}
    </>
  )
}

const range = (s) => (s.from === s.to ? seasonLabel(s.from) : `${seasonLabel(s.from)} to ${seasonLabel(s.to)}`)

/** Everyone who has worn a sweater number, from the team rosters. */
function Numbers() {
  const [params, setParams] = useSearchParams()
  const number = params.has('n') ? Number(params.get('n')) : 99
  const counts = useJson('/api/history/numbers')
  const wearers = useJson(`/api/history/numbers/${number}`)
  const pick = (n) => { const next = new URLSearchParams(params); next.set('n', n); setParams(next, { replace: true }) }
  return (
    <>
      <div className="number-grid" role="group" aria-label="Sweater number">
        {Array.from({ length: 100 }, (_, n) => (
          <button key={n} type="button" className={n === number ? 'on' : ''} aria-pressed={n === number}
            disabled={counts && !counts[n]} title={counts?.[n] ? `${counts[n]} players` : 'Nobody has worn it'} onClick={() => pick(n)}>{n}</button>
        ))}
      </div>
      <h2>#{number} {wearers && <span className="count">{wearers.length} players</span>}</h2>
      {!wearers ? <PageSkeleton /> : wearers.length === 0 ? <p className="status">Nobody has worn #{number}.</p> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th className="left">Player</th><th className="left">Pos</th><th className="left">With #{number}</th></tr></thead>
            <tbody>
              {wearers.map((w) => (
                <tr key={w.player_id}>
                  <td className="left"><Link to={`/${w.position === 'G' ? 'goalie' : 'player'}/${w.player_id}`}>{w.name}</Link></td>
                  <td className="left">{w.position}</td>
                  <td className="left">{w.stints.map((s) => `${s.team} ${range(s)}`).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

const LEADER_LABELS = {
  goals: 'Goals', assists: 'Assists', points: 'Points', wins: 'Wins', shutouts: 'Shutouts', save_pct: 'Save %', gaa: 'GAA',
}
const leaderValue = (stat, v) => (stat === 'save_pct' ? v.toFixed(3).replace(/^0/, '') : stat === 'gaa' ? v.toFixed(2) : v)

function Leaders({ title, stats, rows, kind }) {
  return (
    <>
      <h2>{title}</h2>
      <div className="split-tables">
        {stats.map((stat) => (
          <div key={stat}>
            <h3>{LEADER_LABELS[stat]}</h3>
            <div className="table-wrap">
              <table>
                <thead><tr><th className="left">Player</th><th className="left">Team</th><th>GP</th><th>{LEADER_LABELS[stat]}</th></tr></thead>
                <tbody>
                  {rows[stat].map((p) => (
                    <tr key={p.player_id}>
                      <td className="left"><Link to={`/${kind}/${p.player_id}`}>{p.name}</Link></td>
                      <td className="left">{p.team ?? '–'}</td>
                      <td>{p.gp}</td>
                      <td><strong>{leaderValue(stat, p.value)}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

function Standings({ data }) {
  const record = (r) => (r.ties && r.otl ? [r.wins, r.losses, r.ties, r.otl] : [r.wins, r.losses, r.ties || r.otl || 0]).join('-')
  return (
    <>
      <h2>Final standings <span className="count">{data.rows.length} teams</span>
        <Info label="Final standings">The NHL's standings on the last day of the regular season, in the league order of that era.
          Ties and overtime losses share the last column of the record, and divisions or conferences are blank in the early years.</Info></h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th><th className="left">Team</th><th className="left">Division</th><th>GP</th><th>Record</th><th>Pts</th><th>GF</th><th>GA</th><th>Diff</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r, i) => (
              <tr key={r.abbrev}>
                <td>{r.league_rank ?? i + 1}</td>
                <td className="left">{r.name}</td>
                <td className="left">{r.division ?? '–'}</td>
                <td>{r.gp}</td><td>{record(r)}</td><td><strong>{r.points}</strong></td>
                <td>{r.gf}</td><td>{r.ga}</td><td>{r.diff > 0 ? `+${r.diff}` : r.diff}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function Playoffs({ data }) {
  const side = (seed, won) => <span className={won ? 'winner' : ''} title={seed.name}>{seed.abbrev} <strong>{seed.wins}</strong></span>
  return (
    <>
      <h2>Playoffs {data.champion && <span className="count">Champion: {data.champion}</span>}</h2>
      <div className="split-tables">
        {data.rounds.map((round) => (
          <div key={round.round}>
            <h3>{round.title}</h3>
            <div className="table-wrap">
              <table>
                <tbody>
                  {round.series.map((s) => (
                    <tr key={s.letter}>
                      <td className="left">{side(s.top, s.winner === s.top.abbrev)}</td>
                      <td className="left">{side(s.bottom, s.winner === s.bottom.abbrev)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

/** A finished season: final standings, playoff results and the league leaders. */
function BySeason({ current }) {
  const [params, setParams] = useSearchParams()
  const season = Number(params.get('season')) || current - 10001
  const standings = useJson(`/api/history/season/${season}/standings`)
  const playoffs = useJson(`/api/history/season/${season}/playoffs`)
  const leaders = useJson(`/api/history/season/${season}/leaders`)
  const pick = (e) => { const next = new URLSearchParams(params); next.set('season', e.target.value); setParams(next, { replace: true }) }
  const options = seasonOptions(current).filter((s) => s < current)
  return (
    <>
      <div className="controls">
        <label>Season{' '}
          <select value={season} onChange={pick}>
            {options.map((s) => <option key={s} value={s}>{seasonLabel(s)}</option>)}
          </select>
        </label>
      </div>
      {!standings || !playoffs || !leaders ? <PageSkeleton /> : (
        <>
          {standings.rows.length === 0 ? <p className="status">No NHL season was played in {seasonLabel(season)}.</p> : <Standings data={standings} />}
          {playoffs.rounds.length > 0 && <Playoffs data={playoffs} />}
          <Leaders title="Skater leaders" stats={['points', 'goals', 'assists']} rows={leaders.skaters} kind="player" />
          {leaders.goalies && (
            <Leaders title="Goalie leaders" stats={['wins', 'save_pct', 'gaa', 'shutouts']} rows={leaders.goalies} kind="goalie" />
          )}
        </>
      )}
    </>
  )
}

export default function History() {
  const current = useJson('/api/seasons')?.current
  return (
    <main>
      <header>
        <PageIntro title="NHL history" subtitle="Debuts and final seasons, each season's standings, playoffs and leaders, and every sweater number.">Numbers come from each team's roster for the season, so a mid-season number change shows under the season's final roster.</PageIntro>
      </header>
      {!current ? <PageSkeleton /> : (
        <PageTabs tabs={[
          { id: 'careers', label: 'Debuts & final seasons', content: <Careers current={current} /> },
          { id: 'seasons', label: 'By season', content: <BySeason current={current} /> },
          { id: 'numbers', label: 'Sweater numbers', content: <Numbers /> },
        ]} />
      )}
    </main>
  )
}
