import { Link } from 'react-router-dom'

/** What a page that needs an account shows to someone signed out: what the account is for, anything useful to look at meanwhile, and one way in. */
export default function SignInPrompt({ lead, children }) {
  return (
    <section className="card start">
      <div className="eyebrow">Free account</div>
      <p className="start-lead">{lead}</p>
      {children}
      <Link to="/account" className="start-cta">Log in or create an account</Link>
    </section>
  )
}
