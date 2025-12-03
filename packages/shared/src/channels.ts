// ============================================================================
// Channel Constants
// ============================================================================

export const CHANNEL_PREFIX = {
  PTY_INPUT: 'pty.input',
  PTY_OUTPUT: 'pty.output',
  PTY_CONTROL: 'pty.control',
  TN3270_INPUT: 'tn3270.input',
  TN3270_OUTPUT: 'tn3270.output',
  TN3270_CONTROL: 'tn3270.control',
  SESSIONS: 'sessions.events',
  GATEWAY_CONTROL: 'gateway.control',
} as const;

export type ChannelPrefix = (typeof CHANNEL_PREFIX)[keyof typeof CHANNEL_PREFIX];

export function getPtyInputChannel(sessionId: string): string {
  return `${CHANNEL_PREFIX.PTY_INPUT}.${sessionId}`;
}

export function getPtyOutputChannel(sessionId: string): string {
  return `${CHANNEL_PREFIX.PTY_OUTPUT}.${sessionId}`;
}

export function getPtyControlChannel(sessionId: string): string {
  return `${CHANNEL_PREFIX.PTY_CONTROL}.${sessionId}`;
}

export function getTn3270InputChannel(sessionId: string): string {
  return `${CHANNEL_PREFIX.TN3270_INPUT}.${sessionId}`;
}

export function getTn3270OutputChannel(sessionId: string): string {
  return `${CHANNEL_PREFIX.TN3270_OUTPUT}.${sessionId}`;
}

export function getTn3270ControlChannel(): string {
  return CHANNEL_PREFIX.TN3270_CONTROL;
}

export function getGatewayControlChannel(): string {
  return CHANNEL_PREFIX.GATEWAY_CONTROL;
}

export function getSessionsChannel(): string {
  return CHANNEL_PREFIX.SESSIONS;
}

export function parseChannel(channel: string): {
  prefix: string;
  sessionId: string | null;
} {
  const parts = channel.split('.');
  if (parts.length >= 3) {
    return {
      prefix: `${parts[0]}.${parts[1]}`,
      sessionId: parts.slice(2).join('.'),
    };
  }
  return {
    prefix: channel,
    sessionId: null,
  };
}
