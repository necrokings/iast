// ============================================================================
// History Utility Functions
// ============================================================================

/** Get local date string in YYYY-MM-DD format */
export function getLocalDateString(date: Date = new Date()): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** Get UTC date string in YYYY-MM-DD format */
export function getUTCDateString(date: Date = new Date()): string {
  return date.toISOString().split('T')[0]
}

