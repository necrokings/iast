// ============================================================================
// WebSocket Terminal Handler
// ============================================================================

import type { FastifyInstance, FastifyRequest } from 'fastify';
import type { WebSocket } from 'ws';
import {
  deserializeMessage,
  serializeMessage,
  createErrorMessage,
  createPongMessage,
  isDataMessage,
  isPingMessage,
  isSessionCreateMessage,
  isSessionDestroyMessage,
  isASTRunMessage,
  isASTControlMessage,
  TerminalError,
  ERROR_CODES,
} from '@terminal/shared';
import { verifyToken } from '../services/auth';
import { createTerminalSession, endTerminalSession, touchSession } from '../services/session';
import { getValkeyClient } from '../valkey';

interface TerminalParams {
  sessionId: string;
}

interface TerminalQuery {
  token?: string;
}

export function terminalWebSocket(fastify: FastifyInstance): void {
  fastify.get<{
    Params: TerminalParams;
    Querystring: TerminalQuery;
  }>(
    '/terminal/:sessionId',
    { websocket: true },
    (
      socket: WebSocket,
      request: FastifyRequest<{
        Params: TerminalParams;
        Querystring: TerminalQuery;
      }>
    ) => {
      const { sessionId } = request.params;
      const { token } = request.query;

      // Handle async token verification
      const initConnection = async (): Promise<void> => {
        let userId: string | null = null;

        // Verify token if provided
        if (token) {
          try {
            const payload = await verifyToken(token);
            userId = payload.sub;
          } catch {
            const errorMsg = createErrorMessage(
              sessionId,
              ERROR_CODES.AUTH_INVALID_TOKEN,
              'Invalid authentication token'
            );
            socket.send(serializeMessage(errorMsg));
            socket.close(1008, 'Unauthorized');
            return;
          }
        }

        if (!userId) {
          const errorMsg = createErrorMessage(
            sessionId,
            ERROR_CODES.AUTH_REQUIRED,
            'Authentication required'
          );
          socket.send(serializeMessage(errorMsg));
          socket.close(1008, 'Unauthorized');
          return;
        }

        // Create or get terminal session
        try {
          createTerminalSession(userId, sessionId);
        } catch (err) {
          if (err instanceof TerminalError) {
            const errorMsg = createErrorMessage(sessionId, err.code, err.message);
            socket.send(serializeMessage(errorMsg));
            socket.close(1008, err.message);
            return;
          }
          throw err;
        }

        const valkey = getValkeyClient();

        // Subscribe to TN3270 terminal output
        const handleOutput = (message: string): void => {
          if (socket.readyState === socket.OPEN) {
            socket.send(message);
          }
        };

        valkey.subscribeToOutput(sessionId, handleOutput).catch((err: unknown) => {
          fastify.log.error({ err }, 'Failed to subscribe to TN3270 output');
        });

        fastify.log.info({ sessionId }, 'TN3270 Terminal WebSocket connected');

        // Handle incoming messages
        socket.on('message', (data: Buffer) => {
          try {
            const message = deserializeMessage(data.toString());
            touchSession(sessionId);

            if (isDataMessage(message)) {
              // Forward input to TN3270 terminal via Valkey
              valkey.publishInput(sessionId, message).catch((err: unknown) => {
                fastify.log.error({ err }, 'Failed to publish TN3270 input');
              });
            } else if (isASTRunMessage(message)) {
              // Forward AST run request to TN3270 gateway via input channel
              fastify.log.info(
                { sessionId, astName: message.meta.astName },
                'Forwarding AST run request'
              );
              valkey.publishInput(sessionId, message).catch((err: unknown) => {
                fastify.log.error({ err }, 'Failed to publish AST run request');
              });
            } else if (isASTControlMessage(message)) {
              // Forward AST control (pause/resume/cancel) to TN3270 gateway
              fastify.log.info(
                { sessionId, action: message.meta.action },
                'Forwarding AST control request'
              );
              valkey.publishInput(sessionId, message).catch((err: unknown) => {
                fastify.log.error({ err }, 'Failed to publish AST control request');
              });
            } else if (isPingMessage(message)) {
              // Respond with pong
              const pong = createPongMessage(sessionId);
              socket.send(serializeMessage(pong));
            } else if (isSessionCreateMessage(message)) {
              // Forward session create to TN3270 gateway control channel
              fastify.log.info(
                { sessionId: message.sessionId },
                'Forwarding session create to TN3270 gateway'
              );
              valkey.publishTn3270Control(message).catch((err: unknown) => {
                fastify.log.error({ err }, 'Failed to publish TN3270 session create');
              });
            } else if (isSessionDestroyMessage(message)) {
              // Forward session destroy to TN3270 gateway
              valkey.publishControl(sessionId, message).catch((err: unknown) => {
                fastify.log.error({ err }, 'Failed to publish TN3270 session destroy');
              });
            }
          } catch (err) {
            fastify.log.error({ err }, 'Failed to process message');
            const errorMsg = createErrorMessage(
              sessionId,
              ERROR_CODES.WS_MESSAGE_INVALID,
              'Invalid message format'
            );
            socket.send(serializeMessage(errorMsg));
          }
        });

        // Handle close
        socket.on('close', () => {
          valkey.unsubscribeFromOutput(sessionId, handleOutput).catch((err: unknown) => {
            fastify.log.error({ err }, 'Failed to unsubscribe from TN3270');
          });
          endTerminalSession(sessionId, userId);
        });

        // Handle errors
        socket.on('error', (err: Error) => {
          fastify.log.error({ err }, 'WebSocket error');
        });
      };

      // Start async initialization
      initConnection().catch((err) => {
        fastify.log.error({ err }, 'Failed to initialize WebSocket connection');
        const errorMsg = createErrorMessage(
          sessionId,
          ERROR_CODES.INTERNAL_ERROR,
          'Connection initialization failed'
        );
        socket.send(serializeMessage(errorMsg));
        socket.close(1011, 'Internal Error');
      });
    }
  );
}
