import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getJson } from '../lists.js'
import { newsUrl, timeAgo } from '../news.js'
import { Skeleton } from './Skeleton.jsx'

export const NOTE = 'Headlines and excerpts come from public feeds and link to the publishers.'

/** Stories for a query ({ team, player, top, limit }): { stories, error }, with stories null while loading. */
export function useStories(query) {
  const url = newsUrl(query)
  const [state, setState] = useState({ url: null, stories: null, error: null })
  useEffect(() => {
    let current = true
    getJson(url)
      .then((d) => current && setState({ url, stories: d.stories, error: null }))
      .catch((e) => current && setState({ url, stories: null, error: e.message }))
    return () => { current = false }
  }, [url])
  return state.url === url ? state : { stories: null, error: null }
}

/** The stories as a list: headline linking to the publisher, a short excerpt, then source, age and the teams and players mentioned.
 *  `hideTeam` / `hidePlayer` leave out the tag of the team or player the list is already about. `columns` lays the list out in two columns on wide screens. */
export function NewsItems({ stories, hideTeam, hidePlayer, columns = false }) {
  return (
    <ul className={`news-list${columns ? ' cols' : ''}`}>
      {stories.map((s) => {
        const teams = s.teams.filter((t) => t !== hideTeam).slice(0, 3)
        const players = s.players.filter((p) => p.id !== hidePlayer).slice(0, 3)
        return (
          <li key={s.url} className="news-item">
            <a className="news-title" href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a>
            {s.summary && <p className="news-summary">{s.summary}</p>}
            <div className="news-meta">
              <span className="news-source">{s.source}</span>
              <time dateTime={s.published_at} title={new Date(s.published_at).toLocaleString()}>{timeAgo(s.published_at)}</time>
              {teams.map((t) => <Link key={t} className="news-tag" to={`/team/${t}`}>{t}</Link>)}
              {players.map((p) => <Link key={p.id} className="news-tag" to={`/${p.kind === 'goalie' ? 'goalie' : 'player'}/${p.id}`}>{p.name}</Link>)}
            </div>
          </li>
        )
      })}
    </ul>
  )
}

/** A self-loading news list for a query, with loading, error and empty states. */
export default function NewsList({ team, player, top, limit = 20, empty = 'No stories right now.', hideTeam, hidePlayer, note = false, columns = false }) {
  const { stories, error } = useStories({ team, player, top, limit })
  if (error) return <p className="status">Couldn't load the news: {error}</p>
  if (!stories) return <Skeleton rows={6} />
  if (stories.length === 0) return <p className="status">{empty}</p>
  return (
    <>
      <NewsItems stories={stories} hideTeam={hideTeam ?? team} hidePlayer={hidePlayer ?? player} columns={columns} />
      {note && <p className="news-note">{NOTE}</p>}
    </>
  )
}
