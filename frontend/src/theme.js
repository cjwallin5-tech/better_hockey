// The site is dark only: it was designed for the dark theme, and the light one was never finished. The logos still ask
// whether they are on a dark page, so this stays a hook that always says yes.
export function useTheme() {
  return { dark: true }
}
