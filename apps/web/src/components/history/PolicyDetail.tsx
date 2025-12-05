// ============================================================================
// Policy Detail Component
// ============================================================================

import { Breadcrumb } from './Breadcrumb'
import { StatusIcon } from './StatusIcon'
import { STATUS_COLORS, type ExecutionRecord, type PolicyRecord } from './types'

interface PolicyDetailProps {
  policy: PolicyRecord
  execution: ExecutionRecord
  onBack: () => void
}

export function PolicyDetail({ policy, execution, onBack }: PolicyDetailProps) {
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-zinc-800">
        <Breadcrumb items={[
          { label: 'Executions', onClick: onBack },
          { label: execution.ast_name, onClick: onBack },
          { label: policy.policy_number }
        ]} />
        
        <div className="mt-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold font-mono text-gray-900 dark:text-zinc-100">
            {policy.policy_number}
          </h2>
          <span className={`px-2.5 py-1 text-xs font-medium rounded-full flex items-center gap-1 ${STATUS_COLORS[policy.status]}`}>
            <StatusIcon status={policy.status} /> {policy.status}
          </span>
        </div>
      </div>
      
      {/* Content */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {/* Stats */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
            <div className="text-xs text-gray-500 dark:text-zinc-500 mb-1">Duration</div>
            <div className="text-lg font-semibold text-gray-900 dark:text-zinc-100">
              {(policy.duration_ms / 1000).toFixed(2)}s
            </div>
          </div>
          <div className="p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
            <div className="text-xs text-gray-500 dark:text-zinc-500 mb-1">Status</div>
            <div className={`text-lg font-semibold ${
              policy.status === 'success' ? 'text-emerald-600 dark:text-emerald-400' :
              policy.status === 'failed' ? 'text-red-600 dark:text-red-400' :
              'text-yellow-600 dark:text-yellow-400'
            }`}>
              {policy.status.charAt(0).toUpperCase() + policy.status.slice(1)}
            </div>
          </div>
        </div>
        
        {/* Timestamps */}
        <div className="p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 dark:text-zinc-500">Started</span>
            <span className="text-gray-900 dark:text-zinc-100 font-mono text-xs">
              {new Date(policy.started_at).toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-500 dark:text-zinc-500">Completed</span>
            <span className="text-gray-900 dark:text-zinc-100 font-mono text-xs">
              {new Date(policy.completed_at).toLocaleString()}
            </span>
          </div>
        </div>
        
        {/* Error */}
        {policy.error && (
          <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
            <div className="text-xs font-medium text-red-700 dark:text-red-400 mb-2">Error</div>
            <pre className="text-sm text-red-600 dark:text-red-300 whitespace-pre-wrap font-mono">
              {policy.error}
            </pre>
          </div>
        )}
        
        {/* Error Screen - shown when policy failed and has screen capture */}
        {policy.status === 'failed' && typeof policy.policy_data?.errorScreen === 'string' && (
          <div className="p-3 rounded-lg bg-zinc-900 border border-zinc-700">
            <div className="text-xs font-medium text-zinc-400 mb-2">Screen at Time of Error</div>
            <pre className="text-xs text-green-400 whitespace-pre font-mono overflow-x-auto leading-tight">
              {policy.policy_data.errorScreen}
            </pre>
          </div>
        )}
        
        {/* Policy Data */}
        {policy.policy_data && Object.keys(policy.policy_data).length > 0 && (
          <div className="p-3 rounded-lg bg-gray-50 dark:bg-zinc-800/50">
            <div className="text-xs font-medium text-gray-700 dark:text-zinc-300 mb-2">Policy Data</div>
            <pre className="text-xs text-gray-600 dark:text-zinc-400 whitespace-pre-wrap font-mono overflow-x-auto">
              {JSON.stringify(policy.policy_data, null, 2)}
            </pre>
          </div>
        )}
        
        {/* Actions - only show for failed policies */}
        {policy.status === 'failed' && (
          <div className="flex gap-2 pt-2">
            <button
              className="flex-1 px-3 py-2 text-sm font-medium rounded-lg bg-gray-100 dark:bg-zinc-800 text-gray-700 dark:text-zinc-300 hover:bg-gray-200 dark:hover:bg-zinc-700 transition-colors"
            >
              Re-run Policy
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
