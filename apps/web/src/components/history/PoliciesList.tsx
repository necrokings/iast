// ============================================================================
// Policies List Component
// ============================================================================

import { useMemo } from 'react'
import { Check, X, Circle, Pause } from 'lucide-react'
import { Breadcrumb } from './Breadcrumb'
import { StatusIcon } from './StatusIcon'
import { Tooltip } from '../ui'
import { STATUS_COLORS, type ExecutionRecord, type PolicyRecord } from './types'

interface PoliciesListProps {
  execution: ExecutionRecord
  policies: PolicyRecord[]
  livePolicies: Array<{ itemId: string; status: string; durationMs?: number; error?: string; data?: Record<string, unknown> }>
  isLoading: boolean
  selectedPolicy: PolicyRecord | null
  onSelectPolicy: (policy: PolicyRecord) => void
  onBack: () => void
  isLive: boolean
  liveProgress: { current: number; total: number; percent: number; message?: string } | null
  observerStatus: 'disconnected' | 'connecting' | 'connected' | 'error'
  isPaused: boolean
  onPause: () => void
  onResume: () => void
  onCancel: () => void
}

export function PoliciesList({
  execution,
  policies,
  livePolicies,
  isLoading,
  selectedPolicy,
  onSelectPolicy,
  onBack,
  isLive,
  liveProgress,
  observerStatus,
  isPaused,
  onPause,
  onResume,
  onCancel,
}: PoliciesListProps) {
  // Merge fetched policies with live updates
  const allPolicies = useMemo(() => {
    const policyMap = new Map<string, PolicyRecord>()

    for (const p of policies) {
      policyMap.set(p.policy_number, p)
    }

    for (const lp of livePolicies) {
      const existing = policyMap.get(lp.itemId)
      if (existing) {
        policyMap.set(lp.itemId, {
          ...existing,
          status: lp.status as 'success' | 'failed' | 'skipped',
          duration_ms: lp.durationMs || existing.duration_ms,
          error: lp.error || existing.error,
          policy_data: lp.data || existing.policy_data,
        })
      } else {
        policyMap.set(lp.itemId, {
          execution_id: execution.execution_id,
          policy_number: lp.itemId,
          status: lp.status as 'success' | 'failed' | 'skipped',
          duration_ms: lp.durationMs || 0,
          started_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
          error: lp.error,
          policy_data: lp.data,
        })
      }
    }

    return Array.from(policyMap.values())
  }, [policies, livePolicies, execution.execution_id])

  const combinedCounts = useMemo(() => ({
    success: allPolicies.filter(p => p.status === 'success').length,
    failed: allPolicies.filter(p => p.status === 'failed').length,
    skipped: allPolicies.filter(p => p.status === 'skipped').length,
  }), [allPolicies])

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-zinc-800">
        <Breadcrumb items={[
          { label: 'Executions', onClick: onBack },
          { label: execution.ast_name }
        ]} />

        <div className="mt-3 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-zinc-100">
              Policies
            </h2>
            <p className="text-xs text-gray-500 dark:text-zinc-500">
              {execution.host_user || 'unknown'} • {new Date(execution.started_at).toLocaleString()}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isLive && (
              <span className={`px-2 py-0.5 text-xs rounded-full flex items-center gap-1 ${observerStatus === 'connected'
                ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400'
                : observerStatus === 'connecting'
                  ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
                  : 'bg-gray-100 dark:bg-zinc-800 text-gray-600 dark:text-zinc-400'
                }`}>
                <span className={`w-2 h-2 rounded-full ${observerStatus === 'connected' ? 'bg-emerald-500' : 'bg-gray-400 dark:bg-zinc-500'}`} />
                {observerStatus === 'connected' ? ' Live' : observerStatus === 'connecting' ? ' Connecting...' : ' Disconnected'}
              </span>
            )}
            <span className={`px-2.5 py-1 text-xs font-medium rounded-full flex items-center gap-1.5 ${STATUS_COLORS[execution.status]}`}>
              <StatusIcon status={execution.status} />
              {execution.status}
            </span>
          </div>
        </div>

        {/* Live Progress Bar */}
        {isLive && (
          <div className="mt-3 space-y-2">
            <div className="flex justify-between text-xs text-gray-500 dark:text-zinc-500">
              <span className="flex items-center gap-1">
                {isPaused && <Pause className="w-3.5 h-3.5" />}
                {isPaused
                  ? 'Paused - Make manual adjustments, then resume'
                  : liveProgress?.message
                    ? liveProgress.message.replace(/^Policy \d+\/\d+:\s*/, '')
                    : (observerStatus === 'connecting' ? 'Connecting to session...' : 'Waiting for updates...')
                }
              </span>
              <span>{liveProgress ? `${allPolicies.length}/${liveProgress.total}` : `${combinedCounts.success + combinedCounts.failed + combinedCounts.skipped} processed`}</span>
            </div>
            <div className="h-1.5 bg-gray-200 dark:bg-zinc-700 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${isPaused ? 'bg-amber-500' : 'bg-blue-500'}`}
                style={{ width: `${liveProgress ? (allPolicies.length / liveProgress.total) * 100 : 0}%` }}
              />
            </div>

            {/* Control Buttons */}
            <div className="flex items-center gap-2 pt-1">
              {isPaused ? (
                <button
                  type="button"
                  onClick={onResume}
                  className="cursor-pointer flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-200 dark:hover:bg-emerald-900/50 transition-colors"
                >
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                  </svg>
                  Resume
                </button>
              ) : (
                <Tooltip content="Pause after current item completes or fails" position="bottom">
                  <button
                    type="button"
                    onClick={onPause}
                    className="cursor-pointer flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-colors"
                  >
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M5.75 3a.75.75 0 00-.75.75v12.5c0 .414.336.75.75.75h1.5a.75.75 0 00.75-.75V3.75A.75.75 0 007.25 3h-1.5zM12.75 3a.75.75 0 00-.75.75v12.5c0 .414.336.75.75.75h1.5a.75.75 0 00.75-.75V3.75a.75.75 0 00-.75-.75h-1.5z" />
                    </svg>
                    Pause
                  </button>
                </Tooltip>
              )}
              <Tooltip content="Stop after current item completes or fails" position="bottom">
                <button
                  type="button"
                  onClick={onCancel}
                  className="cursor-pointer flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors"
                >
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                  </svg>
                  Stop
                </button>
              </Tooltip>
            </div>
          </div>
        )}

        {/* Stats */}
        <div className="mt-3 flex items-center gap-4 text-xs">
          <span className="text-gray-600 dark:text-zinc-400">
            {allPolicies.length}/{execution.policy_count || '?'} policies
          </span>
          {isLive ? (
            <>
              <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5"><Check className="w-3 h-3" /> {combinedCounts.success}</span>
              {combinedCounts.failed > 0 && (
                <span className="text-red-600 dark:text-red-400 flex items-center gap-0.5"><X className="w-3 h-3" /> {combinedCounts.failed}</span>
              )}
              {combinedCounts.skipped > 0 && (
                <span className="text-yellow-600 dark:text-yellow-400 flex items-center gap-0.5"><Circle className="w-3 h-3" /> {combinedCounts.skipped}</span>
              )}
            </>
          ) : (
            <>
              {execution.success_count !== undefined && (
                <span className="text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5"><Check className="w-3 h-3" /> {execution.success_count}</span>
              )}
              {execution.failed_count !== undefined && execution.failed_count > 0 && (
                <span className="text-red-600 dark:text-red-400 flex items-center gap-0.5"><X className="w-3 h-3" /> {execution.failed_count}</span>
              )}
              {execution.skipped_count !== undefined && execution.skipped_count > 0 && (
                <span className="text-yellow-600 dark:text-yellow-400 flex items-center gap-0.5"><Circle className="w-3 h-3" /> {execution.skipped_count}</span>
              )}
            </>
          )}
        </div>
      </div>

      {/* Policies List */}
      <div className="flex-1 overflow-auto p-3 space-y-2">
        {isLoading && allPolicies.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-gray-200 dark:border-zinc-700 border-t-blue-500 rounded-full animate-spin" />
          </div>
        ) : allPolicies.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-zinc-500 text-sm">
            {isLive ? 'Waiting for policies...' : 'No policies found'}
          </div>
        ) : (
          allPolicies.map((policy) => (
            <button
              key={policy.policy_number}
              onClick={() => onSelectPolicy(policy)}
              className={`
                cursor-pointer w-full text-left p-3 rounded-lg transition-all duration-150 border
                ${selectedPolicy?.policy_number === policy.policy_number
                  ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800 ring-1 ring-blue-300 dark:ring-blue-700'
                  : 'bg-white dark:bg-zinc-900 hover:bg-gray-50 dark:hover:bg-zinc-800 border-gray-200 dark:border-zinc-800'
                }
              `}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-sm text-gray-900 dark:text-zinc-100">
                  {policy.policy_number}
                </span>
                <span className={`px-2 py-0.5 text-xs font-medium rounded-full flex items-center gap-1 ${STATUS_COLORS[policy.status]}`}>
                  <StatusIcon status={policy.status} /> {policy.status}
                </span>
              </div>
              <div className="mt-1 flex items-center gap-3 text-xs text-gray-500 dark:text-zinc-500">
                <span>{(policy.duration_ms / 1000).toFixed(1)}s</span>
                {policy.error && <span className="text-red-500 truncate max-w-[200px]">{policy.error}</span>}
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
