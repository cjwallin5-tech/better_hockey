// The glossary page's entries, grouped. Each term: id (the #link), name, abbr (what appears in table headers), what (plain-English meaning),
// read (how to interpret it, optional). The A to Z list at the bottom of the page comes from glossary.js, so every column label is covered.
export const GROUPS = [
  {
    id: 'possession',
    title: 'Possession and shot attempts',
    intro: 'Possession stats ask: while this player is on the ice, which team has the puck more? They are counted at five-on-five (no power plays), so every player is judged on the same kind of hockey.',
    terms: [
      { id: 'five-on-five', name: 'Five-on-five (5v5)', abbr: '5v5', what: 'Both teams have five skaters on the ice (plus goalies). Most of a game is played this way, and it leaves out power plays and penalty kills that would skew the numbers.' },
      { id: 'shot-attempt', name: 'Shot attempt', abbr: 'Shot attempts', what: 'Any try at the net: a shot on goal, a shot that misses the net, or a shot that is blocked by a defender.' },
      { id: 'corsi', name: 'Corsi', abbr: 'CF, CA, CF%', what: 'Counts every shot attempt. CF is attempts for your team while the player is on the ice, CA is attempts against. CF% is CF divided by CF + CA.', read: 'Example: 55 attempts for and 45 against is 55%. 50% is even, above 50% means the team is out-shooting its opponent with him on the ice. Most regulars land between about 45% and 55%.' },
      { id: 'fenwick', name: 'Fenwick', abbr: 'FF, FA, FF%', what: 'The same as Corsi but leaving out blocked shots, which some people feel measure effort more than chance quality.', read: 'Read it exactly like Corsi: 50% is even.' },
      { id: 'relative', name: 'Relative (Rel)', abbr: 'CF% Rel, FF% Rel', what: 'The team’s Corsi (or Fenwick) with the player on the ice minus the same number with him off the ice.', read: 'Plus means the team does better with him than without him; minus means worse. It helps compare players on strong and weak teams.' },
      { id: 'zone-starts', name: 'Offensive-zone start %', abbr: 'OZ Start%', what: 'The share of a player’s five-on-five shifts that begin with a faceoff in the offensive zone (out of those that begin in either end).', read: 'Players who start more shifts near the other net have an easier job, so their possession numbers can look better than their play.' },
      { id: 'on-ice', name: 'On the ice', abbr: 'on-ice', what: 'Counted only while the player is playing, not for the whole game. A stat labelled “on ice” belongs to the team during his shifts, not to him alone.' },
    ],
  },
  {
    id: 'expected',
    title: 'Expected goals',
    intro: 'Not every shot is equal: a shot from the slot is worth more than one from the boards. Expected goals give each shot a chance of scoring and add them up. Ours come from our own model, built from past seasons of shots.',
    terms: [
      { id: 'xg', name: 'Expected goals (xG)', abbr: 'xG, xGF, xGA', what: 'The number of goals the quality of the shots would normally produce. xGF is expected goals for, xGA is expected goals against.', read: 'If a team scored 3 goals from shots worth 2 expected goals, it finished above the chances.' },
      { id: 'ixg', name: 'Individual expected goals (ixG)', abbr: 'ixG', what: 'Expected goals from a player’s own shots only.' },
      { id: 'g-ixg', name: 'Goals minus expected goals', abbr: 'G − ixG, G − xG', what: 'Actual goals minus expected goals.', read: 'Positive means finishing above the chances (good shooting or good luck); negative means below. Big gaps tend to shrink over a season.' },
      { id: 'xgf-pct', name: 'Expected goals for percentage', abbr: 'xGF%', what: 'The team’s share of the five-on-five expected goals while the player is on the ice.', read: 'Like Corsi, but it values good shots more than any shot. 50% is even.' },
      { id: 'gsax', name: 'Goals saved above expected', abbr: 'GSAx', what: 'For goalies: expected goals against minus goals actually allowed.', read: 'Positive means the goalie stopped more than the shots he faced were expected to score.' },
    ],
  },
  {
    id: 'luck',
    title: 'Luck and sustainability',
    intro: 'Some numbers are mostly skill and some drift back toward average. These help tell which is which.',
    terms: [
      { id: 'pdo', name: 'PDO', abbr: 'PDO', what: 'A team’s shooting percentage plus its save percentage while a player is on the ice at five-on-five.', read: 'It tends to drift back toward 100. A number far above 100 often means good luck, far below means bad luck, so those players may be due for a change.' },
      { id: 'z-score', name: 'Standard deviations (Z)', abbr: 'Z, Goals Z, Pts Z', what: 'How far a result sits from what chance alone would produce, measured in standard deviations.', read: 'We flag a gap of 1.5 or more as hot or cold. The larger the number, the less likely it is to be pure luck, but short samples still swing a lot.' },
      { id: 'sample-size', name: 'Small samples', abbr: 'dimmed numbers', what: 'Early in a season, or for players with few games, percentages swing wildly. The site dims numbers that do not yet have enough games behind them.' },
    ],
  },
  {
    id: 'scoring',
    title: 'Scoring and ice time',
    terms: [
      { id: 'points', name: 'Points', abbr: 'P', what: 'Goals plus assists. P/GP is points per game played.' },
      { id: 'pace', name: 'Point pace', abbr: 'Pace', what: 'Points per game so far, projected over a full season. The site uses an 84-game season. L10 pace uses only the last 10 games.', read: 'Early-season pace is noisy: a hot week can look like a 150-point season.' },
      { id: 'plus-minus', name: 'Plus/minus', abbr: '+/-', what: 'Even-strength goals for minus goals against while the player is on the ice.', read: 'It depends heavily on teammates and goaltending, so treat it as a rough guide.' },
      { id: 'special-teams', name: 'Power play and penalty kill', abbr: 'PPG, PPP, SHG, SHP', what: 'PPG and PPP are power-play goals and points (the team has an extra skater). SHG and SHP are short-handed goals and points (the team is a skater down).' },
      { id: 'goal-types', name: 'Special goals', abbr: 'GWG, OTG, ENG', what: 'GWG is game-winning goals, OTG is overtime goals, ENG is empty-net goals (scored when the other team has pulled its goalie).' },
      { id: 'toi', name: 'Time on ice', abbr: 'TOI, EV TOI, PP TOI', what: 'Minutes played per game, split by even strength, power play and penalty kill. PP TOI% is the share of the team’s power-play time a player is on the ice for.', read: 'More ice time means more chances to score; it is one of the best clues to a player’s role.' },
      { id: 'per-60', name: 'Per 60', abbr: '/60', what: 'A rate per 60 minutes of ice time (about one full game), so players with different ice time can be compared fairly.' },
    ],
  },
  {
    id: 'goalies',
    title: 'Goalies',
    terms: [
      { id: 'sv-pct', name: 'Save percentage', abbr: 'SV%', what: 'Saves divided by shots against. An NHL starter is usually around .900 to .920.' },
      { id: 'gaa', name: 'Goals against average', abbr: 'GAA', what: 'Goals allowed per 60 minutes. Lower is better.', read: 'It depends on the team in front of the goalie, so save percentage is usually a cleaner measure.' },
      { id: 'gsaa', name: 'Goals saved above average', abbr: 'GSAA', what: 'The goals a league-average goalie would have allowed on the same shots, minus the goals actually allowed.', read: 'Positive means better than average.' },
      { id: 'quality-start', name: 'Quality start', abbr: 'QS, QS%', what: 'A start with a save percentage above the league average, or three goals against or fewer with a save percentage over .885.' },
      { id: 'danger', name: 'Shot danger zones', abbr: 'High, Mid, Long', what: 'Where shots come from: high is the slot and crease, mid is the circles and faceoff dots, long is the perimeter. A goalie’s save percentage is shown for each.' },
    ],
  },
  {
    id: 'standings',
    title: 'Standings and playoffs',
    terms: [
      { id: 'standings-points', name: 'Standings points', abbr: 'PTS, P%', what: 'Two for a win, one for an overtime or shootout loss, none for a regulation loss. P% is the share of the available points a team has earned.' },
      { id: 'streaks', name: 'Streak and last 10', abbr: 'Strk, L10', what: 'The current run of wins (W), losses (L) or overtime losses (OT) in a row, and the record over the last 10 games.' },
      { id: 'playoff-odds', name: 'Playoff odds', abbr: 'Make playoffs, Win Cup', what: 'Chances from a simulation that plays out the rest of the season many times using each team’s strength and schedule.', read: 'They are probabilities, not predictions: a 20% chance still happens one time in five.' },
    ],
  },
  {
    id: 'records',
    title: 'History and records',
    terms: [
      { id: 'hat-trick', name: 'Hat trick and big games', abbr: 'Hat tricks', what: 'A hat trick is three or more goals in one game. The big-game columns count games with at least that many goals, assists or points, so every 4-goal game is also a hat trick.' },
      { id: 'milestone-seasons', name: 'Milestone seasons', abbr: '100-pt seasons, 50-goal seasons', what: 'How many regular seasons a player reached the mark (for example 100 or more points), whatever the schedule length of the time.' },
      { id: 'rookie-season', name: 'Rookie season', abbr: 'Rookie P, Rookie GP', what: 'The first season with more than 25 NHL games, for a player under 26 when it started (the Calder Trophy’s rules). The NHL’s second test is not applied, so a few players can differ from the official list.' },
      { id: 'era-adjusted', name: 'Era-adjusted scoring', abbr: 'Adj G, Adj A, Adj P', what: 'Each season’s goals and assists rescaled to today’s scoring level, separately for forwards and defensemen, because the league averaged about 4 goals per team game in the early 1980s and under 3 in the mid-2000s.', read: 'A fairer comparison across eras, not a ruling: it does not correct for ice time, power-play share, expansion or schedule length.' },
      { id: 'best-seasons', name: 'Best single seasons', abbr: 'Best seasons', what: 'One row per player per season, ranked by any stat, back to 1917-18 for skaters. Per-game and percentage stats count only players with at least half the games of the busiest player that season.' },
    ],
  },
  {
    id: 'fantasy',
    title: 'Fantasy',
    terms: [
      { id: 'replacement', name: 'Value over replacement', abbr: 'Value', what: 'How many fantasy points a player is worth over the rest of the season compared with a player you could pick up for free, under your own league’s scoring.' },
      { id: 'expected-fp', name: 'Expected fantasy points', abbr: 'Expected FP/GP, Projected FP', what: 'Fantasy points per game we expect going forward, after pulling a short sample toward the player’s record or the league average, times the games left.' },
    ],
  },
]

/** The label a column header stands for, with the season window and comparison wrapped around it stripped: "L10 CF% vs season" is "CF%", "Pace (84)" is "Pace". */
export const baseLabel = (label) => label.replace(/[▲▼]/g, '').trim().replace(/^L\d+ /, '').replace(/ vs season$/, '').replace(/^Pace \(\d+\)$/, 'Pace')

/** Where a column label's full explanation lives: its own entry on the glossary page when it has one, else the page opened with the label searched. */
export function glossaryLink(label) {
  const base = baseLabel(label).toLowerCase()
  for (const g of GROUPS) {
    for (const t of g.terms) {
      if (t.name.toLowerCase() === base || t.abbr.toLowerCase().split(',').some((a) => a.trim() === base)) return `/glossary#${t.id}`
    }
  }
  return `/glossary?q=${encodeURIComponent(baseLabel(label))}`
}
