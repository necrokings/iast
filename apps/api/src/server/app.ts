// ============================================================================
// Fastify Server Application
// ============================================================================

import Fastify, { type FastifyInstance } from 'fastify';
import cors from '@fastify/cors';
import websocket from '@fastify/websocket';
import { config } from '../config';
import { authRoutes, historyRoutes, sessionRoutes } from '../routes';
import { terminalWebSocket } from '../ws';
import { closeValkeyClient } from '../valkey';

export async function buildApp(): Promise<FastifyInstance> {
  const app = Fastify({
    logger: {
      level: config.logLevel,
      transport:
        config.env === 'development'
          ? {
              target: 'pino-pretty',
              options: {
                colorize: true,
              },
            }
          : undefined,
    },
  });

  // Register CORS
  await app.register(cors, {
    origin: config.server.cors.origin,
    credentials: config.server.cors.credentials,
    methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  });

  // Register WebSocket
  await app.register(websocket, {
    options: {
      maxPayload: 1024 * 1024, // 1MB
    },
  });

  // Health check with DynamoDB validation
  app.get('/health', async () => {
    try {
      // Validate DynamoDB connection
      const { DynamoDBClient, DescribeTableCommand } = await import('@aws-sdk/client-dynamodb');

      const dynamodb = new DynamoDBClient({
        endpoint: config.dynamodb.endpoint,
        region: config.dynamodb.region,
        credentials: {
          accessKeyId: config.dynamodb.accessKeyId,
          secretAccessKey: config.dynamodb.secretAccessKey,
        },
      });

      // Simple connectivity check - describe table
      await dynamodb.send(
        new DescribeTableCommand({
          TableName: config.dynamodb.tableName,
        })
      );

      return { status: 'ok', timestamp: Date.now(), dynamodb: 'connected' };
    } catch (error) {
      app.log.error(error);
      throw new Error('DynamoDB connection failed');
    }
  });

  // Register routes
  authRoutes(app);
  historyRoutes(app);
  sessionRoutes(app);
  terminalWebSocket(app);

  // Graceful shutdown
  const shutdown = async (): Promise<void> => {
    app.log.info('Shutting down...');
    await closeValkeyClient();
    await app.close();
    process.exit(0);
  };

  process.on('SIGINT', () => void shutdown());
  process.on('SIGTERM', () => void shutdown());

  return app;
}
