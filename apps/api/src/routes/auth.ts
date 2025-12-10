// ============================================================================
// Auth Routes - Azure Entra ID Authentication
// ============================================================================

import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import {
  createSuccessResponse,
  createErrorResponse,
  ERROR_CODES,
  TerminalError,
} from '@terminal/shared';
import { verifyEntraToken, extractUserInfo } from '../services/auth';
import { findUserById, createUser, toPublicUser } from '../models/user';

export function authRoutes(fastify: FastifyInstance): void {
  // Get current user - validates Entra token and auto-provisions user if needed
  fastify.get('/auth/me', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const authHeader = request.headers.authorization;
      if (!authHeader?.startsWith('Bearer ')) {
        return await reply.status(401).send(createErrorResponse(ERROR_CODES.AUTH_REQUIRED));
      }

      const token = authHeader.slice(7);
      
      // Verify Entra token and extract claims
      const entraPayload = await verifyEntraToken(token);
      const userInfo = extractUserInfo(entraPayload);

      // Try to find existing user by oid (id)
      let user = await findUserById(userInfo.id);
      
      // Auto-provision user on first login
      if (!user) {
        user = await createUser({
          id: userInfo.id,
          email: userInfo.email,
          displayName: userInfo.displayName,
        });
        fastify.log.info({ userId: user.id, email: user.email }, 'New user provisioned from Entra ID');
      }

      return await reply.send(createSuccessResponse(toPublicUser(user)));
    } catch (error) {
      if (error instanceof TerminalError) {
        return await reply.status(401).send(createErrorResponse(error.code, error.message));
      }
      fastify.log.error(error);
      return await reply.status(500).send(createErrorResponse(ERROR_CODES.INTERNAL_ERROR));
    }
  });

  // Logout (client-side token invalidation - Entra handles actual logout)
  fastify.post('/auth/logout', async (_request: FastifyRequest, reply: FastifyReply) => {
    return await reply.send(createSuccessResponse({ message: 'Logged out successfully' }));
  });
}
