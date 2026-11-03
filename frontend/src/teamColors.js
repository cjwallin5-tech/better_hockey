// Each team's main color, lightened where the real one is too dark to read on the dark theme. Used for card accents only.
const COLORS = {
  ANA: '#F47A38', BOS: '#FFB81C', BUF: '#3A6FD8', CGY: '#D2001C', CAR: '#CC0000', CHI: '#CF0A2C',
  COL: '#A5314F', CBJ: '#2A6BC4', DAL: '#00A870', DET: '#CE1126', EDM: '#FF6A13', FLA: '#C8102E',
  LAK: '#A2AAAD', MIN: '#2E7D5B', MTL: '#AF1E2D', NSH: '#FFB81C', NJD: '#CE1126', NYI: '#3E7BD6',
  NYR: '#2D6FD6', OTT: '#D2232A', PHI: '#F74902', PIT: '#FFB81C', SJS: '#2B8FA0', SEA: '#68A2B9',
  STL: '#3A6FD8', TBL: '#3A6FD8', TOR: '#3A6FD8', UTA: '#6CACE4', VAN: '#3E8FD0', VGK: '#B4975A',
  WSH: '#D8212F', WPG: '#4A78C2',
}

export const teamColor = (abbrev) => COLORS[abbrev] ?? '#8a93a0'
