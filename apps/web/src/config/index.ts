// ============================================================================
// Frontend Configuration
// ============================================================================

export interface FrontendConfig {
  apiBaseUrl: string;
  wsBaseUrl: string;
  terminal: {
    defaultCols: number;
    defaultRows: number;
    fontSize: number;
    fontFamily: string;
    cursorBlink: boolean;
    scrollback: number;
  };
  reconnect: {
    maxAttempts: number;
    initialDelayMs: number;
    maxDelayMs: number;
    backoffMultiplier: number;
  };
  heartbeat: {
    intervalMs: number;
    timeoutMs: number;
  };
}

function getEnvString(key: string, defaultValue: string): string {
  const value = import.meta.env[key];
  return typeof value === 'string' ? value : defaultValue;
}

function getEnvNumber(key: string, defaultValue: number): number {
  const value = import.meta.env[key];
  if (typeof value === 'string') {
    const parsed = parseInt(value, 10);
    return isNaN(parsed) ? defaultValue : parsed;
  }
  return defaultValue;
}

// In development, we use Vite's proxy (/api -> backend)
// In production, set VITE_API_BASE_URL to your API endpoint
const isDev = import.meta.env.DEV;

export const config: FrontendConfig = {
  // In dev: '/api' (proxied by Vite), in prod: full URL or '/api' if same origin
  apiBaseUrl: getEnvString('VITE_API_BASE_URL', isDev ? '/api' : '/api'),
  // WebSocket connects directly to API server (not proxied by Vite)
  wsBaseUrl: getEnvString('VITE_WS_BASE_URL', isDev ? 'ws://127.0.0.1:3001' : `wss://${window.location.host}`),
  terminal: {
    defaultCols: getEnvNumber('VITE_TERMINAL_COLS', 80),
    defaultRows: getEnvNumber('VITE_TERMINAL_ROWS', 24),
    fontSize: getEnvNumber('VITE_TERMINAL_FONT_SIZE', 14),
    fontFamily: getEnvString('VITE_TERMINAL_FONT_FAMILY', 'Menlo, Monaco, "Courier New", monospace'),
    cursorBlink: true,
    scrollback: getEnvNumber('VITE_TERMINAL_SCROLLBACK', 10000),
  },
  reconnect: {
    maxAttempts: 5,
    initialDelayMs: 1000,
    maxDelayMs: 30000,
    backoffMultiplier: 2,
  },
  heartbeat: {
    intervalMs: 30000,
    timeoutMs: 5000,
  },
};

/**
 * Build a full API URL from a path
 * @param path - API path (e.g., '/history', '/auth/login')
 * @returns Full URL for the API endpoint
 */
export function getApiUrl(path: string): string {
  const base = config.apiBaseUrl.replace(/\/$/, '');
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${base}${cleanPath}`;
}

export default config;
