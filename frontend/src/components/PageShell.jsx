/** A page's outer wrapper: a <main> on its own, a plain block when the page is a tab inside another page. */
export default function PageShell({ embedded = false, children }) {
  return embedded ? <div>{children}</div> : <main>{children}</main>
}
