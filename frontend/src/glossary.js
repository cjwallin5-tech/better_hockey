// Plain-English meaning of the abbreviations used as column headers, shown as a tooltip.
const TERMS = {
  Team: 'Team', Pos: 'Position', Age: 'Age', Debut: 'First NHL season',
  GP: 'Games played', G: 'Goals', A: 'Assists', P: 'Points (goals + assists)', 'P/GP': 'Points per game played',
  '+/-': 'Plus/minus: even-strength goals for minus against while on the ice',
  PIM: 'Penalty minutes', PPG: 'Power-play goals', PPP: 'Power-play points', SHG: 'Short-handed goals',
  SHP: 'Short-handed points', GWG: 'Game-winning goals', OTG: 'Overtime goals', ENG: 'Empty-net goals',
  Shots: 'Shots on goal', 'S%': 'Shooting percentage: goals divided by shots on goal',
  'FO%': 'Faceoff win percentage', TOI: 'Time on ice per game', '5v5 TOI': 'Five-on-five time on ice per game',
  'EV TOI': 'Even-strength time on ice per game', 'PP TOI': 'Power-play time on ice per game',
  'SH TOI': 'Short-handed time on ice per game', 'PP TOI%': 'Share of the team’s power-play time this player is on the ice',
  'SH TOI%': 'Share of the team’s short-handed time this player is on the ice',
  'Shifts/GP': 'Shifts per game', 'Sec/Shift': 'Average shift length in seconds',
  Hits: 'Hits delivered', BLK: 'Blocked shots', Blocks: 'Blocked shots', TK: 'Takeaways', GV: 'Giveaways',
  Takeaways: 'Takeaways', Giveaways: 'Giveaways', 'Missed shots': 'Shot attempts that missed the net',
  'Shot attempts': 'All shot attempts: on goal, missed and blocked',
  'Hits/60': 'Hits per 60 minutes of ice time', 'BLK/60': 'Blocked shots per 60 minutes of ice time',
  'TK/60': 'Takeaways per 60 minutes of ice time', 'GV/60': 'Giveaways per 60 minutes of ice time',
  CF: 'Corsi for: shot attempts by the team while on the ice at 5v5',
  CA: 'Corsi against: shot attempts against the team while on the ice at 5v5',
  'CF%': 'Corsi for percentage: share of 5v5 shot attempts the team takes while on the ice (50% is even)',
  'CF% Rel': 'Corsi % relative: team CF% with this player on the ice minus with them off',
  FF: 'Fenwick for: unblocked shot attempts by the team while on the ice at 5v5',
  FA: 'Fenwick against: unblocked shot attempts against the team while on the ice at 5v5',
  'FF%': 'Fenwick for percentage: like Corsi but ignoring blocked shots',
  'FF% Rel': 'Fenwick % relative: team FF% with this player on the ice minus with them off',
  'OZ Start%': 'Share of 5v5 shifts that start in the offensive zone (of those starting in either end)',
  'EV GF': 'Even-strength goals for while on the ice', 'EV GA': 'Even-strength goals against while on the ice',
  'EV GF%': 'Share of even-strength goals that were for the player’s team while on the ice',
  PDO: 'On-ice shooting % plus save % at 5v5. Near 100% is average; far from it is usually luck',
  ixG: 'Individual expected goals: how many goals the quality of their own shots would normally produce',
  'G − ixG': 'Goals minus individual expected goals. Positive means finishing above the chances',
  'xGF%': 'Expected goals for percentage: share of 5v5 shot quality the team has while on the ice',
  'PPP/60': 'Power-play points per 60 minutes of power-play time',
  'PP GA/60 on ice': 'Power-play goals against per 60 minutes while on the ice short-handed',
  GS: 'Games started', W: 'Wins', L: 'Losses', T: 'Ties', OTL: 'Overtime losses',
  'SV%': 'Save percentage: saves divided by shots against', GAA: 'Goals against average per 60 minutes',
  SO: 'Shutouts', Saves: 'Saves', SA: 'Shots against', GA: 'Goals against', Minutes: 'Minutes played', MIN: 'Minutes played',
  GSAA: 'Goals saved above average: goals a league-average goalie would have allowed on the same shots, minus actual',
  'GSAA/60': 'Goals saved above average per 60 minutes', 'SA/60': 'Shots against per 60 minutes',
  QS: 'Quality starts: starts with a save % above the league average (or 3 goals against or fewer with a save % over .885)',
  'QS%': 'Share of starts that were quality starts', 'Goal supp.': 'Average goals scored by the goalie’s team per start',
  'EV SA': 'Shots against at even strength', 'EV SV%': 'Save percentage at even strength',
  'PK SA': 'Shots against while the goalie’s team is short-handed', 'PK SV%': 'Save percentage while short-handed',
  'PP SA': 'Shots against while the goalie’s team is on the power play', 'PP SV%': 'Save percentage while on the power play',
  'Adj G': 'Goals adjusted to the scoring level of the era', 'Adj A': 'Assists adjusted to the scoring level of the era',
  'Adj P': 'Points adjusted to the scoring level of the era', 'Adj P/GP': 'Era-adjusted points per game',
  'First goals': 'Goals that were the first of the game',
}
const LAST = /^L(\d+) (.+)$/

/** Tooltip text for a column label, or undefined when we have nothing to say. */
export function describe(label) {
  if (TERMS[label]) return TERMS[label]
  if (/^Pace \(\d+\)$/.test(label)) return `Point pace: points per game so far, projected to a full ${label.match(/\d+/)[0]}-game season`
  const m = LAST.exec(label)
  if (m) {
    const [, n, rest] = m
    if (rest === 'Pace') return `Point pace over the last ${n} games, projected to a full season`
    if (rest === 'P') return `Points in the last ${n} games`
    const vs = rest.endsWith(' vs season')
    const base = TERMS[vs ? rest.slice(0, -10) : rest]
    if (base) return `Last ${n} games${vs ? ', compared with the season' : ''}: ${base[0].toLowerCase()}${base.slice(1)}`
  }
  return undefined
}
