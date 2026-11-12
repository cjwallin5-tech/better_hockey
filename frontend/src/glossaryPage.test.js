import test from 'node:test'
import assert from 'node:assert/strict'
import { GROUPS } from './glossaryPage.js'
import { TERM_LIST } from './glossary.js'

test('every glossary entry has an id, a name and a meaning, and ids are unique', () => {
  const ids = GROUPS.flatMap((g) => g.terms.map((t) => t.id))
  assert.equal(new Set(ids).size, ids.length)
  for (const g of GROUPS) for (const t of g.terms) assert.ok(t.id && t.name && t.what && t.abbr, `${g.id}/${t.id}`)
  const sections = GROUPS.map((g) => g.id)
  assert.equal(new Set([...ids, ...sections]).size, ids.length + sections.length) // no section shares an id with a term
})

test('the A to Z list covers every label and is sorted', () => {
  assert.ok(TERM_LIST.length > 100)
  const labels = TERM_LIST.map(([k]) => k)
  assert.deepEqual(labels, [...labels].sort((a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })))
})

test('the possession guide links to terms that exist', async () => {
  const { readFileSync } = await import('node:fs')
  const src = readFileSync(new URL('./components/PossessionGuide.jsx', import.meta.url), 'utf8')
  const ids = new Set(GROUPS.flatMap((g) => g.terms.map((t) => t.id)))
  for (const [, id] of src.matchAll(/\/glossary#([a-z-]+)/g)) assert.ok(ids.has(id), id)
})

test('a header label links to its glossary entry, or to a search when it has none', async () => {
  const { glossaryLink, baseLabel } = await import('./glossaryPage.js')
  assert.equal(glossaryLink('CF%'), '/glossary#corsi')
  assert.equal(glossaryLink('CF% Rel'), '/glossary#relative')
  assert.equal(glossaryLink('PDO'), '/glossary#pdo')
  assert.equal(glossaryLink('L10 CF% vs season'), '/glossary#corsi')
  assert.equal(glossaryLink('Pace (84)'), '/glossary#pace')
  assert.equal(glossaryLink('GP'), '/glossary?q=GP')
  assert.equal(baseLabel('P ▼'), 'P')
})
