// Sell-high / buy-low suggestions: who on your roster is running above what their shots support, who elsewhere
// is running below it, and which swaps trade one for the other without giving up value.

/** A swap target may be worth this much less than what you give (in value units) and still be suggested. */
export const SWAP_TOLERANCE = 0.9

const MAX_TARGETS = 3

/**
 * values: Map id -> { value, group, ... } from playerValues / categoryValues.
 * luck: Map id -> { z, flag, enough } (flag 'hot' | 'cold' | 'steady'); players with a small sample are ignored.
 * roster: Set of ids you own.
 * Returns { sell, buy }:
 *   sell: your hot players with positive value, hottest first, each with `targets`: cold players you don't own,
 *         in the same position group, worth at least SWAP_TOLERANCE of the player's value, best value first.
 *   buy:  cold players you don't own with positive value, best value first.
 * Value already pulls a short hot or cold streak toward the player's norm, so a hot player's value is not inflated
 * by all of the streak; the flag says it still may be.
 */
export function tradeIdeas({ values, luck, roster, limit = 8 }) {
  const rows = []
  for (const [id, v] of values) {
    const l = luck.get(id)
    if (!l || !l.enough || (l.flag !== 'hot' && l.flag !== 'cold')) continue
    rows.push({ id, value: v.value, group: v.group, z: l.z, flag: l.flag, owned: roster.has(id) })
  }
  const buy = rows
    .filter((r) => r.flag === 'cold' && !r.owned && r.value > 0)
    .sort((a, b) => b.value - a.value || a.id - b.id)
  const sell = rows
    .filter((r) => r.flag === 'hot' && r.owned && r.value > 0)
    .sort((a, b) => b.z - a.z || a.id - b.id)
    .map((r) => ({
      ...r,
      targets: buy.filter((t) => t.group === r.group && t.value >= r.value * SWAP_TOLERANCE).slice(0, MAX_TARGETS),
    }))
  return { sell: sell.slice(0, limit), buy: buy.slice(0, limit) }
}
