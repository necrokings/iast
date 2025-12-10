// ============================================================================
// Frontend Types
// ============================================================================

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error';

export interface TerminalSession {
  id: string;
  createdAt: number;
  status: ConnectionStatus;
}

// Note: Auth state is managed by MSAL, not local state
// This interface is kept for backwards compatibility
export interface AuthState {
  isAuthenticated: boolean;
  user: AuthUser | null;
  isLoading: boolean;
  error: string | null;
}

export interface AuthUser {
  id: string;
  email: string;
  displayName?: string;
}

export interface TerminalDimensions {
  cols: number;
  rows: number;
}

export interface WebSocketMessage {
  type: string;
  data: unknown;
}

// Re-export shared types for convenience
export type {
  MessageEnvelope,
  DataMessage,
  ResizeMessage,
  ErrorMessage,
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  User,
} from '@terminal/shared';
