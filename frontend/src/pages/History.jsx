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

export default function History() {
  const current = useJson('/api/seasons')?.current
  return (
    <main>
      <header>
        <PageIntro title="NHL history">Who debuted and who played their last season in any year since 1917-18, and who has worn each sweater number.
          Numbers come from each team's roster for the season, so a mid-season number change shows under the season's final roster.</PageIntro>
      </header>
      {!current ? <PageSkeleton /> : (
        <PageTabs tabs={[
          { id: 'careers', label: 'Debuts & final seasons', content: <Careers current={current} /> },
          { id: 'numbers', label: 'Sweater numbers', content: <Numbers /> },
        ]} />
      )}
    </main>
  )
}
