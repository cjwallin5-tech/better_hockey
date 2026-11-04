// A plain-language introduction to the Luck & regression page: what the numbers are, why luck matters, and what to do with it.

const SKATER_STEPS = [
  {
    title: 'What the shots say',
    body: 'Every shot has a chance of going in, based on where it was taken from and what kind of shot it was. Add those chances up and you get expected goals (xG): the goals an average shooter would have scored from the same shots.',
  },
  {
    title: 'Compare it to what happened',
    body: 'A player with 10 goals from shots worth 6 xG is 4 goals above expectation. Early in a season a gap like that is mostly luck, not skill. Well above is "running hot", well below is "running cold".',
  },
  {
    title: 'What to expect next',
    body: 'Luck evens out over time, which is what regression means. Hot players usually cool off and cold players usually bounce back. Real skill does not fade, which is why the default compares each player with their own past seasons.',
  },
]

const GOALIE_STEPS = [
  {
    title: 'What the shots say',
    body: 'Every shot a goalie faces has a chance of going in, based on where it came from and what kind of shot it was. Add those chances up and you get expected goals against (xGA): the goals an average goalie would have allowed.',
  },
  {
    title: 'Compare it to what happened',
    body: 'A goalie who allowed 20 goals on shots worth 26 xGA saved 6 more than expected. That gap is called goals saved above expected (GSAx). Early in a season it is mostly luck. Well above is "saving more than expected", well below is "saving less".',
  },
  {
    title: 'What to expect next',
    body: 'Luck evens out over time, which is what regression means. Hot streaks tend to fade and cold ones tend to recover. A goalie\'s results repeat less from year to year than a skater\'s, so treat a big gap with extra caution.',
  },
]

const SKATER_TERMS = [
  ['xG', 'Expected goals: what an average shooter would score from the same shots, using our own shot model.'],
  ['G − xG', 'Goals minus xG. Positive means scoring more than the shots predict.'],
  ['Z', 'How unusual the gap is, measured in standard deviations of normal chance. Past 1.5 is flagged; past 2 is a real outlier for the sample so far.'],
  ['xPts and Pts luck', 'Points are goals plus assists. xPts is what the shots and on-ice results predict, and Pts luck is points minus xPts. The assist part is a rough estimate: when teammates score more or less than their shots predict while this player is on the ice, they pick up assists at their usual rate. We do not track who assisted each shot, and power-play assists are left out.'],
  ['Compare to', 'An average shooter: elite finishers show as hot even when it is just skill. Their own history: a player who has beaten xG for years is measured against that higher bar, so good finishers stop looking lucky for being good.'],
  ['Past G − xG', 'Goals minus xG over earlier seasons we have shots for. Positive means a history of finishing above the shots.'],
  ['Sh% and xSh%', 'Shooting percentage, and the percentage an average shooter would have from the same shots.'],
  ['Pace (G / xG)', 'Goals and xG stretched over a full season at the current rate.'],
  ['On-ice luck', '5v5 goals for minus against while the player is on the ice, compared with the expected goals for minus against.'],
  ['PDO', 'On-ice shooting % plus save % at 5v5. 1.000 is average, and a number far above it tends to drift back.'],
]

const GOALIE_TERMS = [
  ['xGA', 'Expected goals against: what an average goalie would allow on the same shots.'],
  ['GSAx', 'Goals saved above expected: xGA minus the goals actually allowed. Positive is better.'],
  ['Per 100 shots', 'GSAx for every 100 shots faced, so goalies with different workloads can be compared.'],
  ['Z', 'How unusual the gap is, measured in standard deviations of normal chance. Past 1.5 is flagged; past 2 is a real outlier for the sample so far.'],
  ['Sv% and xSv%', 'Save percentage, and the save percentage an average goalie would have on the same shots.'],
]

export default function LuckGuide({ goalie = false }) {
  const steps = goalie ? GOALIE_STEPS : SKATER_STEPS
  const terms = goalie ? GOALIE_TERMS : SKATER_TERMS
  return (
    <section className="luck-guide" aria-label="How to read this page">
      <div className="eyebrow">How to read this</div>
      <ol className="luck-steps">
        {steps.map((s, i) => (
          <li key={s.title}>
            <span className="luck-num" aria-hidden="true">{i + 1}</span>
            <strong>{s.title}</strong>
            <p>{s.body}</p>
          </li>
        ))}
      </ol>
      <p className="luck-use">
        <strong>How to use it.</strong>{' '}
        {goalie
          ? 'A goalie running hot is a risky time to pay full price, and one running cold may be worth a look before they recover. "Steady" means nothing to act on.'
          : 'A player running hot is a good time to sell or to avoid overpaying. A player running cold is worth picking up or buying before they bounce back. "Steady" means nothing to act on.'}{' '}
        These are hints, not verdicts: our shot model does not know who is shooting, and a few games can swing everything early on.
      </p>
      <details className="luck-terms">
        <summary>What the columns and terms mean</summary>
        <dl>
          {terms.map(([term, def]) => (
            <div key={term}>
              <dt>{term}</dt>
              <dd>{def}</dd>
            </div>
          ))}
        </dl>
      </details>
    </section>
  )
}
