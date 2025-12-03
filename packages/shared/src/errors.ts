// ============================================================================
// Error Codes - Structured Error System
// ============================================================================

export const ERROR_CODES = {
  // Authentication Errors (1xxx)
  AUTH_REQUIRED: 'E1001',
  AUTH_INVALID_TOKEN: 'E1002',
  AUTH_TOKEN_EXPIRED: 'E1003',
  AUTH_INVALID_CREDENTIALS: 'E1004',
  AUTH_USER_NOT_FOUND: 'E1005',
  AUTH_SESSION_EXPIRED: 'E1006',

  // Session Errors (2xxx)
  SESSION_NOT_FOUND: 'E2001',
  SESSION_ALREADY_EXISTS: 'E2002',
  SESSION_CREATION_FAILED: 'E2003',
  SESSION_LIMIT_EXCEEDED: 'E2004',
  SESSION_INVALID_STATE: 'E2005',

  // PTY Errors (3xxx)
  PTY_SPAWN_FAILED: 'E3001',
  PTY_WRITE_FAILED: 'E3002',
  PTY_RESIZE_FAILED: 'E3003',
  PTY_ALREADY_CLOSED: 'E3004',
  PTY_NOT_FOUND: 'E3005',

  // WebSocket Errors (4xxx)
  WS_CONNECTION_FAILED: 'E4001',
  WS_MESSAGE_INVALID: 'E4002',
  WS_CONNECTION_CLOSED: 'E4003',
  WS_TIMEOUT: 'E4004',

  // Valkey/Redis Errors (5xxx)
  VALKEY_CONNECTION_FAILED: 'E5001',
  VALKEY_PUBLISH_FAILED: 'E5002',
  VALKEY_SUBSCRIBE_FAILED: 'E5003',

  // Validation Errors (6xxx)
  VALIDATION_FAILED: 'E6001',
  VALIDATION_MISSING_FIELD: 'E6002',
  VALIDATION_INVALID_TYPE: 'E6003',
  VALIDATION_INVALID_FORMAT: 'E6004',

  // Internal Errors (9xxx)
  INTERNAL_ERROR: 'E9001',
  NOT_IMPLEMENTED: 'E9002',
  RATE_LIMITED: 'E9003',
} as const;

export type ErrorCode = (typeof ERROR_CODES)[keyof typeof ERROR_CODES];

// ============================================================================
// Structured Error Class
// ============================================================================

export interface TerminalErrorOptions {
  code: ErrorCode;
  message: string;
  details?: Record<string, unknown>;
  cause?: Error;
}

export class TerminalError extends Error {
  public readonly code: ErrorCode;
  public readonly details?: Record<string, unknown>;
  public readonly timestamp: number;

  constructor(options: TerminalErrorOptions) {
    super(options.message);
    this.name = 'TerminalError';
    this.code = options.code;
    this.details = options.details;
    this.timestamp = Date.now();

    if (options.cause) {
      this.cause = options.cause;
    }

    // Maintains proper stack trace for where our error was thrown (V8 only)
    if ('captureStackTrace' in Error && typeof Error.captureStackTrace === 'function') {
      Error.captureStackTrace(this, TerminalError);
    }
  }

  toJSON(): Record<string, unknown> {
    return {
      name: this.name,
      code: this.code,
      message: this.message,
      details: this.details,
      timestamp: this.timestamp,
      stack: this.stack,
    };
  }

  static fromCode(code: ErrorCode, details?: Record<string, unknown>): TerminalError {
    const message = getErrorMessage(code);
    return new TerminalError({ code, message, details });
  }
}

// ============================================================================
// Error Messages Map
// ============================================================================

const ERROR_MESSAGES: Record<ErrorCode, string> = {
  [ERROR_CODES.AUTH_REQUIRED]: 'Authentication required',
  [ERROR_CODES.AUTH_INVALID_TOKEN]: 'Invalid authentication token',
  [ERROR_CODES.AUTH_TOKEN_EXPIRED]: 'Authentication token has expired',
  [ERROR_CODES.AUTH_INVALID_CREDENTIALS]: 'Invalid email or password',
  [ERROR_CODES.AUTH_USER_NOT_FOUND]: 'User not found',
  [ERROR_CODES.AUTH_SESSION_EXPIRED]: 'Session has expired',

  [ERROR_CODES.SESSION_NOT_FOUND]: 'Terminal session not found',
  [ERROR_CODES.SESSION_ALREADY_EXISTS]: 'Terminal session already exists',
  [ERROR_CODES.SESSION_CREATION_FAILED]: 'Failed to create terminal session',
  [ERROR_CODES.SESSION_LIMIT_EXCEEDED]: 'Maximum session limit exceeded',
  [ERROR_CODES.SESSION_INVALID_STATE]: 'Invalid session state',

  [ERROR_CODES.PTY_SPAWN_FAILED]: 'Failed to spawn PTY process',
  [ERROR_CODES.PTY_WRITE_FAILED]: 'Failed to write to PTY',
  [ERROR_CODES.PTY_RESIZE_FAILED]: 'Failed to resize PTY',
  [ERROR_CODES.PTY_ALREADY_CLOSED]: 'PTY is already closed',
  [ERROR_CODES.PTY_NOT_FOUND]: 'PTY not found',

  [ERROR_CODES.WS_CONNECTION_FAILED]: 'WebSocket connection failed',
  [ERROR_CODES.WS_MESSAGE_INVALID]: 'Invalid WebSocket message',
  [ERROR_CODES.WS_CONNECTION_CLOSED]: 'WebSocket connection closed',
  [ERROR_CODES.WS_TIMEOUT]: 'WebSocket operation timed out',

  [ERROR_CODES.VALKEY_CONNECTION_FAILED]: 'Failed to connect to Valkey',
  [ERROR_CODES.VALKEY_PUBLISH_FAILED]: 'Failed to publish to Valkey',
  [ERROR_CODES.VALKEY_SUBSCRIBE_FAILED]: 'Failed to subscribe to Valkey channel',

  [ERROR_CODES.VALIDATION_FAILED]: 'Validation failed',
  [ERROR_CODES.VALIDATION_MISSING_FIELD]: 'Required field is missing',
  [ERROR_CODES.VALIDATION_INVALID_TYPE]: 'Invalid field type',
  [ERROR_CODES.VALIDATION_INVALID_FORMAT]: 'Invalid field format',

  [ERROR_CODES.INTERNAL_ERROR]: 'Internal server error',
  [ERROR_CODES.NOT_IMPLEMENTED]: 'Feature not implemented',
  [ERROR_CODES.RATE_LIMITED]: 'Rate limit exceeded',
};

export function getErrorMessage(code: ErrorCode): string {
  return ERROR_MESSAGES[code];
}

// ============================================================================
// Error Response Type
// ============================================================================

export interface ErrorResponse {
  success: false;
  error: {
    code: ErrorCode;
    message: string;
    details?: Record<string, unknown>;
    timestamp: number;
  };
}

export function createErrorResponse(
  code: ErrorCode,
  message?: string,
  details?: Record<string, unknown>
): ErrorResponse {
  return {
    success: false,
    error: {
      code,
      message: message ?? getErrorMessage(code),
      details,
      timestamp: Date.now(),
    },
  };
}

// ============================================================================
// Success Response Type
// ============================================================================

export interface SuccessResponse<T> {
  success: true;
  data: T;
}

export function createSuccessResponse<T>(data: T): SuccessResponse<T> {
  return {
    success: true,
    data,
  };
}

export type ApiResponse<T> = SuccessResponse<T> | ErrorResponse;

export function isErrorResponse(response: ApiResponse<unknown>): response is ErrorResponse {
  return !response.success;
}

export function isSuccessResponse<T>(response: ApiResponse<T>): response is SuccessResponse<T> {
  return response.success;
}
