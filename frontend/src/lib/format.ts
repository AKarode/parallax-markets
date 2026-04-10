const DASH = '\u2014'

export function pct(value: number | null | undefined, decimals = 1): string {
  if (value == null) return DASH
  return `${(value * 100).toFixed(decimals)}%`
}

export function pctRaw(value: number | null | undefined, decimals = 1): string {
  if (value == null) return DASH
  return `${value.toFixed(decimals)}%`
}

export function usd(value: number | null | undefined, decimals = 2): string {
  if (value == null) return DASH
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
}

export function signedUsd(value: number | null | undefined, decimals = 2): string {
  if (value == null) return DASH
  const sign = value >= 0 ? '+' : ''
  return `${sign}$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}`
}

export function signedPct(value: number | null | undefined, decimals = 1): string {
  if (value == null) return DASH
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)}%`
}

export function edge(value: number | null | undefined): string {
  if (value == null) return DASH
  const pctValue = value * 100
  const sign = pctValue >= 0 ? '+' : ''
  return `${sign}${pctValue.toFixed(1)}%`
}

export function relativeTime(iso: string | null | undefined): string {
  if (iso == null) return DASH
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diffMs = now - then
  if (diffMs < 0) return 'just now'
  const seconds = Math.floor(diffMs / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function shortDate(iso: string | null | undefined): string {
  if (iso == null) return DASH
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

export function fraction(correct: number | null | undefined, total: number | null | undefined): string {
  if (correct == null || total == null) return DASH
  const pctValue = total > 0 ? Math.round((correct / total) * 100) : 0
  return `${correct}/${total} (${pctValue}%)`
}
