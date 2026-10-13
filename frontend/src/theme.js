import { useCallback, useEffect, useState } from 'react'

// Light/dark theme: follows the OS unless the viewer picks one. The choice lives in localStorage
// (which can be unavailable, so it's guarded) and on <html data-theme>, which the CSS keys off.
const KEY = 'nhl-stats.theme'
const EVENT = 'theme-changed'

const readPref = () => {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}
const osDark = () => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false

export function useTheme() {
  const [pref, setPref] = useState(readPref)
  const [os, setOs] = useState(osDark)

  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    const onOs = () => setOs(osDark())
    const onPref = () => setPref(readPref())
    mq?.addEventListener('change', onOs)
    window.addEventListener(EVENT, onPref)
    window.addEventListener('storage', onPref)
    return () => {
      mq?.removeEventListener('change', onOs)
      window.removeEventListener(EVENT, onPref)
      window.removeEventListener('storage', onPref)
    }
  }, [])

  const dark = pref ? pref === 'dark' : os

  const toggle = useCallback(() => {
    const next = dark ? 'light' : 'dark'
    try {
      localStorage.setItem(KEY, next)
    } catch {
      // not persisted, but the toggle still works for this visit
    }
    document.documentElement.dataset.theme = next
    window.dispatchEvent(new Event(EVENT))
    setPref(next)
  }, [dark])

  return { dark, toggle }
}
