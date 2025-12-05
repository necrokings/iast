# Plan: DynamoDB Local + Policy Processing Infrastructure

## Overview
Add DynamoDB Local for persistent storage of users, sessions, AST executions, and policy processing results. Extend Login AST to accept policy numbers and process each one.

---

## Steps

### 1. Add DynamoDB Local to Docker Compose
**File**: `infra/docker-compose.dev.yml`
- Add `dynamodb-local` service on port 8042
- Add volume for data persistence

### 2. Create DynamoDB Setup Script
**File**: `scripts/setup-dynamodb.sh`
- Create tables using AWS CLI:
  - `users` - User accounts
  - `sessions` - User sessions (terminal connections)
  - `ast_registry` - AST metadata (sync with frontend registry)
  - `ast_executions` - Running/completed AST instances
  - `policy_results` - Per-policy processing results

### 3. Add DynamoDB Python Client
**Files**:
- `gateway/src/db/__init__.py`
- `gateway/src/db/client.py` - DynamoDB client wrapper
- `gateway/src/db/models.py` - Pydantic models for tables
- `gateway/src/db/repositories/` - Repository pattern for each table

### 4. Define Table Schemas

**users**
| Attribute | Type | Key |
|-----------|------|-----|
| user_id | S | PK |
| email | S | GSI |
| created_at | S | |

**sessions**
| Attribute | Type | Key |
|-----------|------|-----|
| session_id | S | PK |
| user_id | S | GSI |
| status | S | |
| created_at | S | |
| last_activity | S | |

**ast_executions**
| Attribute | Type | Key |
|-----------|------|-----|
| execution_id | S | PK |
| session_id | S | GSI |
| ast_name | S | |
| status | S | |
| progress | N | (0-100) |
| total_items | N | |
| completed_items | N | |
| started_at | S | |
| completed_at | S | |
| params | M | |
| result | M | |

**policy_results**
| Attribute | Type | Key |
|-----------|------|-----|
| execution_id | S | PK |
| policy_number | S | SK |
| status | S | |
| started_at | S | |
| completed_at | S | |
| error | S | |
| screenshots | L | |

### 5. Update Login AST for Batch Processing
**File**: `gateway/src/ast/login.py`
- Accept `policy_numbers: list[str]` parameter
- Loop through each policy, login/logout
- Save per-policy results to DynamoDB
- Report progress via WebSocket messages

### 6. Add Progress Tracking to AST Base
**File**: `gateway/src/ast/base.py`
- Add `report_progress(current, total, message)` method
- Emit `ast.progress` WebSocket messages

### 7. Update Frontend Login Form
**File**: `apps/web/src/ast/login/LoginASTForm.tsx`
- Add textarea for policy numbers (comma or newline separated)
- Validate: alphanumeric, exactly 9 characters per policy number
- Show progress bar during execution (current/total with percentage)
- Display per-policy results in a scrollable list:
  - Policy number
  - Status icon (success/failed/pending)
  - Duration
  - Error message if failed

### 8. Add Progress Message Type
**Files**:
- `packages/shared/src/messages.ts` - Add `ast.progress` message type
- `gateway/src/models/ast.py` - Add Python equivalent

---

## Further Considerations

1. **AWS SDK vs boto3?** For Python, use `boto3` with endpoint override for local. For future Terraform, same code works with real DynamoDB.

2. **Progress granularity?** Send progress after each policy completes for real-time UI updates.

3. **Policy number format?** Alphanumeric, exactly 9 characters (e.g., "ABC123DEF", "POL456789"). Validate on frontend before submission.






# Stateless Gateway — Local Dev Plan

Overview

This document focuses only on local development for multi-session gateways. Gateways remain stateless and communicate via pub/sub (Redis). Session metadata and durable artifacts can be stored in DynamoDB or `dynamodb-local` for dev, but Redis will be used for pub/sub during local testing.

Goal

Allow developers to run multiple gateway containers locally — one container per user session — and verify multi-session workflows (switching sessions, pub/sub messaging, idle termination) without AWS resources.

Local Steps

1. Local pub/sub and durable stores
- Run Redis locally for pub/sub. Use `infra/docker-compose.dev.yml` to bring up `redis` (published on host port `6379`).
- Optionally run `dynamodb-local` from the same compose for metadata, if you want to keep the same DynamoDB-based metadata flow.

2. Dev orchestration script (`scripts/dev-session.sh`)
- Provide a small script to start/stop/list per-session gateway containers. The script:
  - Ensures `redis` (and optional `dynamodb-local`) are running via Docker Compose.
  - Builds a local `gateway:dev` image from `./gateway` if needed.
  - Starts a container named `gateway-<session-id>` with labels and environment variables (`SESSION_ID`, `REDIS_URL`, `METADATA_STORE=local`) and publishes ports with `-P`.
  - Stops and removes containers on demand.

3. Docker Compose / supervisor
- Use `infra/docker-compose.dev.yml` to run infrastructure services (Redis, dynamodb-local). The per-session gateways run as standalone containers started by the script so multiple instances can coexist.

4. Backend control (dev hook)
- Add a small dev-only control endpoint or a CLI that calls `scripts/dev-session.sh start|stop <session-id>` so the API can simulate the production orchestration flow locally.

5. Frontend UX (dev)
- Add a session selector (dropdown) that the frontend uses to pick which session to connect to. In dev mode, the connection info (pub/sub channel identifiers and host port) can be provided by the local control endpoint or read from a simple `/sessions` dev API.

6. Session lifecycle & termination
- Gateways should support an environment-configurable idle timeout. For local runs, the script will pass `IDLE_TIMEOUT_SECS` to the container so it self-terminates when idle.
- On shutdown, the gateway should publish a final message to its session channel so the backend/frontend can persist any artifacts.

Quick Local Workflow

- Start infra services:
  - `docker compose -f infra/docker-compose.dev.yml up -d redis dynamodb` (if you use dynamodb-local)
- Start a session container:
  - `./scripts/dev-session.sh start my-session-1`
- Query session status and port mapping:
  - `./scripts/dev-session.sh status my-session-1`
- Stop a session:
  - `./scripts/dev-session.sh stop my-session-1`

Notes

- Use `host.docker.internal` for container-to-host connections on macOS during dev (e.g., if the API runs on the host and gateways are in containers). If you run the API in containers as well, you may prefer to run the gateway containers in the same Docker network.
- Keep containers lightweight for fast startup; avoid heavy dependencies in the gateway image to reduce iteration time.

Next steps (local-only)

- Create `scripts/dev-session.sh` (done) and a short README/help text.
- Optionally add a dev-only endpoint in `apps/api` to call the script for start/stop operations.
- Implement small frontend dev hooks to list sessions and switch between them.


