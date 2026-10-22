// Award names on player pages and in the trophy list differ in quotes and case, so they are matched on letters and digits only.
export const trophyKey = (name) => (name ?? '').toLowerCase().replace(/[^a-z0-9]/g, '')

// One request for the trophy list, shared by every awards table on the page.
let index = null
/** Promise of {key: trophy id} for every NHL trophy; empty when the list can't be loaded. */
export function trophyIds() {
  if (!index) {
    index = fetch('/api/trophy-index')
      .then((r) => (r.ok ? r.json() : { trophies: [] }))
      .then((d) => Object.fromEntries(d.trophies.map((t) => [t.key, t.id])))
      .catch(() => { index = null; return {} })
  }
  return index
}
