import test from 'node:test'
import assert from 'node:assert/strict'
import { isPage, withTags } from './shareTags.js'

const html = '<head><title>Faceoff</title><meta charset="utf-8" /></head>'

test('the title is replaced by the tags, which bring their own title', () => {
  const out = withTags(html, '<title>Connor McDavid · Faceoff</title>\n<meta property="og:title" content="x" />')
  assert.ok(out.includes('<title>Connor McDavid · Faceoff</title>'))
  assert.ok(out.includes('og:title'))
  assert.ok(out.includes('<meta charset="utf-8" />'))
  assert.equal(out.match(/<title>/g).length, 1)
})

test('no tags leaves the page exactly as it was', () => {
  assert.equal(withTags(html, null), html)
  assert.equal(withTags(html, ''), html)
})

test('dollar signs in the tags are not treated as replacement patterns', () => {
  const out = withTags(html, "<title>Costs $& and $1 · Faceoff</title>")
  assert.ok(out.includes('Costs $& and $1'))
})

const get = (url, accept = 'text/html,application/xhtml+xml') => ({ method: 'GET', url, headers: { accept } })

test('page addresses are pages', () => {
  for (const u of ['/', '/player/8478402', '/team/EDM', '/compare?ids=1,2', '/reset-password?token=abc', '/alltime/skaters']) {
    assert.equal(isPage(get(u)), true, u)
  }
})

test('the API, assets, source files and other files are not pages', () => {
  for (const u of ['/api/share/head?url=%2F', '/assets/index-abc.js', '/favicon.svg', '/src/main.jsx', '/@vite/client', '/flags/ca.svg', '/trophies/1.png', '/node_modules/x.js']) {
    assert.equal(isPage(get(u)), false, u)
  }
})

test('only GET requests that accept HTML count', () => {
  assert.equal(isPage({ method: 'POST', url: '/player/1', headers: { accept: 'text/html' } }), false)
  assert.equal(isPage(get('/player/1', 'application/json')), false)
  assert.equal(isPage({ method: 'GET', url: '/player/1', headers: {} }), false)
})
