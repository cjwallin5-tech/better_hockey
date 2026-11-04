import { Link, useLocation, useNavigate } from 'react-router-dom'

/**
 * "Back" for a detail page. When you got here from another page on the site it returns to that page (a trophy list, a standings
 * table, a comparison), filters and tab included; opened directly (a shared link, a new tab) it goes to `to`, the page's home list.
 * The label is always "Back".
 */
export default function BackLink({ to }) {
  const navigate = useNavigate()
  const { key } = useLocation()
  const cameFromSite = key !== 'default' // the first entry in a tab has no earlier page on the site
  const onClick = (e) => {
    if (!cameFromSite || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return // let "open in new tab" work
    e.preventDefault()
    navigate(-1)
  }
  return <Link to={to} className="back" onClick={onClick}>← Back</Link>
}
