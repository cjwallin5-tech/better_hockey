/** The reset token from a page address's query string ("?token=..."), or '' when there is none. Reading it changes nothing, so it is
 *  safe to run more than once (React runs state initializers twice in development). */
export function tokenFromSearch(search) {
  return new URLSearchParams(search ?? '').get('token') ?? ''
}
