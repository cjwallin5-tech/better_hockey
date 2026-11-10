/** True when a prospect's season rows (from /api/prospects/{id}) include a regular-season NHL year with a game played. */
export const reachedNhl = (seasons) => (seasons ?? []).some((s) => s.league === 'NHL' && s.game_type === 2 && (s.games ?? 0) > 0)
