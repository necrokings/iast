// ============================================================================
// Valkey Client - Redis-compatible pub/sub
// ============================================================================

import Redis from 'ioredis';
import { config } from '../config';
import {
  getTn3270InputChannel,
  getTn3270OutputChannel,
  getTn3270ControlChannel,
  getGatewayControlChannel,
  getSessionsChannel,
  type MessageEnvelope,
  serializeMessage,
} from '@terminal/shared';

export class ValkeyClient {
  private publisher: Redis;
  private subscriber: Redis;
  // Support multiple handlers per session (for Terminal + History observer)
  private sessionSubscribers: Map<string, Set<(message: string) => void>> = new Map();

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
        const handlers = this.sessionSubscribers.get(sessionId);
        if (handlers) {
          console.log('[Valkey] Found', handlers.size, 'handler(s) for session:', sessionId);
          // Call ALL handlers for this session
          for (const handler of handlers) {
            handler(message);
          }
        }
      }
    });
  }

  // TN3270 channel methods
  async publishInput(sessionId: string, message: MessageEnvelope): Promise<void> {
    const channel = getTn3270InputChannel(sessionId);
    await this.publisher.publish(channel, serializeMessage(message));
  }

  async publishOutput(sessionId: string, message: MessageEnvelope): Promise<void> {
    const channel = getTn3270OutputChannel(sessionId);
    await this.publisher.publish(channel, serializeMessage(message));
  }

  async publishControl(sessionId: string, message: MessageEnvelope): Promise<void> {
    // TN3270 uses input channel for control messages
    const channel = getTn3270InputChannel(sessionId);
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

  async subscribeToOutput(sessionId: string, handler: (message: string) => void): Promise<void> {
    const channel = getTn3270OutputChannel(sessionId);

    // Get or create the set of handlers for this session
    let handlers = this.sessionSubscribers.get(sessionId);
    if (!handlers) {
      handlers = new Set();
      this.sessionSubscribers.set(sessionId, handlers);
      // Only subscribe to the channel if this is the first handler
      await this.subscriber.subscribe(channel);
    }
    handlers.add(handler);
  }

  async unsubscribeFromOutput(
    sessionId: string,
    handler?: (message: string) => void
  ): Promise<void> {
    const channel = getTn3270OutputChannel(sessionId);
    const handlers = this.sessionSubscribers.get(sessionId);

    if (handlers) {
      if (handler) {
        // Remove specific handler
        handlers.delete(handler);
      }

      // Only unsubscribe from channel if no handlers left
      if (handlers.size === 0 || !handler) {
        this.sessionSubscribers.delete(sessionId);
        await this.subscriber.unsubscribe(channel);
      }
    }
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
