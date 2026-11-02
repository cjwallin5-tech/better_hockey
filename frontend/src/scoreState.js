export const STATE_LABEL = {
  trail2: 'Down 2 or more', trail1: 'Down 1', tied: 'Tied', lead1: 'Up 1', lead2: 'Up 2 or more',
}

export const pct1 = (v) => (v == null ? '–' : `${(v * 100).toFixed(1)}%`)
export const signedPts = (v) => (v == null ? '–' : `${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}`)
export const signed = (v, d = 1) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(d)}`)

/** Plain-language read of a clutch z-score: nothing short of 2 standard deviations is more than chance. */
export function clutchVerdict(z) {
  if (z == null) return 'Too few goals to compare.'
  if (z >= 2) return 'Scores more in close, late moments than his own finishing predicts. Rarely more than luck, see the note below.'
  if (z <= -2) return 'Scores less in close, late moments than his own finishing predicts. Rarely more than luck, see the note below.'
  return 'Within chance of his own finishing everywhere else.'
}

/** How far a team's score-adjusted share moved from its raw one, in percentage points (positive = looks better adjusted). */
export const adjustment = (t, key = 'xg') => (t[`${key}_pct_adj`] == null || t[`${key}_pct`] == null ? null : t[`${key}_pct_adj`] - t[`${key}_pct`])
