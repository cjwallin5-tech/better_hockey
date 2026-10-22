import { Component } from 'react'

/** Catches a crash while rendering a page, so a bug shows a message and a way out instead of a blank screen. */
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Page crashed:', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <main>
        <h1>Something went wrong</h1>
        <p className="status">This page hit an error and couldn't be shown. The rest of the site still works.</p>
        <p className="header-actions">
          <button type="button" className="link-button" onClick={() => window.location.reload()}>Reload the page</button>
          <a href="/">Go to the home page</a>
        </p>
        <details className="notice">
          <summary>Technical details</summary>
          <pre>{String(this.state.error?.stack ?? this.state.error)}</pre>
        </details>
      </main>
    )
  }
}
