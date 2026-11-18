import { Link } from 'react-router-dom'
import { TAB_GUIDES } from '../tabGuides.js'

/** A collapsed plain-language guide for one leaderboard tab, each entry linking to its full glossary definition. */
export default function TabGuide({ id }) {
  const guide = TAB_GUIDES[id]
  if (!guide) return null
  return (
    <details className="guide">
      <summary>{guide.summary}</summary>
      <div className="guide-body">
        <p className="guide-lead">{guide.lead}</p>
        <dl>
          {guide.items.map(([term, text, gid]) => (
            <div key={gid}>
              <dt><Link to={`/glossary#${gid}`}>{term}</Link></dt>
              <dd>{text}</dd>
            </div>
          ))}
        </dl>
        <p className="guide-foot">
          Hover any column heading for its definition. <Link to={`/glossary#${guide.section}`}>See these definitions in the glossary</Link>
          {' '}or <Link to="/glossary">every definition</Link>.
        </p>
      </div>
    </details>
  )
}
