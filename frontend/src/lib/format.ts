export function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value))
}

export function formatDateTime(value: string | null): string {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function timeAgo(value: string | null): string {
  if (!value) return 'Date unknown'
  const days = Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000)
  if (days <= 0) return 'Today'
  if (days === 1) return '1 day ago'
  if (days < 60) return `${days} days ago`
  return formatDate(value)
}

// Listing URLs come from external sources: only ever render http(s) links.
export function safeHref(url: string): string {
  return /^https?:\/\//i.test(url) ? url : '#'
}