// One bio request per player (the career endpoint, cached on the server), shared by everything on a player page that needs it.
const cache = new Map()

/** Promise of the player's bio ({ headshot, birth_country, ... }), or null when it can't be loaded. */
export function fetchBio(id) {
  if (!cache.has(id)) {
    cache.set(id, fetch(`/api/players/${id}/career`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.bio ?? null)
      .catch(() => { cache.delete(id); return null }))
  }
  return cache.get(id)
}
