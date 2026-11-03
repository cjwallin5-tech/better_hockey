import { Link } from 'react-router-dom'

/** The quiet stand-in for a Fantasy tab that has nothing to show until the roster has players: one line and a way to fix it. */
export default function NeedRoster({ what }) {
  return (
    <div className="need-roster">
      <p>Add players to {what}.</p>
      <Link to="/fantasy" className="start-add">Add players</Link>
    </div>
  )
}
