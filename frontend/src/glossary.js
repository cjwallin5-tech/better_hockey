// Plain-English meaning of the abbreviations used as column headers, shown as a tooltip.
const TERMS = {
  Team: 'Team', Pos: 'Position', Age: 'Age', Debut: 'First NHL season',
  GP: 'Games played', G: 'Goals', A: 'Assists', P: 'Points (goals + assists)', 'P/GP': 'Points per game played',
  '+/-': 'Plus/minus: even-strength goals for minus against while on the ice',
  PIM: 'Penalty minutes', PPG: 'Power-play goals', PPP: 'Power-play points', SHG: 'Short-handed goals',
  SHP: 'Short-handed points', GWG: 'Game-winning goals', OTG: 'Overtime goals', ENG: 'Empty-net goals',
  Shots: 'Shots on goal', 'S%': 'Shooting percentage: goals divided by shots on goal',
  'FO%': 'Faceoff win percentage', TOI: 'Time on ice (an average per game in season tables)', '5v5 TOI': 'Five-on-five time on ice (an average per game in season tables)',
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
  // Smaller tables (game logs, standings, luck, fantasy, tracking and so on)
  S: 'Shots on goal', SOG: 'Shots on goal', SV: 'Saves', Dec: 'Decision in the game: win, loss or overtime loss', Start: 'Whether the goalie started the game or came on in relief',
  Pace: 'Point pace: points per game so far, projected over a full season',
  'L10 pace': 'Point pace over the last 10 games, projected over a full season', 'L10 P': 'Points in the last 10 games',
  'S/GP': 'Shots on goal per game', 'Shots/GP': 'Shots against per game', 'Hits/GP': 'Hits per game',
  'Recent SV%': 'Save percentage over the goalie\u2019s recent starts', 'Recent GSAA': 'Goals saved above average over the goalie\u2019s recent starts',
  PTS: 'Standings points: 2 for a win, 1 for an overtime or shootout loss', 'P%': 'Points percentage: standings points earned out of the points available',
  GF: 'Goals for', Diff: 'Goal differential: goals for minus goals against', 'PP%': 'Power-play percentage: how often the team scores on the power play',
  'PK%': 'Penalty-kill percentage: how often the team stops the opponent\u2019s power play from scoring', L10: 'Record over the last 10 games',
  Strk: 'Current streak: wins (W), losses (L) or overtime losses (OT) in a row',
  Together: 'Five-on-five time the two have played together', 'CF% together': 'Corsi percentage while the two are on the ice together',
  'CF% player apart': 'Corsi percentage for this player\u2019s team when he plays without this teammate',
  'CF% teammate apart': 'Corsi percentage for the team when the teammate plays without this player',
  'GF\u2013GA': 'Goals for and against while the two are on the ice together',
  '5v5 min': 'Five-on-five minutes played', 'xGA/60': 'Expected goals against per 60 minutes at five-on-five while on the ice',
  High: 'Save percentage on high-danger shots (from the slot and crease)', Mid: 'Save percentage on mid-range shots (from the circles and faceoff dots)',
  Long: 'Save percentage on long-range shots (from the perimeter)', 'Games > .900': 'Share of games with a save percentage above .900',
  'Top speed': 'Fastest skating speed recorded, in mph', '22+ bursts': 'Skating bursts of 22 mph or faster', 'Hardest shot': 'Hardest shot recorded, in mph',
  'Avg shot': 'Average shot speed, in mph', 'Miles / GP': 'Distance skated per game, in miles', 'OZ %': 'Share of ice time spent in the offensive zone',
  'DZ %': 'Share of ice time spent in the defensive zone', 'NHL percentile': 'Where this ranks among all NHL players with this stat (100 is the best)',
  'Career now': 'Career total so far', 'To go': 'How many more are needed to reach the milestone', 'Est. games': 'Estimated games until the milestone is reached',
  'Projected pts': 'Projected final standings points', 'Likely range': 'The range the final points total will most likely fall in',
  'Make playoffs': 'Chance of making the playoffs', 'Win division': 'Chance of winning the division', 'Best record': 'Chance of finishing with the league\u2019s best record',
  'PP share': 'Share of the team\u2019s power-play time, earlier games then recent games', 'PP time / game': 'Power-play ice time per game, earlier games then recent games',
  'Even strength / game': 'Even-strength ice time per game, earlier games then recent games', 'Total / game': 'Total ice time per game, earlier games then recent games',
  'Power-play unit': 'Power-play unit, earlier then recent: PP1 plays the most (45% or more of the team\u2019s power play), PP2 at least 15%',
  Attempts: 'Unblocked shot attempts, the shots our expected-goals model scores', xG: 'Expected goals: the goals the quality of the shots would normally produce',
  'G \u2212 xG': 'Goals minus expected goals. Positive means finishing above what the shots suggested',
  'Goals Z': 'How far the goals-minus-expected-goals gap is from what chance alone produces, in standard deviations (1.5 or more is flagged)',
  'Pts Z': 'How far the points luck is from what chance alone produces, in standard deviations (1.5 or more is flagged)',
  Z: 'How far the gap from expected is from what chance alone produces, in standard deviations (1.5 or more is flagged)',
  xPts: 'Points expected from shot quality: own expected goals plus an estimate of assists', 'Pts luck': 'Points minus expected points. Positive means more than the chances suggested',
  'Sh%': 'Shooting percentage', 'xSh%': 'Shooting percentage the quality of the shots predicts', 'Per 100 shots': 'Goals saved above expected for every 100 shots faced',
  'Sv%': 'Save percentage', 'xSv%': 'Save percentage the quality of the shots faced predicts', 'Shots faced': 'Shots on goal faced',
  'Goals allowed': 'Goals allowed on shots that have an expected-goals value (empty-net goals left out)', xGA: 'Expected goals against: the goals the quality of the shots faced would normally produce',
  GSAx: 'Goals saved above expected: expected goals against minus goals allowed', Status: 'Hot or cold flag: shown when the gap from expected is 1.5 standard deviations or more',
  Value: 'Worth over the rest of the season compared with a replacement-level player, under your league settings', 'Per GP': 'Fantasy points per game played',
  'Fantasy pts': 'Fantasy points so far under your league scoring', 'Games left': 'Games the player\u2019s team has left in the regular season',
  'Projected FP': 'Expected fantasy points over the games left', Net: 'What you get minus what you give',
  'Style match': 'How closely the playing style matches (higher is closer)',
  'xGF/G': 'Expected goals for per game', 'xGA/G': 'Expected goals against per game',
  'Expected FP/GP': 'Fantasy points per game we expect going forward, after pulling a short sample toward the player\u2019s record or the average',
}
const LAST = /^L(\d+) (.+)$/

/** Tooltip text for a column label, or undefined when we have nothing to say. */
export function describe(label) {
  if (TERMS[label]) return TERMS[label]
  if (/^Pace \(\d+\)$/.test(label)) return `Point pace: points per game so far, projected to a full ${label.match(/\d+/)[0]}-game season`
  const m = LAST.exec(label)
  if (m) {
    const [, n, rest] = m
    if (rest.toLowerCase() === 'pace') return `Point pace over the last ${n} games, projected to a full season`
    if (rest === 'P') return `Points in the last ${n} games`
    const vs = rest.endsWith(' vs season')
    const base = TERMS[vs ? rest.slice(0, -10) : rest]
    if (base) return `Last ${n} games${vs ? ', compared with the season' : ''}: ${base[0].toLowerCase()}${base.slice(1)}`
  }
  return undefined
}
