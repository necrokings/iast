// ============================================================================
// Index Route - Terminal Page
// ============================================================================

import { createFileRoute } from '@tanstack/react-router';
import { useCallback, useEffect, useState } from 'react';
import { getStoredSessionId, setStoredSessionId, removeStoredSessionId } from '../utils/storage';
import { createSession, deleteSession, getSessions, updateSession, getActiveExecution } from '../services/session';
import { useAST } from '../hooks/useAST';
import { useASTStore } from '../stores/astStore';
import { Terminal } from '../components/Terminal';
import { ASTPanel } from '../ast';
import type { ASTStatusMeta, ASTProgressMeta, ASTItemResultMeta } from '@terminal/shared';
import type { ASTItemStatus } from '../ast/types';

export const Route = createFileRoute('/')({
  component: TerminalPage,
});

interface TerminalApi {
  runAST: (astName: string, params?: Record<string, unknown>) => void;
}

function TerminalPage() {
  const [availableSessions, setAvailableSessions] = useState<{ id: string; name?: string }[]>([]);
  const [tabs, setTabs] = useState<{ id: string; sessionId: string; name?: string }[]>([]);
  const [activeTabId, setActiveTabIdLocal] = useState<string>('');
  const [sessionsLoaded, setSessionsLoaded] = useState(false);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editingTabId, setEditingTabId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  // Get Zustand store actions
  const initTab = useASTStore((state) => state.initTab);
  const removeTab = useASTStore((state) => state.removeTab);
  const setActiveTabId = useASTStore((state) => state.setActiveTabId);

  // Sync active tab ID to Zustand store
  useEffect(() => {
    if (activeTabId) {
      setActiveTabId(activeTabId);
    }
  }, [activeTabId, setActiveTabId]);

  useEffect(() => {
    const initializeSession = async () => {
      try {
        const sessions = await getSessions();

        setAvailableSessions(sessions);
        setLoadError(null);

        let currentSessionId = getStoredSessionId();
        let validSession = sessions.find((s) => s.id === currentSessionId);

        if (!validSession && sessions.length > 0) {
          removeStoredSessionId();
          currentSessionId = sessions[0].id;
          validSession = sessions[0];
        }

        if (sessions.length > 0) {
          const initialTabs = sessions.map((s) => {
            // Use sessionId as tabId for stable identity across navigation
            initTab(s.id);
            return {
              id: s.id,
              sessionId: s.id,
              name: s.name,
            };
          });
          setTabs(initialTabs);
          if (validSession) {
            setStoredSessionId(currentSessionId ?? '');
            setActiveTabIdLocal(validSession.id);
          } else {
            setActiveTabIdLocal(initialTabs[0].id);
            setStoredSessionId(initialTabs[0].sessionId);
          }
        } else {
          setTabs([]);
          setActiveTabIdLocal('');
          removeStoredSessionId();
        }
      } catch (error) {
        console.error('Failed to initialize session:', error);
        removeStoredSessionId();
        setLoadError('Unable to load sessions. Use + to start a new one.');
        setTabs([]);
        setActiveTabIdLocal('');
      } finally {
        setSessionsLoaded(true);
      }
    };

    initializeSession();
  }, [initTab]);

  const handleAddTab = useCallback(() => {
    if (isCreatingSession) return;
    const newName = `Session ${tabs.length + 1}`;
    setIsCreatingSession(true);
    createSession(newName)
      .then((session) => {
        setAvailableSessions((prev) => [...prev, { id: session.id, name: session.name }]);
        // Use sessionId as tabId for stable identity
        initTab(session.id);
        const newTab = { id: session.id, sessionId: session.id, name: session.name };
        setTabs((prev) => [...prev, newTab]);
        setActiveTabIdLocal(session.id);
        setStoredSessionId(session.id);
      })
      .catch((error) => {
        console.error('Failed to create session:', error);
      })
      .finally(() => setIsCreatingSession(false));
  }, [initTab, isCreatingSession, tabs.length]);

  // Get tabs state from Zustand to check for running ASTs
  const tabsASTState = useASTStore((state) => state.tabs);

  // Check if a tab has a running AST
  const isTabRunningAST = useCallback(
    (tabId: string): boolean => {
      const tabState = tabsASTState[tabId];
      if (!tabState) return false;
      return tabState.status === 'running' || tabState.status === 'paused';
    },
    [tabsASTState]
  );

  const handleCloseTab = useCallback(
    (tabId: string) => {
      const tabToClose = tabs.find((t) => t.id === tabId);
      if (!tabToClose) return;

      // Prevent closing if AST is running
      if (isTabRunningAST(tabId)) {
        return; // Don't allow closing
      }

      const idx = tabs.findIndex((t) => t.id === tabId);
      const nextTabs = tabs.filter((t) => t.id !== tabId);

      const isClosingActive = tabId === activeTabId;
      const nextActiveTab = nextTabs.length === 0 ? null : isClosingActive ? nextTabs[Math.max(0, idx - 1)] : nextTabs.find((t) => t.id === activeTabId) ?? nextTabs[0];

      // Remove tab from Zustand store
      removeTab(tabId);
      setTabs(nextTabs);

      if (!nextActiveTab) {
        setActiveTabIdLocal('');
        removeStoredSessionId();
      } else {
        setActiveTabIdLocal(nextActiveTab.id);
        setStoredSessionId(nextActiveTab.sessionId);
      }

      // Remove from available sessions
      if (tabToClose.sessionId) {
        setAvailableSessions((prev) => prev.filter((s) => s.id !== tabToClose.sessionId));

        // Delete session from backend (fire and forget)
        deleteSession(tabToClose.sessionId).catch((error) => {
          console.error('Failed to delete session:', error);
        });
      }
    },
    [activeTabId, isTabRunningAST, removeTab, tabs]
  );

  const handleSwitchTab = useCallback(
    (tabId: string) => {
      const target = tabs.find((t) => t.id === tabId);
      if (!target) return;
      setActiveTabIdLocal(tabId);
      setStoredSessionId(target.sessionId);
    },
    [tabs]
  );

  const renderTabLabel = useCallback(
    (tab: { id: string; sessionId: string; name?: string }) => {
      const sessionName =
        availableSessions.find((s) => s.id === tab.sessionId)?.name ??
        tab.name ??
        (tab.sessionId ? `Session ${tab.sessionId.slice(0, 6)}` : 'No session');
      return sessionName;
    },
    [availableSessions]
  );

  const handleStartEdit = useCallback(
    (tab: { id: string; sessionId: string; name?: string }, event: React.MouseEvent) => {
      event.stopPropagation();
      setEditingTabId(tab.id);
      setEditName(renderTabLabel(tab));
    },
    [renderTabLabel]
  );

  const handleSaveEdit = useCallback(
    async (tab: { id: string; sessionId: string; name?: string }) => {
      if (!editName.trim() || !tab.sessionId) return;

      try {
        const updated = await updateSession(tab.sessionId, editName.trim());
        setAvailableSessions((prev) =>
          prev.map((s) => (s.id === tab.sessionId ? { ...s, name: updated.name } : s))
        );
        setTabs((prev) =>
          prev.map((t) => (t.id === tab.id ? { ...t, name: updated.name } : t))
        );
        setEditingTabId(null);
        setEditName('');
      } catch (error) {
        console.error('Failed to update session:', error);
        setEditingTabId(null);
        setEditName('');
      }
    },
    [editName]
  );

  const handleCancelEdit = useCallback(() => {
    setEditingTabId(null);
    setEditName('');
  }, []);

  if (!sessionsLoaded) {
    return (
      <main className="flex-1 overflow-auto flex flex-col p-4 gap-4 bg-white dark:bg-zinc-950">
        <div className="flex items-center justify-center h-32">
          <div className="text-sm text-gray-500">Loading sessions...</div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex-1 overflow-auto flex flex-col bg-white dark:bg-zinc-950">
      {/* Tab bar */}
      <div className="flex items-stretch h-9 bg-zinc-100 dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
        {tabs.map((tab) => (
          <div
            key={tab.id}
            className={`group relative flex items-center gap-2 px-4 text-sm ${editingTabId === tab.id ? '' : 'cursor-pointer'} select-none border-r border-zinc-200 dark:border-zinc-800 ${tab.id === activeTabId
              ? 'bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100'
              : 'bg-zinc-100 dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800'
              }`}
            onClick={() => editingTabId !== tab.id && handleSwitchTab(tab.id)}
          >
            {editingTabId === tab.id ? (
              <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSaveEdit(tab);
                    if (e.key === 'Escape') handleCancelEdit();
                  }}
                  onBlur={() => handleSaveEdit(tab)}
                  className="px-1 py-0.5 text-sm border rounded bg-white dark:bg-zinc-800 dark:border-zinc-600 min-w-[80px] max-w-[160px]"
                  autoFocus
                />
              </div>
            ) : (
              <span
                className="whitespace-nowrap"
                onDoubleClick={(e) => handleStartEdit(tab, e)}
                title="Double-click to rename"
              >
                {renderTabLabel(tab)}
              </span>
            )}
            {tabs.length > 1 && editingTabId !== tab.id && (
              <button
                className={`w-4 h-4 flex items-center justify-center rounded ${isTabRunningAST(tab.id)
                  ? 'opacity-20 cursor-not-allowed'
                  : 'opacity-60 hover:opacity-100 hover:bg-zinc-200 dark:hover:bg-zinc-700 cursor-pointer'
                  } text-zinc-500 dark:text-zinc-400`}
                onClick={(e) => {
                  e.stopPropagation();
                  handleCloseTab(tab.id);
                }}
                disabled={isTabRunningAST(tab.id)}
                aria-label={isTabRunningAST(tab.id) ? "Cannot close while AST is running" : "Close tab"}
                title={isTabRunningAST(tab.id) ? "Cannot close while AST is running" : "Close tab"}
              >
                <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M3 3l6 6M9 3l-6 6" />
                </svg>
              </button>
            )}
          </div>
        ))}
        <button
          className="flex items-center gap-2 px-3 text-zinc-500 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          onClick={handleAddTab}
          disabled={isCreatingSession}
          aria-label="New session"
        >
          <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M8 3v10M3 8h10" />
          </svg>
          <span className="text-sm whitespace-nowrap">New Session</span>
        </button>
      </div>

      {/* Content - Only render the active tab to avoid multiple WebSocket connections */}
      <div className="flex-1 flex flex-col gap-4 p-4">
        {tabs.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-sm text-gray-500 dark:text-gray-400">
              No sessions available. Create one to get started.
            </div>
          </div>
        ) : (
          tabs
            .filter((tab) => tab.id === activeTabId)
            .map((tab) => <TabContent key={tab.id} tab={tab} active={true} />)
        )}
        {loadError ? (
          <div className="text-xs text-amber-600 dark:text-amber-400">{loadError}</div>
        ) : null}
      </div>
    </main>
  );
}

function TabContent({
  tab,
}: {
  tab: { id: string; sessionId: string };
}) {
  // Pass the tab ID to useAST to get per-tab state
  const {
    setRunCallback,
    handleASTComplete,
    handleASTProgress,
    handleASTItemResult,
    handleASTPaused,
    restoreFromExecution,
  } = useAST(tab.id);

  const [checkedForActiveExecution, setCheckedForActiveExecution] = useState(false);

  // Check for active execution on mount (handles page refresh)
  useEffect(() => {
    if (checkedForActiveExecution || !tab.sessionId) return;

    const checkActiveExecution = async () => {
      try {
        const execution = await getActiveExecution(tab.sessionId);
        if (execution && (execution.status === 'running' || execution.status === 'paused')) {
          restoreFromExecution({
            ast_name: execution.ast_name,
            status: execution.status,
            policy_count: execution.policy_count,
            success_count: execution.success_count,
            failed_count: execution.failed_count,
            execution_id: execution.execution_id,
          });
        }
      } catch (error) {
        console.error('Failed to check for active execution:', error);
      } finally {
        setCheckedForActiveExecution(true);
      }
    };

    checkActiveExecution();
  }, [tab.sessionId, checkedForActiveExecution, restoreFromExecution]);

  const handleTerminalReady = useCallback(
    (api: TerminalApi) => {
      setRunCallback(api.runAST);
    },
    [setRunCallback]
  );

  const handleASTStatus = useCallback(
    (status: ASTStatusMeta) => {
      const mappedStatus = status.status === 'pending' ? 'running' : status.status;
      handleASTComplete({
        status: mappedStatus,
        message: status.message,
        error: status.error,
        duration: status.duration,
        data: status.data,
      });
    },
    [handleASTComplete]
  );

  const handleASTProgressUpdate = useCallback(
    (progress: ASTProgressMeta) => {
      handleASTProgress({
        current: progress.current,
        total: progress.total,
        currentItem: progress.currentItem,
        itemStatus: progress.itemStatus as ASTItemStatus | undefined,
        message: progress.message,
        percentage: progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0,
      });
    },
    [handleASTProgress]
  );

  const handleASTItemResultUpdate = useCallback(
    (itemResult: ASTItemResultMeta) => {
      handleASTItemResult({
        itemId: itemResult.itemId,
        status: itemResult.status as ASTItemStatus,
        durationMs: itemResult.durationMs,
        error: itemResult.error,
        data: itemResult.data,
      });
    },
    [handleASTItemResult]
  );

  return (
    <div className="flex-1 flex flex-col gap-4">
      <div className="flex-1 flex gap-4">
        {tab.sessionId ? (
          <Terminal
            key={tab.id}
            sessionId={tab.sessionId}
            autoConnect={true}
            onReady={handleTerminalReady}
            onASTStatus={handleASTStatus}
            onASTProgress={handleASTProgressUpdate}
            onASTItemResult={handleASTItemResultUpdate}
            onASTPaused={handleASTPaused}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-sm text-gray-500">
              No sessions available. Create one to get started.
            </div>
          </div>
        )}

        <div className="w-[400px] flex-shrink-0">
          <ASTPanel key={tab.id} />
        </div>
      </div>
    </div>
  );
}
