import { useTheme } from '../theme.js'

// Logos come from the NHL's public asset host; the dark-mode variant is used in the dark theme.
export default function TeamLogo({ team, size = 22 }) {
  const { dark } = useTheme()
  if (!team.logo_url) return null
  return <img src={dark && team.logo_dark_url ? team.logo_dark_url : team.logo_url} alt="" width={size} height={size} className="logo" loading="lazy" />
}
