// ============================================================================
// Valkey Client - Redis-compatible pub/sub
// ============================================================================

import Redis from 'ioredis';
import { config } from '../config';
import {
  getPtyInputChannel,
  getPtyOutputChannel,
  getPtyControlChannel,
  getTn3270InputChannel,
  getTn3270OutputChannel,
  getTn3270ControlChannel,
  getGatewayControlChannel,
  getSessionsChannel,
  type MessageEnvelope,
  type TerminalType,
  serializeMessage,
} from '@terminal/shared';

export class ValkeyClient {
  private publisher: Redis;
  private subscriber: Redis;
  private sessionSubscribers: Map<string, (message: string) => void> = new Map();

  constructor() {
    const redisConfig = {
      host: config.valkey.host,
      port: config.valkey.port,
      password: config.valkey.password,
      db: config.valkey.db,
      tls: config.valkey.tls ? {} : undefined,
      retryStrategy: (times: number): number => {
        return Math.min(times * 100, 3000);
      },
    };

    this.publisher = new Redis(redisConfig);
    this.subscriber = new Redis(redisConfig);

    this.publisher.on('error', (err) => {
      console.error('Valkey publisher error:', err);
    });

    this.subscriber.on('error', (err) => {
      console.error('Valkey subscriber error:', err);
    });

    this.subscriber.on('message', (channel: string, message: string) => {
      // Extract sessionId from channel
      const parts = channel.split('.');
      if (parts.length >= 3) {
        const sessionId = parts.slice(2).join('.');
        const handler = this.sessionSubscribers.get(sessionId);
        if (handler) {
          handler(message);
        }
      }
    });
  }

  // PTY channel methods
  async publishInput(sessionId: string, message: MessageEnvelope, terminalType: TerminalType = 'pty'): Promise<void> {
    const channel = terminalType === 'tn3270' 
      ? getTn3270InputChannel(sessionId) 
      : getPtyInputChannel(sessionId);
    await this.publisher.publish(channel, serializeMessage(message));
  }

  async publishOutput(sessionId: string, message: MessageEnvelope, terminalType: TerminalType = 'pty'): Promise<void> {
    const channel = terminalType === 'tn3270'
      ? getTn3270OutputChannel(sessionId)
      : getPtyOutputChannel(sessionId);
    await this.publisher.publish(channel, serializeMessage(message));
  }

  async publishControl(sessionId: string, message: MessageEnvelope, terminalType: TerminalType = 'pty'): Promise<void> {
    const channel = terminalType === 'tn3270'
      ? getTn3270InputChannel(sessionId)  // TN3270 uses input channel for control
      : getPtyControlChannel(sessionId);
    await this.publisher.publish(channel, serializeMessage(message));
  }

  async publishGatewayControl(message: MessageEnvelope): Promise<void> {
    const channel = getGatewayControlChannel();
    await this.publisher.publish(channel, serializeMessage(message));
  }

  async publishTn3270Control(message: MessageEnvelope): Promise<void> {
    const channel = getTn3270ControlChannel();
    await this.publisher.publish(channel, serializeMessage(message));
  }

  async publishSessionEvent(message: MessageEnvelope): Promise<void> {
    const channel = getSessionsChannel();
    await this.publisher.publish(channel, serializeMessage(message));
  }

  async subscribeToOutput(sessionId: string, handler: (message: string) => void, terminalType: TerminalType = 'pty'): Promise<void> {
    const channel = terminalType === 'tn3270'
      ? getTn3270OutputChannel(sessionId)
      : getPtyOutputChannel(sessionId);
    this.sessionSubscribers.set(sessionId, handler);
    await this.subscriber.subscribe(channel);
  }

  async unsubscribeFromOutput(sessionId: string, terminalType: TerminalType = 'pty'): Promise<void> {
    const channel = terminalType === 'tn3270'
      ? getTn3270OutputChannel(sessionId)
      : getPtyOutputChannel(sessionId);
    this.sessionSubscribers.delete(sessionId);
    await this.subscriber.unsubscribe(channel);
  }

  async close(): Promise<void> {
    await this.publisher.quit();
    await this.subscriber.quit();
  }

  isConnected(): boolean {
    return this.publisher.status === 'ready' && this.subscriber.status === 'ready';
  }
}

// Singleton instance
let valkeyClient: ValkeyClient | null = null;

export function getValkeyClient(): ValkeyClient {
  if (!valkeyClient) {
    valkeyClient = new ValkeyClient();
  }
  return valkeyClient;
}

export async function closeValkeyClient(): Promise<void> {
  if (valkeyClient) {
    await valkeyClient.close();
    valkeyClient = null;
  }
}
