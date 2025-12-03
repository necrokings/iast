// ============================================================================
// @terminal/shared - Main Entry Point
// ============================================================================

// Channels
export {
  CHANNEL_PREFIX,
  type ChannelPrefix,
  getPtyInputChannel,
  getPtyOutputChannel,
  getPtyControlChannel,
  getTn3270InputChannel,
  getTn3270OutputChannel,
  getTn3270ControlChannel,
  getGatewayControlChannel,
  getSessionsChannel,
  parseChannel,
} from './channels';

// Messages
export {
  type MessageType,
  type Encoding,
  type TerminalType,
  type DataMessage,
  type ResizeMessage,
  type ResizeMeta,
  type PingMessage,
  type PongMessage,
  type ErrorMessage,
  type ErrorMeta,
  type SessionCreateMessage,
  type SessionCreateMeta,
  type SessionDestroyMessage,
  type SessionCreatedMessage,
  type SessionCreatedMeta,
  type SessionDestroyedMessage,
  type SessionDestroyedMeta,
  type TN3270Field,
  type TN3270ScreenMeta,
  type TN3270ScreenMessage,
  type TN3270CursorMeta,
  type TN3270CursorMessage,
  type MessageEnvelope,
  isDataMessage,
  isResizeMessage,
  isPingMessage,
  isPongMessage,
  isErrorMessage,
  isSessionCreateMessage,
  isSessionDestroyMessage,
  isSessionCreatedMessage,
  isSessionDestroyedMessage,
  isTN3270ScreenMessage,
  isTN3270CursorMessage,
  resetSequence,
  createDataMessage,
  createResizeMessage,
  createPingMessage,
  createPongMessage,
  createErrorMessage,
  createSessionCreateMessage,
  createSessionDestroyMessage,
  createSessionCreatedMessage,
  createSessionDestroyedMessage,
  createTN3270ScreenMessage,
  createTN3270CursorMessage,
  serializeMessage,
  deserializeMessage,
} from './messages';

// Errors
export {
  ERROR_CODES,
  type ErrorCode,
  TerminalError,
  type TerminalErrorOptions,
  getErrorMessage,
  type ErrorResponse,
  type SuccessResponse,
  type ApiResponse,
  createErrorResponse,
  createSuccessResponse,
  isErrorResponse,
  isSuccessResponse,
} from './errors';

// Auth
export {
  type User,
  type AuthSession,
  type AuthTokenPayload,
  type LoginRequest,
  type RegisterRequest,
  type AuthResponse,
  type RefreshTokenRequest,
  type RefreshTokenResponse,
  type ValidationResult,
  isValidEmail,
  isValidPassword,
  validateLoginRequest,
  validateRegisterRequest,
  AUTH_STORAGE_KEYS,
} from './auth';

// Config
export {
  type ServerConfig,
  type ValkeyConfig,
  type AuthConfig,
  type PtyConfig,
  type AppConfig,
  DEFAULT_SERVER_CONFIG,
  DEFAULT_VALKEY_CONFIG,
  DEFAULT_AUTH_CONFIG,
  DEFAULT_PTY_CONFIG,
  getDefaultConfig,
} from './config';

// Utils
export {
  generateSessionId,
  generateUserId,
  now,
  sleep,
  retry,
  clamp,
  debounce,
  throttle,
  safeJsonParse,
  base64Encode,
  base64Decode,
} from './utils';
