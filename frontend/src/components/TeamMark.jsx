import { useTheme } from '../theme.js'

// The NHL's public logo host has one file per team abbreviation, so a logo needs no data beyond the abbreviation.
export default function TeamMark({ abbrev, size = 28 }) {
  const { dark } = useTheme()
  return (
    <img
      src={`https://assets.nhle.com/logos/nhl/svg/${abbrev}_${dark ? 'dark' : 'light'}.svg`}
      alt="" width={size} height={size} className="logo" loading="lazy"
    />
  )
}
