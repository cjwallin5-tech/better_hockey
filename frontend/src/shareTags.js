// Helpers for the link-preview plugin in vite.config.js (see backend/previews.py), kept here so they can be tested.

/** `html` with its <title> replaced by `tags` (the API's <head> tags, which include their own title); unchanged when there are none. */
export const withTags = (html, tags) => (tags ? html.replace(/<title>[^<]*<\/title>/, () => tags) : html)

/** True for a browser or crawler asking for a page: a GET that accepts HTML and is not an API call, a script or any other file. */
export const isPage = (req) => {
  const url = req.url ?? ''
  return req.method === 'GET' && /text\/html/.test(req.headers?.accept ?? '') &&
    !/^\/(api|assets|@|src|node_modules)\b/.test(url) && !/\.\w+$/.test(url.split('?')[0])
}
