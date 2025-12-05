// ============================================================================
// History Route - AST Execution History (Side-by-Side Layout)
// ============================================================================

import { createFileRoute } from '@tanstack/react-router'
import { useState, useEffect, useCallback, useRef } from 'react'
import { useExecutionObserver } from '../../hooks/useExecutionObserver'
import { useApi } from '../../hooks/useApi'

import {
  type ExecutionStatus,
  type TabFilter,
  type ExecutionRecord,
  type PolicyRecord,
  getLocalDateString,
  getUTCDateString,
  TabBar,
  DatePicker,
  EmptyPanel,
  ExecutionListItem,
  PoliciesList,
  PolicyDetail,
} from '../../components/history'

// ============================================================================
// Route Definition
// ============================================================================

export const Route = createFileRoute('/history')({
  component: HistoryPage,
})

// ============================================================================
// Main Page Component
// ============================================================================

function HistoryPage() {
  // List state
  const [activeTab, setActiveTab] = useState<TabFilter>('all')
  const [selectedDate, setSelectedDate] = useState(() => getLocalDateString())
  const [executions, setExecutions] = useState<ExecutionRecord[]>([])
  const [isLoadingExecutions, setIsLoadingExecutions] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [cursor, setCursor] = useState<string | undefined>()
  const [error, setError] = useState<string | null>(null)

  // Selection state
  const [selectedExecution, setSelectedExecution] = useState<ExecutionRecord | null>(null)
  const [selectedPolicy, setSelectedPolicy] = useState<PolicyRecord | null>(null)

  // Policies state
  const [policies, setPolicies] = useState<PolicyRecord[]>([])
  const [isLoadingPolicies, setIsLoadingPolicies] = useState(false)

  const observerTarget = useRef<HTMLDivElement>(null)

  // Live execution observer - observe both running and paused executions
  const isLive = selectedExecution?.status === 'running' || selectedExecution?.status === 'paused'

  const {
    status: observerStatus,
    progress: liveProgress,
    policyResults: livePolicies,
    astStatus,
    isPaused,
    pause: pauseExecution,
    resume: resumeExecution,
    cancel: cancelExecution,
  } = useExecutionObserver({
    sessionId: selectedExecution?.session_id || null,
    executionId: selectedExecution?.execution_id || '',
    enabled: isLive,
    initialPaused: selectedExecution?.status === 'paused',
  })

  const api = useApi()

  // Update execution status when AST completes via WebSocket
  useEffect(() => {
    if (astStatus && selectedExecution && isLive) {
      const newStatus = astStatus.status as ExecutionStatus
      if (newStatus !== 'running' && newStatus !== selectedExecution.status) {
        // Calculate final counts from livePolicies + fetched policies
        const allPolicies = new Map<string, { status: string }>()
        for (const p of policies) {
          allPolicies.set(p.policy_number, { status: p.status })
        }
        for (const lp of livePolicies) {
          allPolicies.set(lp.itemId, { status: lp.status })
        }

        const successCount = Array.from(allPolicies.values()).filter(p => p.status === 'success').length
        const failedCount = Array.from(allPolicies.values()).filter(p => p.status === 'failed').length
        const skippedCount = Array.from(allPolicies.values()).filter(p => p.status === 'skipped').length

        // Update the selected execution with new status
        setSelectedExecution((prev: ExecutionRecord | null) => prev ? {
          ...prev,
          status: newStatus,
          completed_at: new Date().toISOString(),
          message: astStatus.message,
          success_count: successCount,
          failed_count: failedCount,
          skipped_count: skippedCount,
        } : null)

        // Also update in the executions list
        setExecutions((prev: ExecutionRecord[]) => prev.map(e =>
          e.execution_id === selectedExecution.execution_id
            ? {
              ...e,
              status: newStatus,
              completed_at: new Date().toISOString(),
              message: astStatus.message,
              success_count: successCount,
              failed_count: failedCount,
              skipped_count: skippedCount,
            }
            : e
        ))
      }
    }
  }, [astStatus, selectedExecution, isLive, livePolicies, policies])

  // Update execution status when paused state changes
  const selectedExecutionIdRef = useRef(selectedExecution?.execution_id)
  const selectedExecutionStatusRef = useRef(selectedExecution?.status)
  const isPausedInitializedRef = useRef(false)

  useEffect(() => {
    isPausedInitializedRef.current = false
  }, [selectedExecution?.execution_id])

  if (selectedExecutionIdRef.current !== selectedExecution?.execution_id) {
    selectedExecutionIdRef.current = selectedExecution?.execution_id
    selectedExecutionStatusRef.current = selectedExecution?.status
  }

  useEffect(() => {
    if (!isLive || !selectedExecutionIdRef.current) return

    if (!isPausedInitializedRef.current) {
      isPausedInitializedRef.current = true
      return
    }

    const newStatus = isPaused ? 'paused' : 'running'
    if (newStatus !== selectedExecutionStatusRef.current) {
      const executionId = selectedExecutionIdRef.current
      selectedExecutionStatusRef.current = newStatus
      setSelectedExecution((prev: ExecutionRecord | null) => prev ? { ...prev, status: newStatus } : null)
      setExecutions((prev: ExecutionRecord[]) => prev.map(e =>
        e.execution_id === executionId ? { ...e, status: newStatus } : e
      ))
    }
  }, [isPaused, isLive])

  // Fetch executions (moved to api service)
  const fetchExecutions = useCallback(async (reset = false) => {
    if (isLoadingExecutions) return

    setIsLoadingExecutions(true)
    setError(null)

    try {
      const utcDate = getUTCDateString(new Date(selectedDate + 'T12:00:00'))
      const data = await api.getExecutions(utcDate, activeTab, 30, reset ? undefined : cursor)
      setExecutions((prev: ExecutionRecord[]) => reset ? data.executions : [...prev, ...data.executions])
      setHasMore(data.hasMore)
      setCursor(data.nextCursor)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load history')
    } finally {
      setIsLoadingExecutions(false)
    }
  }, [selectedDate, activeTab, cursor, isLoadingExecutions, api])

  // Fetch policies for selected execution (via api service)
  const fetchPolicies = useCallback(async (executionId: string) => {
    setIsLoadingPolicies(true)
    setPolicies([])

    try {
      const data = await api.getPolicies(executionId)
      setPolicies(data.policies)
    } catch (err) {
      console.error('Failed to fetch policies:', err)
    } finally {
      setIsLoadingPolicies(false)
    }
  }, [api])

  // Reset and fetch when date or tab changes
  useEffect(() => {
    setExecutions([])
    setCursor(undefined)
    setHasMore(false)
    setSelectedExecution(null)
    setSelectedPolicy(null)
    void fetchExecutions(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDate, activeTab])

  // Fetch policies when execution is selected
  const selectedExecutionId = selectedExecution?.execution_id
  useEffect(() => {
    if (selectedExecutionId) {
      setSelectedPolicy(null)
      void fetchPolicies(selectedExecutionId)
    }
  }, [selectedExecutionId, fetchPolicies])

  // Infinite scroll observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && hasMore && !isLoadingExecutions) {
          void fetchExecutions()
        }
      },
      { threshold: 0.1 }
    )

    if (observerTarget.current) observer.observe(observerTarget.current)
    return () => observer.disconnect()
  }, [hasMore, isLoadingExecutions, fetchExecutions])

  // Filter executions
  const filteredExecutions = activeTab === 'all'
    ? executions
    : executions.filter(e => e.status === activeTab)

  const handleSelectExecution = (execution: ExecutionRecord) => {
    setSelectedExecution(execution)
    setSelectedPolicy(null)
  }

  const handleBackToList = () => {
    setSelectedExecution(null)
    setSelectedPolicy(null)
    setPolicies([])
  }

  const handleBackToPolicies = () => {
    setSelectedPolicy(null)
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Panel 1: Executions List */}
      <div className="w-[480px] flex-shrink-0 bg-white dark:bg-zinc-900 border-r border-gray-200 dark:border-zinc-800 flex flex-col">
        {/* Controls */}
        <div className="p-3 border-b border-gray-200 dark:border-zinc-800 space-y-3">
          <div className="flex items-center justify-between">
            <h1 className="text-sm font-semibold text-gray-900 dark:text-zinc-100">History</h1>
            <DatePicker value={selectedDate} onChange={setSelectedDate} />
          </div>
          <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
        </div>

        {/* List */}
        <div className="flex-1 overflow-auto p-3 space-y-2">
          {error && (
            <div className="p-2 rounded bg-red-50 dark:bg-red-900/20 text-xs text-red-700 dark:text-red-400">
              {error}
            </div>
          )}

          {filteredExecutions.map((execution) => (
            <ExecutionListItem
              key={execution.execution_id}
              execution={execution}
              isSelected={selectedExecution?.execution_id === execution.execution_id}
              onClick={() => handleSelectExecution(execution)}
            />
          ))}

          <div ref={observerTarget} className="h-2" />

          {isLoadingExecutions && (
            <div className="flex justify-center py-4">
              <div className="w-5 h-5 border-2 border-gray-200 dark:border-zinc-700 border-t-blue-500 rounded-full animate-spin" />
            </div>
          )}

          {!isLoadingExecutions && filteredExecutions.length === 0 && (
            <EmptyPanel message="No executions found" />
          )}
        </div>
      </div>

      {/* Panel 2: Policies List */}
      <div className="w-[480px] flex-shrink-0 bg-gray-50 dark:bg-zinc-900/50 border-r border-gray-200 dark:border-zinc-800">
        {selectedExecution ? (
          <PoliciesList
            execution={selectedExecution}
            policies={policies}
            livePolicies={livePolicies}
            isLoading={isLoadingPolicies}
            selectedPolicy={selectedPolicy}
            onSelectPolicy={setSelectedPolicy}
            onBack={handleBackToList}
            isLive={isLive}
            liveProgress={liveProgress}
            observerStatus={observerStatus}
            isPaused={isPaused}
            onPause={pauseExecution}
            onResume={resumeExecution}
            onCancel={cancelExecution}
          />
        ) : (
          <EmptyPanel message="Select an execution to view policies" />
        )}
      </div>

      {/* Panel 3: Policy Detail */}
      <div className="flex-1 bg-white dark:bg-zinc-900">
        {selectedPolicy && selectedExecution ? (
          <PolicyDetail
            policy={selectedPolicy}
            execution={selectedExecution}
            onBack={handleBackToPolicies}
          />
        ) : selectedExecution ? (
          <EmptyPanel message="Select a policy to view details" />
        ) : (
          <EmptyPanel message="Select an execution to get started" />
        )}
      </div>
    </div>
  )
}
