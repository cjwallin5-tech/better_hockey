const KINDS = [['skater', 'Skaters'], ['goalie', 'Goalies']]

/** The Skaters / Goalies switch at the top of the Players and All-time pages. `onPick` gets the kind that was chosen. */
export default function KindSwitch({ kind, onPick }) {
  return (
    <div className="tabs players-switch" role="tablist" aria-label="Skaters or goalies">
      {KINDS.map(([id, label]) => (
        <button key={id} role="tab" aria-selected={id === kind} className={id === kind ? 'on' : ''} onClick={() => id !== kind && onPick(id)}>{label}</button>
      ))}
    </div>
  )
}
