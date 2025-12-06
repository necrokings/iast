// ============================================================================
// AST Store - Zustand store for AST state management
// ============================================================================

import { create } from 'zustand';
import type { ASTStatus, ASTResult, ASTProgress, ASTItemResult } from '../ast/types';

// ============================================================================
// Types
// ============================================================================

export interface TabASTState {
  /** Currently selected AST ID in the panel */
  selectedASTId: string | null;
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
}

interface ASTStore {
  /** State per tab, keyed by tabId */
  tabs: Record<string, TabASTState>;
  /** Currently active tab ID */
  activeTabId: string | null;

  // Tab management
  setActiveTabId: (tabId: string | null) => void;
  initTab: (tabId: string) => void;
  removeTab: (tabId: string) => void;

  // AST selection (persisted per tab)
  setSelectedASTId: (tabId: string, astId: string | null) => void;

  // Run callback management
  setRunCallback: (tabId: string, callback: (astName: string, params?: Record<string, unknown>) => void) => void;

  // AST execution
  executeAST: (tabId: string, astName: string, params?: Record<string, unknown>) => void;

  // Status handlers
  handleASTComplete: (tabId: string, result: ASTResult) => void;
  handleASTProgress: (tabId: string, progress: ASTProgress) => void;
  handleASTItemResult: (tabId: string, itemResult: ASTItemResult) => void;
  handleASTPaused: (tabId: string, isPaused: boolean) => void;

  // Restore state from active execution (e.g., after page refresh)
  restoreFromExecution: (tabId: string, execution: {
    ast_name: string;
    status: 'running' | 'paused';
    policy_count: number;
    success_count?: number;
    failed_count?: number;
    execution_id: string;
  }) => void;

  // Reset
  reset: (tabId: string) => void;
}

// ============================================================================
// Initial State
// ============================================================================

const createInitialTabState = (): TabASTState => ({
  selectedASTId: null,
  runningAST: null,
  status: 'idle',
  lastResult: null,
  progress: null,
  itemResults: [],
  runAST: null,
});

// ============================================================================
// Store
// ============================================================================

export const useASTStore = create<ASTStore>((set, get) => ({
  tabs: {},
  activeTabId: null,

  setActiveTabId: (tabId) => {
    set({ activeTabId: tabId });
  },

  initTab: (tabId) => {
    const { tabs } = get();
    if (!tabs[tabId]) {
      set({
        tabs: {
          ...tabs,
          [tabId]: createInitialTabState(),
        },
      });
    }
  },

  removeTab: (tabId) => {
    const { tabs, activeTabId } = get();
    const { [tabId]: _removed, ...rest } = tabs;
    void _removed; // Silence unused variable warning
    set({
      tabs: rest,
      activeTabId: activeTabId === tabId ? null : activeTabId,
    });
  },

  setSelectedASTId: (tabId, astId) => {
    const { tabs } = get();
    const tabState = tabs[tabId];
    if (tabState) {
      set({
        tabs: {
          ...tabs,
          [tabId]: { ...tabState, selectedASTId: astId },
        },
      });
    }
  },

  setRunCallback: (tabId, callback) => {
    const { tabs } = get();
    const tabState = tabs[tabId] ?? createInitialTabState();
    set({
      tabs: {
        ...tabs,
        [tabId]: { ...tabState, runAST: callback },
      },
    });
  },

  executeAST: (tabId, astName, params) => {
    const { tabs } = get();
    const tabState = tabs[tabId];
    if (tabState?.runAST) {
      set({
        tabs: {
          ...tabs,
          [tabId]: {
            ...tabState,
            runningAST: astName,
            status: 'running',
            lastResult: null,
            progress: null,
            itemResults: [],
          },
        },
      });
      tabState.runAST(astName, params);
    } else {
      console.warn('AST run callback not set. Is terminal connected?');
    }
  },

  handleASTComplete: (tabId, result) => {
    const { tabs } = get();
    const tabState = tabs[tabId];
    if (tabState) {
      set({
        tabs: {
          ...tabs,
          [tabId]: {
            ...tabState,
            runningAST: null,
            status: result.status,
            lastResult: result,
            progress: null,
          },
        },
      });
    }
  },

  handleASTProgress: (tabId, progress) => {
    const { tabs } = get();
    const tabState = tabs[tabId];
    if (tabState) {
      set({
        tabs: {
          ...tabs,
          [tabId]: { ...tabState, progress },
        },
      });
    }
  },

  handleASTItemResult: (tabId, itemResult) => {
    const { tabs } = get();
    const tabState = tabs[tabId];
    if (tabState) {
      set({
        tabs: {
          ...tabs,
          [tabId]: {
            ...tabState,
            itemResults: [...tabState.itemResults, itemResult],
          },
        },
      });
    }
  },

  handleASTPaused: (tabId, isPaused) => {
    const { tabs } = get();
    const tabState = tabs[tabId];
    if (tabState) {
      set({
        tabs: {
          ...tabs,
          [tabId]: {
            ...tabState,
            status: isPaused ? 'paused' : 'running',
          },
        },
      });
    }
  },

  restoreFromExecution: (tabId, execution) => {
    const { tabs } = get();
    const tabState = tabs[tabId] ?? createInitialTabState();
    
    // Calculate progress from execution counts
    const processed = (execution.success_count ?? 0) + (execution.failed_count ?? 0);
    const progress = execution.policy_count > 0 ? {
      current: processed,
      total: execution.policy_count,
      percentage: Math.round((processed / execution.policy_count) * 100),
    } : null;

    set({
      tabs: {
        ...tabs,
        [tabId]: {
          ...tabState,
          runningAST: execution.ast_name,
          status: execution.status,
          progress,
          // Store execution_id in lastResult for reference
          lastResult: null,
          itemResults: [],
        },
      },
    });
  },

  reset: (tabId) => {
    const { tabs } = get();
    const tabState = tabs[tabId];
    if (tabState) {
      set({
        tabs: {
          ...tabs,
          [tabId]: {
            ...tabState,
            runningAST: null,
            status: 'idle',
            lastResult: null,
            progress: null,
            itemResults: [],
          },
        },
      });
    }
  },
}));

// ============================================================================
// Selector Hooks
// ============================================================================

/** Get the state for a specific tab */
export const useTabASTState = (tabId: string): TabASTState | null => {
  return useASTStore((state) => state.tabs[tabId] ?? null);
};

/** Get the active tab ID */
export const useActiveTabId = (): string | null => {
  return useASTStore((state) => state.activeTabId);
};

