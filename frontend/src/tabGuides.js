// The collapsed guides above the leaderboard's Speed & shots and Projection & luck tabs: [term, plain meaning, glossary id].
export const TAB_GUIDES = {
  speed: {
    summary: 'What the speed and shot columns mean',
    section: 'tracking',
    lead: 'These come from the NHL’s EDGE tracking, which has measured every player since 2021-22. Speeds are in mph and distances in miles.',
    items: [
      ['Top speed', 'The fastest the player skated at any point this season.', 'top-speed'],
      ['22+ mph bursts', 'How often the player skated faster than 22 mph. A steadier sign of speed than one top speed.', 'bursts'],
      ['Hardest shot, Avg shot, 90+ mph shots', 'The single hardest shot, the average over all tracked shots, and how many attempts were 90 mph or harder.', 'shot-speed'],
      ['Miles, Miles/GP', 'Distance skated in total and per game. It mostly follows ice time.', 'distance'],
      ['OZ time, DZ time, HD SOG', 'Share of ice time in the offensive and defensive zones, and shots on goal from in front of the net.', 'zone-time'],
    ],
  },
  outlook: {
    summary: 'What projection and luck mean',
    section: 'outlook',
    lead: 'Projection says where the season is headed. Luck says whether the numbers so far are likely to hold.',
    items: [
      ['Proj P, Proj G, Proj A', 'Current totals plus the expected rest of the season. It does not predict injuries or trades.', 'projection'],
      ['P low, P high', 'An 80% range for the final points: about four times in five the finish lands inside it.', 'projection-range'],
      ['xP, P − xP', 'Expected points from the player’s shots and their linemates’ shots, and the gap from actual. Positive is running hot.', 'expected-points'],
      ['Luck z, Luck', 'How unusual the gap is. 1.5 or more is flagged hot or cold, and hot streaks tend to fade.', 'luck-flag'],
    ],
  },
}
