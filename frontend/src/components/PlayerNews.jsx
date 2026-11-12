import { Skeleton } from './Skeleton.jsx'
import { currentTeam } from '../news.js'
import { NewsItems, NOTE, useStories } from './NewsList.jsx'

/** One block of a News tab: a heading, then the stories (or a loading, error or empty message). */
function Block({ title, state, empty, hideTeam, hidePlayer }) {
  return (
    <>
      <h2>{title}</h2>
      {state.error && <p className="status">Couldn't load the news: {state.error}</p>}
      {!state.error && !state.stories && <Skeleton rows={4} />}
      {state.stories && state.stories.length === 0 && <p className="status">{empty}</p>}
      {state.stories && state.stories.length > 0 && <NewsItems stories={state.stories} hideTeam={hideTeam} hidePlayer={hidePlayer} />}
    </>
  )
}

/** A player's News tab: the stories that mention them, then the latest from their team (leaving out the ones already shown above). */
export default function PlayerNews({ playerId, name, team }) {
  const abbrev = currentTeam(team)
  const mine = useStories({ player: playerId, limit: 15 })
  const club = useStories({ team: abbrev, limit: 15 })
  const seen = new Set((mine.stories ?? []).map((s) => s.url))
  const more = club.stories && { ...club, stories: club.stories.filter((s) => !seen.has(s.url)).slice(0, 8) }
  return (
    <>
      <Block title={`Mentioning ${name}`} state={mine} empty={`No recent headlines mention ${name}.`} hidePlayer={playerId} />
      {abbrev && <Block title={`More ${abbrev} news`} state={more ?? club} empty={`Nothing else about ${abbrev} right now.`} hideTeam={abbrev} />}
      <p className="news-note">{NOTE}</p>
    </>
  )
}
