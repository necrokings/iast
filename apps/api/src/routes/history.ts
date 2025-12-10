// ============================================================================
// History Routes
// ============================================================================

import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import {
  createSuccessResponse,
  createErrorResponse,
  ERROR_CODES,
} from '@terminal/shared';
import {
  getExecutionsByDate,
  getExecutionById,
  getExecutionPolicies,
  getFailedPolicies,
  type ExecutionStatus,
} from '../services/dynamodb';
import { verifyToken } from '../services/auth';

// ============================================================================
// Types
// ============================================================================

interface GetHistoryQuery {
  date?: string;
  status?: ExecutionStatus;
  cursor?: string;
  limit?: string;
}

interface GetPoliciesQuery {
  status?: 'success' | 'failed' | 'skipped';
  cursor?: string;
  limit?: string;
}

interface ExecutionParams {
  executionId: string;
}

// ============================================================================
// Helpers
// ============================================================================

async function getUserIdFromAuth(request: FastifyRequest): Promise<string | null> {
  const authHeader = request.headers.authorization;
  if (!authHeader?.startsWith('Bearer ')) {
    return null;
  }
  
  try {
    const token = authHeader.slice(7);
    const payload = await verifyToken(token);
    return payload.sub; // sub contains the userId
  } catch {
    return null;
  }
}

// ============================================================================
// Routes
// ============================================================================

function parseCursor(cursorStr: string | undefined): Record<string, unknown> | undefined {
  if (!cursorStr) return undefined;
  try {
    return JSON.parse(decodeURIComponent(cursorStr)) as Record<string, unknown>;
  } catch {
    return undefined;
  }
}

export function historyRoutes(fastify: FastifyInstance): void {
  /**
   * GET /history
   * Get executions for the authenticated user, filtered by date and status
   */
  fastify.get('/history', async (request: FastifyRequest, reply: FastifyReply) => {
    try {
      const userId = await getUserIdFromAuth(request);
      if (!userId) {
        return await reply.status(401).send(createErrorResponse(ERROR_CODES.AUTH_REQUIRED));
      }

      const query = request.query as GetHistoryQuery;
      const date = query.date || new Date().toISOString().split('T')[0];
      const limit = query.limit ? parseInt(query.limit, 10) : 50;
      const cursor = parseCursor(query.cursor);

      const result = await getExecutionsByDate(userId, date, {
        status: query.status,
        limit,
        cursor,
      });

      return await reply.send(createSuccessResponse({
        executions: result.items,
        nextCursor: result.nextCursor 
          ? encodeURIComponent(JSON.stringify(result.nextCursor))
          : undefined,
        hasMore: !!result.nextCursor,
        date,
        status: query.status || 'all',
      }));
    } catch (error) {
      fastify.log.error(error);
      return await reply.status(500).send(createErrorResponse(ERROR_CODES.INTERNAL_ERROR));
    }
  });

  /**
   * GET /history/:executionId
   * Get a single execution by ID
   */
  fastify.get<{ Params: ExecutionParams }>(
    '/history/:executionId',
    async (request, reply) => {
      try {
        const userId = await getUserIdFromAuth(request);
        if (!userId) {
          return await reply.status(401).send(createErrorResponse(ERROR_CODES.AUTH_REQUIRED));
        }

        const { executionId } = request.params;
        const execution = await getExecutionById(executionId);

        if (!execution) {
          return await reply.status(404).send(
            createErrorResponse(ERROR_CODES.RESOURCE_NOT_FOUND, 'Execution not found')
          );
        }

        // Verify user owns this execution
        if (execution.user_id !== userId) {
          return await reply.status(403).send(
            createErrorResponse(ERROR_CODES.FORBIDDEN, 'Access denied')
          );
        }

        return await reply.send(createSuccessResponse(execution));
      } catch (error) {
        fastify.log.error(error);
        return await reply.status(500).send(createErrorResponse(ERROR_CODES.INTERNAL_ERROR));
      }
    }
  );

  /**
   * GET /history/:executionId/policies
   * Get policies for an execution with optional status filter
   */
  fastify.get<{ Params: ExecutionParams }>(
    '/history/:executionId/policies',
    async (request, reply) => {
      try {
        const userId = await getUserIdFromAuth(request);
        fastify.log.info({ userId, path: request.url }, 'Policies request');
        
        if (!userId) {
          return await reply.status(401).send(createErrorResponse(ERROR_CODES.AUTH_REQUIRED));
        }

        const { executionId } = request.params;
        const query = request.query as GetPoliciesQuery;
        
        fastify.log.info({ executionId }, 'Looking up execution');
        
        // First verify user owns this execution
        const execution = await getExecutionById(executionId);
        fastify.log.info({ found: !!execution, userId: execution?.user_id }, 'Execution lookup result');
        
        if (!execution) {
          return await reply.status(404).send(
            createErrorResponse(ERROR_CODES.RESOURCE_NOT_FOUND, 'Execution not found')
          );
        }
        if (execution.user_id !== userId) {
          return await reply.status(403).send(
            createErrorResponse(ERROR_CODES.FORBIDDEN, 'Access denied')
          );
        }

        const limit = query.limit ? parseInt(query.limit, 10) : 100;
        const cursor = parseCursor(query.cursor);

        const result = await getExecutionPolicies(executionId, {
          status: query.status,
          limit,
          cursor,
        });

        return await reply.send(createSuccessResponse({
          policies: result.items,
          nextCursor: result.nextCursor 
            ? encodeURIComponent(JSON.stringify(result.nextCursor))
            : undefined,
          hasMore: !!result.nextCursor,
        }));
      } catch (error) {
        fastify.log.error(error);
        return await reply.status(500).send(createErrorResponse(ERROR_CODES.INTERNAL_ERROR));
      }
    }
  );

  /**
   * GET /history/:executionId/policies/failed
   * Get only failed policies for an execution (convenience endpoint)
   */
  fastify.get<{ Params: ExecutionParams }>(
    '/history/:executionId/policies/failed',
    async (request, reply) => {
      try {
        const userId = await getUserIdFromAuth(request);
        if (!userId) {
          return await reply.status(401).send(createErrorResponse(ERROR_CODES.AUTH_REQUIRED));
        }

        const { executionId } = request.params;
        
        // First verify user owns this execution
        const execution = await getExecutionById(executionId);
        if (!execution) {
          return await reply.status(404).send(
            createErrorResponse(ERROR_CODES.RESOURCE_NOT_FOUND, 'Execution not found')
          );
        }
        if (execution.user_id !== userId) {
          return await reply.status(403).send(
            createErrorResponse(ERROR_CODES.FORBIDDEN, 'Access denied')
          );
        }

        const policies = await getFailedPolicies(executionId);

        return await reply.send(createSuccessResponse({
          policies,
          count: policies.length,
        }));
      } catch (error) {
        fastify.log.error(error);
        return await reply.status(500).send(createErrorResponse(ERROR_CODES.INTERNAL_ERROR));
      }
    }
  );
}
