// Which roster the Fantasy page and the star buttons work on: your roster in the active league once it has its own, otherwise
// your personal roster. Pure, so it can be tested; roster.js is the hook around it.
//   { kind: 'loading' }   signed in and the leagues have not arrived yet (nothing should be changed meanwhile)
//   { kind: 'league', id, name, players }
//   { kind: 'personal', needsStart, leagueName }   needsStart: a league is active but its team still shows the personal roster
export function rosterSource({ signedIn, status, active }) {
  if (signedIn && status !== 'ready' && status !== 'error') return { kind: 'loading' }
  const mine = signedIn ? active?.teams?.find((t) => t.mine) ?? null : null
  if (active && mine?.own_roster) return { kind: 'league', id: active.id, name: active.name, players: mine.players }
  return { kind: 'personal', needsStart: !!(active && mine), leagueName: active?.name ?? null }
}
