// Places in a ranking, with ties: players level on a value share a place, and each shows a "T" in front of it (T5, T-5th).

/** 1 -> "1st", 2 -> "2nd", 11 -> "11th", 22 -> "22nd". */
export function ordinal(n) {
  const v = n % 100
  if (v >= 11 && v <= 13) return `${n}th`
  return `${n}${{ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th'}`
}

/** "5th", or "T-5th" for a rank shared with another player. `r` is { rank, tied } as the API sends it. */
export const placeLabel = (r) => `${r.tied ? 'T-' : ''}${ordinal(r.rank)}`

const same = (a, b) => typeof a === 'number' && typeof b === 'number' && Math.abs(a - b) < 1e-9

/**
 * The place of each row of a list already sorted by `key`: [{ rank, tied }, ...]. Rows with equal values share the place of the first of
 * them (1, 2, 2, 4), and every one of those rows is tied. Rows without a number to compare (a text sort, or a missing value) just
 * count their position and are never tied.
 */
export function placesFor(rows, key) {
  return rows.map((row, i) => {
    const v = row[key]
    if (typeof v !== 'number') return { rank: i + 1, tied: false }
    let first = i
    while (first > 0 && same(rows[first - 1][key], v)) first--
    const nextSame = i + 1 < rows.length && same(rows[i + 1][key], v)
    return { rank: first + 1, tied: first < i || nextSame }
  })
}
