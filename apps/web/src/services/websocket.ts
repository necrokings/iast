// ============================================================================
// WebSocket Service - TN3270 Terminal Communication
// ============================================================================

import { config } from '../config';
import type { ConnectionStatus } from '../types';
import {
  type MessageEnvelope,
  type ASTControlAction,
  createDataMessage,
  createPingMessage,
  createSessionCreateMessage,
  createSessionDestroyMessage,
  createASTRunMessage,
  createASTControlMessage,
  createResizeMessage,
  serializeMessage,
  deserializeMessage,
} from '@terminal/shared';
import { getAccessToken } from '../utils/tokenAccessor';

export type WebSocketEventHandler = {
  onMessage: (message: MessageEnvelope) => void;
  onStatusChange: (status: ConnectionStatus) => void;
  onError: (error: Error) => void;
};

// Track sessions that have been initialized to avoid duplicate session.create messages
// (React StrictMode can cause double-mounts)
const initializedSessions = new Set<string>();

export class TerminalWebSocket {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private handlers: WebSocketEventHandler;
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private isClosing = false;
  private seq = 0;

  constructor(sessionId: string, handlers: WebSocketEventHandler) {
    this.sessionId = sessionId;
    this.handlers = handlers;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.isClosing = false;
    this.handlers.onStatusChange('connecting');

    // Get token asynchronously and then connect
    this.connectWithToken();
  }

  private async connectWithToken(): Promise<void> {
    try {
      const token = await getAccessToken();
      const params = new URLSearchParams();
      if (token) params.set('token', token);
      const queryString = params.toString();
      const url = `${config.wsBaseUrl}/terminal/${this.sessionId}${queryString ? `?${queryString}` : ''}`;

      this.ws = new WebSocket(url);
      this.setupEventListeners();
    } catch (error) {
      this.handlers.onError(
        error instanceof Error ? error : new Error('Failed to create WebSocket')
      );
      this.handlers.onStatusChange('error');
      this.scheduleReconnect();
    }
  }

  private setupEventListeners(): void {
    if (!this.ws) return;

    this.ws.onopen = (): void => {
      this.reconnectAttempts = 0;
      this.handlers.onStatusChange('connected');
      this.startHeartbeat();

      // Only send session create message if not already initialized
      // (React StrictMode can cause double-mounts, and we don't want duplicate session.create)
      if (!initializedSessions.has(this.sessionId)) {
        initializedSessions.add(this.sessionId);
        const createMsg = createSessionCreateMessage(this.sessionId, {
          terminalType: 'tn3270',
          cols: 80,
          rows: 43,
        });
        this.sendRaw(serializeMessage(createMsg));
      }
    };

    this.ws.onmessage = (event: MessageEvent<string>): void => {
      try {
        const message = deserializeMessage(event.data);
        this.handlers.onMessage(message);
      } catch (error) {
        this.handlers.onError(
          error instanceof Error ? error : new Error('Failed to parse message')
        );
      }
    };

    this.ws.onerror = (): void => {
      this.handlers.onError(new Error('WebSocket error'));
      this.handlers.onStatusChange('error');
    };

    this.ws.onclose = (): void => {
      this.stopHeartbeat();

      if (!this.isClosing) {
        this.handlers.onStatusChange('reconnecting');
        this.scheduleReconnect();
      } else {
        this.handlers.onStatusChange('disconnected');
      }
    };
  }

  private scheduleReconnect(): void {
    if (this.isClosing) return;
    if (this.reconnectAttempts >= config.reconnect.maxAttempts) {
      this.handlers.onStatusChange('error');
      this.handlers.onError(new Error('Max reconnection attempts reached'));
      return;
    }

    const delay = Math.min(
      config.reconnect.initialDelayMs *
        Math.pow(config.reconnect.backoffMultiplier, this.reconnectAttempts),
      config.reconnect.maxDelayMs
    );

    this.reconnectTimeout = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        const pingMsg = createPingMessage(this.sessionId);
        this.sendRaw(serializeMessage(pingMsg));
      }
    }, config.heartbeat.intervalMs);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private sendRaw(data: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    }
  }

  sendData(data: string): void {
    const message = createDataMessage(this.sessionId, data);
    message.seq = ++this.seq;
    this.sendRaw(serializeMessage(message));
  }

  sendASTRun(astName: string, params?: Record<string, unknown>): void {
    // Automatically include sessionId in params for DynamoDB storage
    const enrichedParams = {
      ...params,
      sessionId: this.sessionId,
    };
    const message = createASTRunMessage(this.sessionId, astName, enrichedParams);
    message.seq = ++this.seq;
    this.sendRaw(serializeMessage(message));
  }

  sendASTControl(action: ASTControlAction): void {
    const message = createASTControlMessage(this.sessionId, action);
    message.seq = ++this.seq;
    this.sendRaw(serializeMessage(message));
  }

  sendASTPause(): void {
    this.sendASTControl('pause');
  }

  sendASTResume(): void {
    this.sendASTControl('resume');
  }

  sendASTCancel(): void {
    this.sendASTControl('cancel');
  }

  sendResize(cols: number, rows: number): void {
    const message = createResizeMessage(this.sessionId, cols, rows);
    message.seq = ++this.seq;
    this.sendRaw(serializeMessage(message));
  }

  /**
   * Disconnect from the WebSocket.
   * @param destroySession - If true, sends a session destroy message to the backend.
   *                         Default is false to allow sessions with running ASTs to persist.
   */
  disconnect(destroySession = false): void {
    this.isClosing = true;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    this.stopHeartbeat();

    if (destroySession && this.ws?.readyState === WebSocket.OPEN) {
      const destroyMsg = createSessionDestroyMessage(this.sessionId);
      this.sendRaw(serializeMessage(destroyMsg));
      // Clear from initialized sessions so a new session with same ID can be created
      initializedSessions.delete(this.sessionId);
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.handlers.onStatusChange('disconnected');
  }

  getSessionId(): string {
    return this.sessionId;
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export function createTerminalWebSocket(
  sessionId: string,
  handlers: WebSocketEventHandler
): TerminalWebSocket {
  return new TerminalWebSocket(sessionId, handlers);
}
