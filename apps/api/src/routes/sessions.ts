// ============================================================================
// Session Routes
// ============================================================================

import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import {
  createSuccessResponse,
  createErrorResponse,
  createSessionDestroyMessage,
  ERROR_CODES,
  TerminalError,
} from '@terminal/shared';
import {
  createUserSession,
  findUserSessionById,
  getUserSessionsByUserId,
  updateUserSessionName,
  deleteUserSession,
} from '../models/userSession';
import { verifyToken } from '../services/auth';
import { getValkeyClient } from '../valkey';

export function sessionRoutes(fastify: FastifyInstance): void {
  // Create a new session
  fastify.post('/sessions', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const authHeader = request.headers.authorization;
      if (!authHeader?.startsWith('Bearer ')) {
        return await reply.status(401).send(createErrorResponse(ERROR_CODES.AUTH_REQUIRED));
      }

      const token = authHeader.slice(7);
      const payload = verifyToken(token);

      const body = request.body as { name: string };
      if (!body.name || typeof body.name !== 'string' || body.name.trim().length === 0) {
        return await reply
          .status(400)
          .send(
            createErrorResponse(ERROR_CODES.VALIDATION_MISSING_FIELD, 'Session name is required')
          );
      }

      const session = await createUserSession({
        userId: payload.sub,
        name: body.name.trim(),
      });

      return await reply.status(201).send(createSuccessResponse(session));
    } catch (error) {
      if (error instanceof TerminalError) {
        return await reply.status(401).send(createErrorResponse(error.code, error.message));
      }
      fastify.log.error(error);
      return await reply.status(500).send(createErrorResponse(ERROR_CODES.INTERNAL_ERROR));
    }
  });

  // Get all sessions for the authenticated user
  fastify.get('/sessions', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const authHeader = request.headers.authorization;
      if (!authHeader?.startsWith('Bearer ')) {
        return await reply.status(401).send(createErrorResponse(ERROR_CODES.AUTH_REQUIRED));
      }

      const token = authHeader.slice(7);
      const payload = verifyToken(token);

      const sessions = await getUserSessionsByUserId(payload.sub);
      return await reply.send(createSuccessResponse(sessions));
    } catch (error) {
      if (error instanceof TerminalError) {
        return await reply.status(401).send(createErrorResponse(error.code, error.message));
      }
      fastify.log.error(error);
      return await reply.status(500).send(createErrorResponse(ERROR_CODES.INTERNAL_ERROR));
    }
  });

  // Get a specific session by ID
  fastify.get('/sessions/:sessionId', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const authHeader = request.headers.authorization;
      if (!authHeader?.startsWith('Bearer ')) {
        return await reply.status(401).send(createErrorResponse(ERROR_CODES.AUTH_REQUIRED));
      }

      const token = authHeader.slice(7);
      const payload = verifyToken(token);

      const { sessionId } = request.params as { sessionId: string };
      const session = await findUserSessionById(payload.sub, sessionId);

      if (!session) {
        return await reply
          .status(404)
          .send(createErrorResponse(ERROR_CODES.VALIDATION_FAILED, 'Session not found'));
      }

      return await reply.send(createSuccessResponse(session));
    } catch (error) {
      if (error instanceof TerminalError) {
        return await reply.status(401).send(createErrorResponse(error.code, error.message));
      }
      fastify.log.error(error);
      return await reply.status(500).send(createErrorResponse(ERROR_CODES.INTERNAL_ERROR));
    }
  });

  // Update session name
  fastify.put('/sessions/:sessionId', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const authHeader = request.headers.authorization;
      if (!authHeader?.startsWith('Bearer ')) {
        return await reply.status(401).send(createErrorResponse(ERROR_CODES.AUTH_REQUIRED));
      }

      const token = authHeader.slice(7);
      const payload = verifyToken(token);

      const { sessionId } = request.params as { sessionId: string };
      const body = request.body as { name: string };

      if (!body.name || typeof body.name !== 'string' || body.name.trim().length === 0) {
        return await reply
          .status(400)
          .send(
            createErrorResponse(ERROR_CODES.VALIDATION_MISSING_FIELD, 'Session name is required')
          );
      }

      // Verify session exists and belongs to user
      const session = await findUserSessionById(payload.sub, sessionId);
      if (!session) {
        return await reply
          .status(404)
          .send(createErrorResponse(ERROR_CODES.VALIDATION_FAILED, 'Session not found'));
      }

      await updateUserSessionName(payload.sub, sessionId, body.name.trim());

      // Return updated session
      const updatedSession = await findUserSessionById(payload.sub, sessionId);
      if (!updatedSession) {
        return await reply
          .status(500)
          .send(
            createErrorResponse(
              ERROR_CODES.INTERNAL_ERROR,
              'Updated session could not be retrieved'
            )
          );
      }

      return await reply.send(createSuccessResponse(updatedSession));
    } catch (error) {
      if (error instanceof TerminalError) {
        return await reply.status(401).send(createErrorResponse(error.code, error.message));
      }
      fastify.log.error(error);
      return await reply.status(500).send(createErrorResponse(ERROR_CODES.INTERNAL_ERROR));
    }
  });

  // Delete a session
  fastify.delete('/sessions/:sessionId', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const authHeader = request.headers.authorization;
      if (!authHeader?.startsWith('Bearer ')) {
        return await reply.status(401).send(createErrorResponse(ERROR_CODES.AUTH_REQUIRED));
      }

      const token = authHeader.slice(7);
      const payload = verifyToken(token);

      const { sessionId } = request.params as { sessionId: string };

      // Verify session exists and belongs to user
      const session = await findUserSessionById(payload.sub, sessionId);
      if (!session) {
        return await reply
          .status(404)
          .send(createErrorResponse(ERROR_CODES.VALIDATION_FAILED, 'Session not found'));
      }

      // Send destroy message to gateway to terminate TN3270 connection
      try {
        const valkey = getValkeyClient();
        const destroyMsg = createSessionDestroyMessage(sessionId);
        await valkey.publishControl(sessionId, destroyMsg);
      } catch (err) {
        fastify.log.error({ err }, 'Failed to send session destroy to gateway');
        // Continue with deletion even if gateway notification fails
      }

      await deleteUserSession(payload.sub, sessionId);
      return await reply.send(createSuccessResponse({ message: 'Session deleted successfully' }));
    } catch (error) {
      if (error instanceof TerminalError) {
        return await reply.status(401).send(createErrorResponse(error.code, error.message));
      }
      fastify.log.error(error);
      return await reply.status(500).send(createErrorResponse(ERROR_CODES.INTERNAL_ERROR));
    }
  });
}
