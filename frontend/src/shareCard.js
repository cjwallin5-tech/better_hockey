const W = 1200
const PAD = 48
const ROW = 52
const FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
const COLORS = { bg: '#0f172a', panel: '#1e293b', line: '#334155', text: '#f1f5f9', muted: '#94a3b8', accent: '#38bdf8' }

/** Shrinks text with an ellipsis until it fits `max` pixels. */
function fit(ctx, text, max) {
  if (ctx.measureText(text).width <= max) return text
  let t = text
  while (t.length > 1 && ctx.measureText(`${t}…`).width > max) t = t.slice(0, -1)
  return `${t}…`
}

/**
 * Draws a table as a shareable card and returns the canvas.
 * card: { title, subtitle?, columns: [heading, ...], rows: [{ label, cells: [text, ...], best?: cellIndex }],
 *         footer?: string, verdict?: string }
 * `best` highlights one cell in the row; `verdict` is a one-line takeaway shown under the table.
 */
export function drawCard({ title, subtitle, columns, rows, footer, verdict }) {
  const labelW = 360
  const cellW = (W - PAD * 2 - labelW) / Math.max(1, columns.length)
  const headH = 150
  const verdictH = verdict ? 70 : 0
  const height = headH + ROW * (rows.length + 1) + verdictH + 90
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = height
  const ctx = canvas.getContext('2d')

  ctx.fillStyle = COLORS.bg
  ctx.fillRect(0, 0, W, height)
  ctx.textBaseline = 'middle'

  ctx.fillStyle = COLORS.text
  ctx.font = `700 44px ${FONT}`
  ctx.fillText(fit(ctx, title, W - PAD * 2), PAD, 64)
  if (subtitle) {
    ctx.fillStyle = COLORS.muted
    ctx.font = `400 24px ${FONT}`
    ctx.fillText(fit(ctx, subtitle, W - PAD * 2), PAD, 112)
  }

  let y = headH
  ctx.fillStyle = COLORS.panel
  ctx.fillRect(PAD, y, W - PAD * 2, ROW)
  ctx.fillStyle = COLORS.muted
  ctx.font = `600 22px ${FONT}`
  ctx.textAlign = 'right'
  columns.forEach((c, i) => ctx.fillText(fit(ctx, c, cellW - 20), PAD + labelW + cellW * (i + 1) - 16, y + ROW / 2))

  rows.forEach((row, r) => {
    y += ROW
    if (r % 2 === 1) {
      ctx.fillStyle = COLORS.panel
      ctx.globalAlpha = 0.45
      ctx.fillRect(PAD, y, W - PAD * 2, ROW)
      ctx.globalAlpha = 1
    }
    ctx.textAlign = 'left'
    ctx.fillStyle = COLORS.muted
    ctx.font = `400 24px ${FONT}`
    ctx.fillText(fit(ctx, row.label, labelW - 16), PAD + 16, y + ROW / 2)
    ctx.textAlign = 'right'
    row.cells.forEach((cell, i) => {
      const best = row.best === i
      ctx.fillStyle = best ? COLORS.accent : COLORS.text
      ctx.font = `${best ? 700 : 500} 26px ${FONT}`
      ctx.fillText(fit(ctx, String(cell), cellW - 20), PAD + labelW + cellW * (i + 1) - 16, y + ROW / 2)
    })
  })
  ctx.strokeStyle = COLORS.line
  ctx.lineWidth = 2
  ctx.strokeRect(PAD, headH, W - PAD * 2, ROW * (rows.length + 1))

  if (verdict) {
    ctx.textAlign = 'left'
    ctx.fillStyle = COLORS.text
    ctx.font = `700 28px ${FONT}`
    ctx.fillText(fit(ctx, verdict, W - PAD * 2), PAD, y + ROW + 48)
  }
  if (footer) {
    ctx.textAlign = 'left'
    ctx.fillStyle = COLORS.muted
    ctx.font = `400 20px ${FONT}`
    ctx.fillText(fit(ctx, footer, W - PAD * 2), PAD, height - 36)
  }
  return canvas
}

/** Saves a canvas as a PNG download. */
export function downloadCanvas(canvas, filename) {
  canvas.toBlob((blob) => {
    if (!blob) return
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }, 'image/png')
}
