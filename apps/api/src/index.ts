// ============================================================================
// API Entry Point
// ============================================================================

import 'dotenv/config';
import type { FastifyInstance } from 'fastify';
import { buildApp } from './server';
import { config } from './config';

async function main(): Promise<void> {
  const app: FastifyInstance = await buildApp();

  try {
    await app.listen({
      host: config.server.host,
      port: config.server.port,
    });

    app.log.info(`Server listening on http://${config.server.host}:${String(config.server.port)}`);
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
}

main().catch(console.error);
