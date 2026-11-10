import fs from 'node:fs'
import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { isPage, withTags } from './src/shareTags.js'

// In production (`vite preview` on Railway) /api is proxied to the backend service via API_URL.
const api = globalThis.process?.env.API_URL || 'http://localhost:8000'

// Link previews. Chat apps and social networks fetch a page without running JavaScript, so a single-page app would show the same
// title and picture for every address. For each page we ask the API (backend/previews.py) for that page's <head> tags (title,
// description, Open Graph and Twitter card) and put them into index.html. If the API is slow or down the page is served unchanged.
const headTags = async (url) => {
  try {
    const r = await fetch(`${api}/api/share/head?url=${encodeURIComponent(url)}`, { signal: AbortSignal.timeout(2500) })
    return r.ok ? await r.text() : null
  } catch {
    return null
  }
}

function sharePreviews() {
  return {
    name: 'share-previews',
    apply: 'serve', // the dev server and `vite preview`, not the production build
    transformIndexHtml: {
      order: 'pre',
      async handler(html, ctx) {
        return withTags(html, await headTags(ctx.originalUrl ?? ctx.path ?? '/'))
      },
    },
    configurePreviewServer(server) {
      const file = path.resolve(server.config.root, server.config.build.outDir, 'index.html')
      server.middlewares.use(async (req, res, next) => {
        if (!isPage(req)) return next()
        const tags = await headTags(req.url)
        if (!tags || !fs.existsSync(file)) return next() // nothing to add: serve the page as usual
        res.setHeader('content-type', 'text/html; charset=utf-8')
        res.setHeader('cache-control', 'no-cache')
        res.end(withTags(fs.readFileSync(file, 'utf8'), tags))
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), sharePreviews()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
  preview: { host: '0.0.0.0', allowedHosts: true, proxy: { '/api': { target: api, changeOrigin: true } } },
})
