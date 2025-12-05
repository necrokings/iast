// ============================================================================
// Date Picker Component
// ============================================================================

import { ChevronLeft, ChevronRight } from 'lucide-react'
import { getLocalDateString } from './utils'

interface DatePickerProps {
  value: string
  onChange: (date: string) => void
}

export function DatePicker({ value, onChange }: DatePickerProps) {
  const today = getLocalDateString()
  const isToday = value === today

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => {
          const date = new Date(value + 'T12:00:00') // Use noon to avoid timezone issues
          date.setDate(date.getDate() - 1)
          const newLocal = getLocalDateString(date)
          onChange(newLocal)
        }}
        className="cursor-pointer p-1.5 rounded hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      <input
        type="date"
        value={value}
        max={today}
        onChange={(e) => onChange(e.target.value)}
        className="px-2 py-1 text-xs font-medium rounded bg-white dark:bg-zinc-800 border border-gray-200 dark:border-zinc-700"
      />

      <button
        onClick={() => {
          const date = new Date(value + 'T12:00:00') // Use noon to avoid timezone issues
          date.setDate(date.getDate() + 1)
          const nextLocal = getLocalDateString(date)
          if (nextLocal <= today) onChange(nextLocal)
        }}
        disabled={isToday}
        className={`p-1.5 rounded transition-colors ${isToday ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:bg-gray-100 dark:hover:bg-zinc-800'}`}
      >
        <ChevronRight className="w-4 h-4" />
      </button>

      {!isToday && (
        <button
          onClick={() => onChange(getLocalDateString())}
          className="cursor-pointer px-2 py-1 text-xs font-medium rounded bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50"
        >
          Today
        </button>
      )}
    </div>
  )
}
