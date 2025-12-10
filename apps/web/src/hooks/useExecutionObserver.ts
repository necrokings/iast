// ============================================================================
// useExecutionObserver - WebSocket hook for observing running executions
// ============================================================================

import { useEffect, useState, useCallback, useRef } from 'react';
import { config } from '../config';
import {
  deserializeMessage,
  serializeMessage,
  isASTProgressMessage,
  isASTItemResultMessage,
  isASTStatusMessage,
  isASTPausedMessage,
  createASTControlMessage,
  type ASTProgressMeta,
  type ASTStatusMeta,
  type ASTControlAction,
} from '@terminal/shared';
import { getAccessToken } from '../utils/tokenAccessor';

export type ObserverStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface PolicyResult {
  itemId: string;
  status: 'success' | 'failed' | 'skipped';
  durationMs?: number;
  error?: string;
  data?: Record<string, unknown>;
}

export interface ExecutionObserverState {
  status: ObserverStatus;
  progress: ASTProgressMeta | null;
  policyResults: PolicyResult[];
  astStatus: ASTStatusMeta | null;
  isPaused: boolean;
  error: string | null;
}

interface UseExecutionObserverOptions {
  sessionId: string | null;
  executionId: string;
  enabled?: boolean;
  /** Initial paused state from execution record (e.g., when reconnecting) */
  initialPaused?: boolean;
}

/**
 * Hook to observe a running AST execution via WebSocket.
 * Connects to the session's WebSocket and filters messages for the specific execution.
 */
export function useExecutionObserver({
  sessionId,
  executionId,
  enabled = true,
  initialPaused = false,
}: UseExecutionObserverOptions): ExecutionObserverState & {
  disconnect: () => void;
  sendControl: (action: ASTControlAction) => void;
  pause: () => void;
  resume: () => void;
  cancel: () => void;
} {
  const [state, setState] = useState<ExecutionObserverState>({
    status: 'disconnected',
    progress: null,
    policyResults: [],
    astStatus: null,
    isPaused: initialPaused,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const mountedRef = useRef(true);
  const sessionIdRef = useRef(sessionId);

  // Keep sessionId ref updated
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (mountedRef.current) {
      setState((prev) => ({ ...prev, status: 'disconnected' }));
    }
  }, []);

  const sendControl = useCallback((action: ASTControlAction) => {
    if (wsRef.current?.readyState === WebSocket.OPEN && sessionIdRef.current) {
      const message = createASTControlMessage(sessionIdRef.current, action);
      wsRef.current.send(serializeMessage(message));
    }
  }, []);

  const pause = useCallback(() => sendControl('pause'), [sendControl]);
  const resume = useCallback(() => sendControl('resume'), [sendControl]);
  const cancel = useCallback(() => sendControl('cancel'), [sendControl]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Track previous executionId to detect changes
  const prevExecutionIdRef = useRef(executionId);
  
  // Reset state when execution changes (new execution selected)
  // Only trigger on executionId change, not initialPaused changes
  useEffect(() => {
    if (prevExecutionIdRef.current !== executionId) {
      prevExecutionIdRef.current = executionId;
      // Close existing WebSocket before resetting state
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setState({
        status: 'disconnected',
        progress: null,
        policyResults: [],
        astStatus: null,
        isPaused: initialPaused,
        error: null,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [executionId]); // intentionally exclude initialPaused to avoid loops

  useEffect(() => {
    if (!enabled || !sessionId) {
      return;
    }

    setState((prev) => ({ ...prev, status: 'connecting', error: null }));

    // Track if this effect instance is still active (handles React StrictMode double-invocation)
    let isActive = true;

    const connectWebSocket = async () => {
      const token = await getAccessToken();
      if (!token) {
        if (isActive && mountedRef.current) {
          setState((prev) => ({
            ...prev,
            status: 'error',
            error: 'Not authenticated',
          }));
        }
        return;
      }

      if (!isActive) return;

      const params = new URLSearchParams({ token });
      const url = `${config.wsBaseUrl}/terminal/${sessionId}?${params}`;

      try {
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          if (isActive && mountedRef.current) {
            setState((prev) => ({ ...prev, status: 'connected', error: null }));
          }
        };

      ws.onmessage = (event: MessageEvent<string>) => {
        // Only process messages if this WebSocket is still the current one
        if (!isActive || wsRef.current !== ws) return;
        
        try {
          const message = deserializeMessage(event.data);

          // Filter by execution ID
          if (isASTProgressMessage(message)) {
            if (message.meta.executionId === executionId) {
              setState((prev) => ({
                ...prev,
                progress: message.meta,
              }));
            }
          } else if (isASTItemResultMessage(message)) {
            if (message.meta.executionId === executionId) {
              const result: PolicyResult = {
                itemId: message.meta.itemId,
                status: message.meta.status,
                durationMs: message.meta.durationMs,
                error: message.meta.error,
                data: message.meta.data,
              };
              setState((prev) => ({
                ...prev,
                policyResults: [...prev.policyResults, result],
              }));
            }
          } else if (isASTStatusMessage(message)) {
            setState((prev) => ({
              ...prev,
              astStatus: message.meta,
            }));
          } else if (isASTPausedMessage(message)) {
            setState((prev) => ({
              ...prev,
              isPaused: message.meta.paused,
            }));
          }
        } catch {
          // Ignore parse errors for messages we don't care about
        }
      };

      ws.onerror = () => {
        if (isActive && mountedRef.current) {
          setState((prev) => ({
            ...prev,
            status: 'error',
            error: 'WebSocket connection error',
          }));
        }
      };

      ws.onclose = () => {
        if (isActive && mountedRef.current) {
          setState((prev) => ({ ...prev, status: 'disconnected' }));
        }
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
      };
      } catch (err) {
        if (isActive && mountedRef.current) {
          setState((prev) => ({
            ...prev,
            status: 'error',
            error: err instanceof Error ? err.message : 'Failed to connect',
          }));
        }
      }
    };

    connectWebSocket();

    return () => {
      isActive = false;
      disconnect();
    };
  }, [sessionId, executionId, enabled, disconnect]);

  return { ...state, disconnect, sendControl, pause, resume, cancel };
}
