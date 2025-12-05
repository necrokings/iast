// ============================================================================
// Index Route - Terminal Page
// ============================================================================

import { createFileRoute } from '@tanstack/react-router'
import { useCallback, useEffect, useState } from 'react'
import SessionSelector from '../components/SessionSelector'
import { getStoredSessionId, setStoredSessionId } from '../utils/storage'
import { generateSessionId } from '@terminal/shared'
import { useAST } from '../hooks/useAST'
import { Terminal } from '../components/Terminal'
import { ASTPanel } from '../ast'
import type { ASTStatusMeta, ASTProgressMeta, ASTItemResultMeta } from '@terminal/shared'
import type { ASTItemStatus } from '../ast/types'

export const Route = createFileRoute('/')({
  component: TerminalPage,
})

interface TerminalApi {
  runAST: (astName: string, params?: Record<string, unknown>) => void
}

function TerminalPage() {
  const { setRunCallback, handleASTComplete, handleASTProgress, handleASTItemResult, handleASTPaused, reset: resetAST } = useAST()

  // Reset AST state when Terminal page mounts (in case user navigated back from History
  // where an AST completed without this page knowing)
  useEffect(() => {
    resetAST()
  }, [resetAST])

  const handleTerminalReady = useCallback(
    (api: TerminalApi) => {
      setRunCallback(api.runAST)
    },
    [setRunCallback]
  )

  const handleASTStatus = useCallback(
    (status: ASTStatusMeta) => {
      const mappedStatus = status.status === 'pending' ? 'running' : status.status
      handleASTComplete({
        status: mappedStatus,
        message: status.message,
        error: status.error,
        duration: status.duration,
        data: status.data,
      })
    },
    [handleASTComplete]
  )

  const handleASTProgressUpdate = useCallback(
    (progress: ASTProgressMeta) => {
      handleASTProgress({
        current: progress.current,
        total: progress.total,
        currentItem: progress.currentItem,
        itemStatus: progress.itemStatus as ASTItemStatus | undefined,
        message: progress.message,
        percentage: progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0,
      })
    },
    [handleASTProgress]
  )

  const handleASTItemResultUpdate = useCallback(
    (itemResult: ASTItemResultMeta) => {
      handleASTItemResult({
        itemId: itemResult.itemId,
        status: itemResult.status as ASTItemStatus,
        durationMs: itemResult.durationMs,
        error: itemResult.error,
        data: itemResult.data,
      })
    },
    [handleASTItemResult]
  )

  const [sessionId, setSessionId] = useState<string>(() => {
    const stored = getStoredSessionId()
    if (stored) return stored
    const gen = generateSessionId()
    try {
      setStoredSessionId(gen)
    } catch {
      // ignore
    }
    return gen
  })

  return (
    <main className="flex-1 overflow-auto flex flex-col p-4 gap-4 bg-white dark:bg-zinc-950">
      <div className="flex items-center justify-between">
        <SessionSelector
          value={sessionId}
          onChange={(id) => {
            setStoredSessionId(id)
            setSessionId(id)
          }}
        />
      </div>

      <div className="flex-1 flex gap-4">
        <Terminal
          key={sessionId}
          sessionId={sessionId}
          autoConnect={true}
          onReady={handleTerminalReady}
          onASTStatus={handleASTStatus}
          onASTProgress={handleASTProgressUpdate}
          onASTItemResult={handleASTItemResultUpdate}
          onASTPaused={handleASTPaused}
        />

        {/* Side panel for AST controls */}
        <div className="w-[400px] flex-shrink-0">
          <ASTPanel />
        </div>
      </div>
    </main>
  )
}