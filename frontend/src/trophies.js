// Award names on player pages and in the trophy list differ in quotes and case, so they are matched on letters and digits only.
export const trophyKey = (name) => (name ?? '').toLowerCase().replace(/[^a-z0-9]/g, '')

// The site's own award pages shorten a few trophy names ("Norris Trophy"), so they are matched to the NHL's full names here.
const ALIASES = {
  mauricerichardtrophy: 'mauricerocketrichardtrophy',
  norristrophy: 'jamesnorrismemorialtrophy',
  caldertrophy: 'caldermemorialtrophy',
  harttrophy: 'hartmemorialtrophy',
  selketrophy: 'frankjselketrophy',
}
export const trophyMatchKey = (name) => { const k = trophyKey(name); return ALIASES[k] ?? k }

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
