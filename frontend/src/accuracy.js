// Plain-English readings of the accuracy numbers from /api/accuracy (see backend/accuracy.py).

/** 'better', 'worse' or 'unclear' for a paired difference in a loss (lower is better) from the first model minus the second. */
export function verdictFor(diff) {
  if (!diff) return 'unclear'
  if (diff.high < 0) return 'better'
  if (diff.low > 0) return 'worse'
  return 'unclear'
}

/** The bins where what was said and what happened disagree by `gap` or more over at least `minN` predictions. */
export function miscalibrated(bins, { minN = 20, gap = 0.1 } = {}) {
  return (bins ?? [])
    .filter((b) => b.n >= minN && Math.abs(b.mean_p - b.rate) >= gap)
    .map((b) => ({ ...b, direction: b.mean_p > b.rate ? 'over' : 'under' }))
}

/** One sentence for a miscalibrated bin, e.g. "When it said about 93% (41 games), it happened 78% of the time." */
export function calibrationSentence(b, what = 'it happened') {
  return `When it said about ${Math.round(b.mean_p * 100)}% (${b.n} games), ${what} ${Math.round(b.rate * 100)}% of the time.`
}

/** The label for a bin edge pair as a percent range. */
export const binLabel = (b) => `${Math.round(b.lo * 100)}%${b.hi >= 1 ? '+' : `-${Math.round(b.hi * 100)}%`}`
