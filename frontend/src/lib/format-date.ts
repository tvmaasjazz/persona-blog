export function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

export function formatDateTime(isoDate: string): string {
  return new Date(isoDate).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
