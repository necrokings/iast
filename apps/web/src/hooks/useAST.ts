// ============================================================================
// useAST Hook - Access AST state from Zustand store
// ============================================================================

import { useCallback, useMemo } from 'react';
import { useASTStore, type TabASTState } from '../stores/astStore';
import type { ASTStatus, ASTResult, ASTProgress, ASTItemResult } from '../ast/types';

// ============================================================================
// Return Type (maintains backward compatibility with old context)
// ============================================================================

export interface UseASTReturn {
  /** Currently running AST name, if any */
  runningAST: string | null;
  /** Status of the last/current AST */
  status: ASTStatus;
  /** Result of the last AST execution */
  lastResult: ASTResult | null;
  /** Current progress (for batch operations) */
  progress: ASTProgress | null;
  /** Item results (for batch operations) */
  itemResults: ASTItemResult[];
  /** Callback to run an AST (injected from terminal) */
  runAST: ((astName: string, params?: Record<string, unknown>) => void) | null;
  /** Execute an AST with parameters */
  executeAST: (astName: string, params?: Record<string, unknown>) => void;
  /** Set the run callback (from terminal hook) */
  setRunCallback: (callback: (astName: string, params?: Record<string, unknown>) => void) => void;
  /** Handle AST completion (from status messages) */
  handleASTComplete: (result: ASTResult) => void;
  /** Handle AST progress update */
  handleASTProgress: (progress: ASTProgress) => void;
  /** Handle AST item result */
  handleASTItemResult: (itemResult: ASTItemResult) => void;
  /** Handle AST paused state change */
  handleASTPaused: (isPaused: boolean) => void;
  /** Reset state */
  reset: () => void;
  /** Check if an AST is currently running */
  isRunning: boolean;
  /** Currently selected AST ID in the panel */
  selectedASTId: string | null;
  /** Set selected AST ID */
  setSelectedASTId: (astId: string | null) => void;
  /** Restore AST state from an active execution (e.g., after page refresh) */
  restoreFromExecution: (execution: {
    ast_name: string;
    status: 'running' | 'paused';
    policy_count: number;
    success_count?: number;
    failed_count?: number;
    execution_id: string;
  }) => void;
}

// ============================================================================
// Default state for when no tab is active
// ============================================================================

const defaultTabState: TabASTState = {
  selectedASTId: null,
  runningAST: null,
  status: 'idle',
  lastResult: null,
  progress: null,
  itemResults: [],
  runAST: null,
};

// ============================================================================
// Hook
// ============================================================================

/**
 * Access AST state for the current active tab.
 * 
 * This hook provides the same interface as the old ASTContext-based useAST,
 * but now backed by Zustand for persistence across route navigation.
 * 
 * @param tabId - Optional tab ID. If not provided, uses the active tab ID from the store.
 */
export function useAST(tabId?: string): UseASTReturn {
  // Get the active tab ID from the store if not provided
  const activeTabId = useASTStore((state) => state.activeTabId);
  const effectiveTabId = tabId ?? activeTabId;

  // Get the tab state
  const tabState = useASTStore((state) => 
    effectiveTabId ? state.tabs[effectiveTabId] ?? null : null
  );

  // Get store actions - these are stable references from Zustand
  const storeSetRunCallback = useASTStore((state) => state.setRunCallback);
  const storeExecuteAST = useASTStore((state) => state.executeAST);
  const storeHandleASTComplete = useASTStore((state) => state.handleASTComplete);
  const storeHandleASTProgress = useASTStore((state) => state.handleASTProgress);
  const storeHandleASTItemResult = useASTStore((state) => state.handleASTItemResult);
  const storeHandleASTPaused = useASTStore((state) => state.handleASTPaused);
  const storeReset = useASTStore((state) => state.reset);
  const storeSetSelectedASTId = useASTStore((state) => state.setSelectedASTId);
  const storeRestoreFromExecution = useASTStore((state) => state.restoreFromExecution);

  // Create bound action wrappers that automatically use the effective tab ID
  const setRunCallback = useCallback(
    (callback: (astName: string, params?: Record<string, unknown>) => void) => {
      if (effectiveTabId) {
        storeSetRunCallback(effectiveTabId, callback);
      }
    },
    [effectiveTabId, storeSetRunCallback]
  );

  const executeAST = useCallback(
    (astName: string, params?: Record<string, unknown>) => {
      if (effectiveTabId) {
        storeExecuteAST(effectiveTabId, astName, params);
      } else {
        console.warn('No active tab ID. Cannot execute AST.');
      }
    },
    [effectiveTabId, storeExecuteAST]
  );

  const handleASTComplete = useCallback(
    (result: ASTResult) => {
      if (effectiveTabId) {
        storeHandleASTComplete(effectiveTabId, result);
      }
    },
    [effectiveTabId, storeHandleASTComplete]
  );

  const handleASTProgress = useCallback(
    (progress: ASTProgress) => {
      if (effectiveTabId) {
        storeHandleASTProgress(effectiveTabId, progress);
      }
    },
    [effectiveTabId, storeHandleASTProgress]
  );

  const handleASTItemResult = useCallback(
    (itemResult: ASTItemResult) => {
      if (effectiveTabId) {
        storeHandleASTItemResult(effectiveTabId, itemResult);
      }
    },
    [effectiveTabId, storeHandleASTItemResult]
  );

  const handleASTPaused = useCallback(
    (isPaused: boolean) => {
      if (effectiveTabId) {
        storeHandleASTPaused(effectiveTabId, isPaused);
      }
    },
    [effectiveTabId, storeHandleASTPaused]
  );

  const reset = useCallback(() => {
    if (effectiveTabId) {
      storeReset(effectiveTabId);
    }
  }, [effectiveTabId, storeReset]);

  const setSelectedASTId = useCallback(
    (astId: string | null) => {
      if (effectiveTabId) {
        storeSetSelectedASTId(effectiveTabId, astId);
      }
    },
    [effectiveTabId, storeSetSelectedASTId]
  );

  const restoreFromExecution = useCallback(
    (execution: {
      ast_name: string;
      status: 'running' | 'paused';
      policy_count: number;
      success_count?: number;
      failed_count?: number;
      execution_id: string;
    }) => {
      if (effectiveTabId) {
        storeRestoreFromExecution(effectiveTabId, execution);
      }
    },
    [effectiveTabId, storeRestoreFromExecution]
  );

  // Compute derived values
  const state = tabState ?? defaultTabState;
  const isRunning = state.status === 'running' || state.status === 'paused';

  return useMemo(
    () => ({
      runningAST: state.runningAST,
      status: state.status,
      lastResult: state.lastResult,
      progress: state.progress,
      itemResults: state.itemResults,
      runAST: state.runAST,
      executeAST,
      setRunCallback,
      handleASTComplete,
      handleASTProgress,
      handleASTItemResult,
      handleASTPaused,
      reset,
      isRunning,
      selectedASTId: state.selectedASTId,
      setSelectedASTId,
      restoreFromExecution,
    }),
    [
      state,
      executeAST,
      setRunCallback,
      handleASTComplete,
      handleASTProgress,
      handleASTItemResult,
      handleASTPaused,
      reset,
      isRunning,
      setSelectedASTId,
      restoreFromExecution,
    ]
  );
}
