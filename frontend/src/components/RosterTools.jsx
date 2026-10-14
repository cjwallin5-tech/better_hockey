import { useRef, useState } from 'react'
import { downloadText } from '../csv.js'
import { decodeShare, encodeShare, exportBackup, parseBackup } from '../fantasy.js'

/** Back up, restore and share the roster + scoring (the data only lives in this browser). */
export default function RosterTools({ players = [], scoring, onLoad, shared, only }) {
  const file = useRef(null)
  const [msg, setMsg] = useState('')

  const copyLink = async () => {
    const url = `${window.location.origin}/fantasy?roster=${encodeShare(players, scoring)}`
    try {
      await navigator.clipboard.writeText(url)
      setMsg('Link copied.')
    } catch {
      setMsg(url) // clipboard blocked: show it so it can be copied by hand
    }
  }

  const onFile = async (e) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    const parsed = parseBackup(await f.text())
    if (!parsed) return setMsg("That file isn't a roster backup.")
    onLoad(parsed)
    setMsg(`Loaded ${parsed.players.length} players.`)
  }

  const sharedRoster = shared ? decodeShare(shared) : null

  return (
    <div className="roster-tools">
      {only !== 'buttons' && shared && (
        <p className="notice">
          {sharedRoster
            ? <>Someone shared a roster of {sharedRoster.players.length} players with you. <button onClick={() => { onLoad(sharedRoster); setMsg('Loaded the shared roster.') }}>Load it (replaces your roster)</button></>
            : "That share link couldn't be read."}
        </p>
      )}
      {only === 'banner' ? null : <>
      {players.length > 0 && <button onClick={copyLink}>Copy share link</button>}
      {players.length > 0 && <button onClick={() => downloadText('fantasy-roster.json', exportBackup(players, scoring), 'application/json')}>Download backup</button>}
      <button onClick={() => file.current?.click()}>Restore from backup…</button>
      <input ref={file} type="file" accept="application/json,.json" hidden onChange={onFile} />
      </>}
      {msg && <span className="muted" role="status"> {msg}</span>}
    </div>
  )
}
