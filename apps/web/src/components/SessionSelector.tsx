import { useState, useEffect, useRef } from 'react'
import { generateSessionId } from '@terminal/shared'
import { setStoredSessionId } from '../utils/storage'

const SESSIONS_KEY = 'terminal_sessions'

function readSessions(): string[] {
  try {
    const raw = localStorage.getItem(SESSIONS_KEY)
    if (!raw) return []
    return JSON.parse(raw) as string[]
  } catch {
    return []
  }
}

function writeSessions(list: string[]) {
  try {
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(list))
  } catch {
    console.error('Failed to write sessions to localStorage')
  }
}

export default function SessionSelector({
  value,
  onChange,
}: {
  value?: string
  onChange: (id: string) => void
}) {
  const [sessions, setSessions] = useState<string[]>(() => readSessions())
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const createNew = () => {
    const id = generateSessionId()
    const updated = [id, ...sessions.filter(s => s !== id)]
    setSessions(updated)
    writeSessions(updated)
    setStoredSessionId(id)
    onChange(id)
    setIsOpen(false)
  }

  const select = (id: string) => {
    setStoredSessionId(id)
    onChange(id)
    setIsOpen(false)
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 rounded border bg-white dark:bg-zinc-900 hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors"
      >
        <span className="text-sm">{value || 'Select session'}</span>
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute top-full mt-1 w-full bg-white dark:bg-zinc-900 border rounded shadow-lg z-10 max-h-60 overflow-auto">
          {sessions.map((s) => (
            <button
              key={s}
              onClick={() => select(s)}
              className="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors text-sm"
            >
              {s}
            </button>
          ))}
          <div className="border-t border-gray-200 dark:border-zinc-700">
            <button
              onClick={createNew}
              className="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-zinc-800 transition-colors text-sm text-blue-600 dark:text-blue-400"
            >
              + New Session
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
