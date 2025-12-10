# Terminal Monorepo Architecture

## Overview

This is a full-stack web-based terminal application that provides secure, real-time TN3270 terminal emulation through a browser. The architecture follows a microservices pattern with clear separation of concerns.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Browser (Client)                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                React 19 + Vite 7 + TanStack Router + Zustand            │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │ │
│  │  │   Auth UI    │  │  AST Panel   │  │     Terminal Component       │   │ │
│  │  │ (Entra SSO)  │  │  (Zustand)   │  │    (xterm.js + WebSocket)    │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ HTTP (REST) + WebSocket
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API Server (Node.js)                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                      Fastify + @fastify/websocket                       │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │ │
│  │  │  Auth Routes │  │  History API │  │    WebSocket Terminal        │   │ │
│  │  │ (Entra/jose) │  │ (Executions) │  │       Handler                │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────────┘   │ │
│  │                          │                        │                     │ │
│  │                   ┌──────┴───────┐                │                     │ │
│  │                   │  DynamoDB    │                │                     │ │
│  │                   │   Client     │                │                     │ │
│  │                   └──────────────┘                │                     │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Pub/Sub (Redis Protocol)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Valkey (Redis-compatible)                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         Pub/Sub Channels                                │ │
│  │  ┌──────────────────┐  ┌─────────────────┐  ┌──────────────────────┐    │ │
│  │  │ gateway.control  │  │ tn3270.input.<id>│  │  tn3270.output.<id>  │    │ │
│  │  │ (session create) │  │ (user keystrokes)│  │  (TN3270 output)     │    │ │
│  │  └──────────────────┘  └─────────────────┘  └──────────────────────┘    │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Pub/Sub (Redis Protocol)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          TN3270 Gateway (Python)                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    asyncio + redis-py + tn3270 + DynamoDB               │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │ │
│  │  │ Valkey Client│  │ AST Engine   │  │      TN3270 Sessions         │   │ │
│  │  │  (Pub/Sub)   │  │ (Automation) │  │   (TN3270 connections)       │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────────┘   │ │
│  │                          │                                              │ │
│  │                   ┌──────┴───────┐                                      │ │
│  │                   │  DynamoDB    │  (Execution history, policies)       │ │
│  │                   │   Client     │                                      │ │
│  │                   └──────────────┘                                      │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ TN3270 Protocol (TCP)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Mainframe (TN3270 Host)                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                          IBM z/OS, TSO, etc.                            │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
terminal/
├── apps/
│   ├── api/                    # Fastify backend server
│   │   └── src/
│   │       ├── routes/         # HTTP endpoints (auth, history, sessions)
│   │       ├── ws/             # WebSocket handlers
│   │       ├── services/       # Business logic (auth, session, dynamodb)
│   │       ├── models/         # Data models (user, session)
│   │       └── valkey/         # Valkey pub/sub client
│   │
│   └── web/                    # React frontend
│       └── src/
│           ├── components/     # UI components (Terminal, History, etc.)
│           ├── hooks/          # React hooks (useAuth, useTerminal, useAST)
│           ├── stores/         # Zustand stores (astStore)
│           ├── services/       # API client, WebSocket service
│           ├── ast/            # AST panel components and forms
│           ├── routes/         # TanStack Router pages
│           └── config/         # Frontend configuration
│
├── packages/
│   └── shared/                 # Shared TypeScript types & utilities
│       └── src/
│           ├── messages.ts     # Message envelope types
│           ├── channels.ts     # Pub/sub channel definitions
│           ├── errors.ts       # Error codes & types
│           ├── auth.ts         # Auth-related types
│           └── utils.ts        # Shared utilities
│
├── gateway/                    # Python TN3270 gateway
│   └── src/
│       ├── app.py              # Main entry point
│       ├── services/           # TN3270 service, Valkey client
│       ├── ast/                # AST automation scripts
│       ├── models/             # Pydantic message models
│       ├── db/                 # DynamoDB client
│       └── core/               # Config, channels, errors
│
├── infra/
│   └── docker-compose.dev.yml  # Valkey + DynamoDB containers
│
├── scripts/
│   └── dev.sh                  # Development startup script
│
└── docs/
    ├── ARCHITECTURE.md         # This document
    ├── diagrams.md             # Mermaid architecture diagrams
    └── AWS_DEPLOYMENT.md       # AWS deployment guide
```

## Components

### 1. Web Frontend (`apps/web`)

**Technology**: React 19, Vite 7, TypeScript 5.9, TanStack Router, Zustand, Tailwind CSS v4, xterm.js, MSAL

**Responsibilities**:

- User authentication via Azure Entra ID (MSAL)
- Multi-tab terminal sessions with tab management
- Terminal UI rendering with xterm.js
- AST (Automated Streamlined Transaction) panel with form inputs
- Execution history viewing with live updates
- WebSocket connection management with auto-reconnect
- Theme switching (light/dark mode)
- Session persistence via localStorage

**State Management**:

- **Zustand** for global state (AST panel state per session)
- **TanStack Router** for route-based navigation
- **React Context** for auth state
- **localStorage** for theme and session persistence

**Key Files**:

- `hooks/useTerminal.ts` - xterm.js integration and WebSocket handling
- `hooks/useAST.ts` - AST state access via Zustand store
- `hooks/useAuth.ts` - Authentication state management
- `stores/astStore.ts` - Zustand store for per-tab AST state
- `services/websocket.ts` - WebSocket client with reconnection logic
- `components/Terminal.tsx` - Terminal UI component
- `routes/index.tsx` - Terminal page with tab management
- `routes/history/route.tsx` - Execution history page

### 2. API Server (`apps/api`)

**Technology**: Fastify 5, TypeScript, ioredis, AWS SDK (DynamoDB), jose

**Responsibilities**:

- REST API for user info (auto-provisioning from Entra tokens)
- REST API for session management (CRUD)
- REST API for execution history
- WebSocket endpoint for terminal connections
- Azure Entra ID token validation via jose
- Message routing between browser and TN3270 gateway via Valkey

**Key Files**:

- `routes/auth.ts` - User info endpoint (auto-provisions users)
- `routes/sessions.ts` - Session management endpoints
- `routes/history.ts` - Execution history endpoints
- `ws/terminal.ts` - WebSocket terminal handler
- `services/auth.ts` - Entra token validation via jose
- `services/dynamodb.ts` - DynamoDB client
- `valkey/client.ts` - Valkey pub/sub client

**Endpoints**:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/me` | Get current user info (auto-provisions from Entra token) |
| GET | `/sessions` | List user sessions |
| POST | `/sessions` | Create new session |
| PUT | `/sessions/:id` | Update session |
| DELETE | `/sessions/:id` | Delete session |
| GET | `/history` | List execution history |
| GET | `/history/:id/policies` | Get policies for execution |
| WS | `/terminal/:sessionId` | WebSocket terminal connection |

### 3. Shared Package (`packages/shared`)

**Technology**: TypeScript (source-only, no build step)

**Responsibilities**:

- Type definitions shared between frontend and backend
- Message envelope structure for WebSocket communication
- Error codes and error handling utilities
- Channel name conventions for pub/sub
- Validation utilities

**Key Types**:

```typescript
// Message types
type MessageType = 'data' | 'resize' | 'ping' | 'pong' | 'error' 
                 | 'session.create' | 'session.destroy' 
                 | 'session.created' | 'session.destroyed'
                 | 'ast.run' | 'ast.status' | 'ast.progress' 
                 | 'ast.item_result' | 'ast.control' | 'ast.paused';

// Message envelope structure
interface MessageEnvelope {
  type: MessageType;
  sessionId: string;
  timestamp: number;
  encoding: string;
  seq: number;
  payload?: string;
  meta?: Record<string, unknown>;
}
```

### 4. TN3270 Gateway (`gateway`)

**Technology**: Python 3.12+, asyncio, Pydantic v2, redis-py, boto3, structlog

**Responsibilities**:

- Establish and manage TN3270 connections to mainframe systems
- Handle TN3270 protocol communication
- Execute AST automation scripts
- Record execution history to DynamoDB
- Handle terminal resize events
- Stream I/O between TN3270 and Valkey pub/sub

**Key Files**:

- `app.py` - Main entry point with signal handling
- `services/tn3270/manager.py` - TN3270 session lifecycle management
- `services/tn3270/client.py` - TN3270 protocol client
- `services/valkey.py` - Async Valkey client for pub/sub
- `ast/` - AST automation scripts (login, etc.)
- `db/client.py` - DynamoDB client for execution history
- `models/` - Pydantic models matching TypeScript types

### 5. Valkey (`infra`)

**Technology**: Valkey (Redis-compatible), Docker

**Responsibilities**:

- Message broker between API and Gateway
- Pub/sub channels for real-time communication
- Decouples API from Gateway for scalability

**Channels**:

| Channel | Direction | Purpose |
|---------|-----------|---------|
| `gateway.control` | API → Gateway | Session create/destroy commands |
| `tn3270.input.<sessionId>` | API → Gateway | User keystrokes |
| `tn3270.output.<sessionId>` | Gateway → API | TN3270 output |
| `tn3270.control.<sessionId>` | API → Gateway | Resize, AST control events |

### 6. DynamoDB

**Technology**: AWS DynamoDB (or DynamoDB Local for development)

**Tables**:

| Table | Purpose |
|-------|---------|
| `Users` | User accounts and credentials |
| `Sessions` | Terminal session metadata |
| `Executions` | AST execution history |
| `Policies` | Policy results from AST executions |

## Data Flow

### 1. Authentication Flow (Azure Entra ID)

```
Browser                    Azure Entra ID              API Server              DynamoDB
   │                            │                          │                      │
   │  User visits app           │                          │                      │
   │  (not authenticated)       │                          │                      │
   │────────────────────────────>                          │                      │
   │                            │                          │                      │
   │  Redirect to Microsoft     │                          │                      │
   │  login page                │                          │                      │
   │<───────────────────────────│                          │                      │
   │                            │                          │                      │
   │  User authenticates        │                          │                      │
   │──────────────────────────>│                          │                      │
   │                            │                          │                      │
   │  Redirect back with        │                          │                      │
   │  authorization code        │                          │                      │
   │<───────────────────────────│                          │                      │
   │                            │                          │                      │
   │  MSAL exchanges code       │                          │                      │
   │  for access token          │                          │                      │
   │──────────────────────────>│                          │                      │
   │<───────────────────────────│                          │                      │
   │                            │                          │                      │
   │  GET /auth/me              │                          │                      │
   │  Authorization: Bearer <token>                        │                      │
   │──────────────────────────────────────────────────────>│                      │
   │                            │                          │  Validate token      │
   │                            │                          │  against JWKS        │
   │                            │                          │  Query/Create user   │
   │                            │                          │─────────────────────>│
   │                            │                          │<─────────────────────│
   │  {id, email, displayName}  │                          │                      │
   │<──────────────────────────────────────────────────────│                      │
```

### 2. Terminal Session Flow

```
Browser              API Server              Valkey              Gateway
   │                     │                     │                    │
   │ WS Connect          │                     │                    │
   │ /terminal/:id       │                     │                    │
   │────────────────────>│                     │                    │
   │                     │                     │                    │
   │ session.create      │                     │                    │
   │────────────────────>│ PUBLISH             │                    │
   │                     │ gateway.control     │                    │
   │                     │────────────────────>│                    │
   │                     │                     │ MESSAGE            │
   │                     │                     │───────────────────>│
   │                     │                     │ connect TN3270     │
   │                     │                     │ PUBLISH            │
   │                     │                     │ tn3270.output.<id> │
   │                     │<────────────────────│<───────────────────│
   │ session.created     │                     │                    │
   │<────────────────────│                     │                    │
   │                     │                     │                    │
   │ data (keystroke)    │ PUBLISH             │                    │
   │────────────────────>│ tn3270.input.<id>   │                    │
   │                     │────────────────────>│ MESSAGE            │
   │                     │                     │───────────────────>│
   │                     │                     │                    │ send to TN3270
   │                     │                     │                    │
   │                     │                     │ PUBLISH            │ receive from TN3270
   │                     │                     │ tn3270.output.<id> │
   │ data (output)       │<────────────────────│<───────────────────│
   │<────────────────────│                     │                    │
```

### 3. AST Execution Flow

```
Browser              API Server              Valkey              Gateway            DynamoDB
   │                     │                     │                    │                   │
   │ ast.run             │                     │                    │                   │
   │ {name, params}      │                     │                    │                   │
   │────────────────────>│ PUBLISH             │                    │                   │
   │                     │ tn3270.input.<id>   │                    │                   │
   │                     │────────────────────>│ MESSAGE            │                   │
   │                     │                     │───────────────────>│                   │
   │                     │                     │                    │ Create execution  │
   │                     │                     │                    │──────────────────>│
   │                     │                     │                    │                   │
   │                     │                     │ PUBLISH            │ Execute AST       │
   │ ast.progress        │                     │ tn3270.output.<id> │ (loop)            │
   │<────────────────────│<────────────────────│<───────────────────│                   │
   │                     │                     │                    │ Record policy     │
   │ ast.item_result     │                     │ PUBLISH            │──────────────────>│
   │<────────────────────│<────────────────────│<───────────────────│                   │
   │                     │                     │                    │                   │
   │ ast.status          │                     │ PUBLISH            │ Update execution  │
   │ {complete}          │                     │ tn3270.output.<id> │──────────────────>│
   │<────────────────────│<────────────────────│<───────────────────│                   │
```

## Security

### Authentication

- Azure Entra ID (Microsoft Identity Platform) for single sign-on
- MSAL library handles token acquisition, caching, and refresh
- Backend validates tokens using jose against Azure JWKS endpoint
- Users auto-provisioned on first login from Entra token claims

### WebSocket Security

- Entra access token required in query parameter for WebSocket connections
- Token validated against Azure JWKS before establishing connection
- Invalid tokens result in immediate connection close (code 1008)
- Token refresh handled automatically by MSAL

### TN3270 Security

- Each session establishes secure TN3270 connections
- Sessions tied to authenticated users
- Graceful cleanup on disconnect
- WebSocket disconnect does NOT destroy TN3270 session (allows navigation)
- Explicit session destruction only on tab close

## Development

### Prerequisites

- Node.js 24+
- pnpm 10+
- Python 3.12+
- uv (Python package manager)
- Docker (for Valkey and DynamoDB Local)

### Quick Start

```bash
# Install dependencies
pnpm install
cd gateway && uv sync && cd ..

# Start infrastructure (Valkey + DynamoDB)
docker compose -f infra/docker-compose.dev.yml up -d

# Setup DynamoDB tables
./scripts/setup-dynamodb.sh

# Start all services
pnpm dev

# Services will be available at:
# - Web:      http://localhost:5173
# - API:      http://localhost:3001
# - Valkey:   localhost:6379
# - DynamoDB: localhost:8042
```

### Demo User

Users are authenticated via Azure Entra ID. No local demo user is created.
Configure your Entra ID tenant and application registration with the following environment variables:

**Frontend (.env)**:
```
VITE_ENTRA_CLIENT_ID=your-client-id
VITE_ENTRA_TENANT_ID=your-tenant-id
VITE_ENTRA_REDIRECT_URI=http://localhost:5173
VITE_ENTRA_API_SCOPE=api://your-client-id/access_as_user
```

**Backend (.env)**:
```
ENTRA_TENANT_ID=your-tenant-id
ENTRA_CLIENT_ID=your-client-id
ENTRA_API_AUDIENCE=api://your-client-id
```

## Scaling Considerations

### Horizontal Scaling

- **API Servers**: Stateless, can run multiple instances behind load balancer
- **Gateways**: Each gateway handles multiple TN3270 sessions; add more for capacity
- **Valkey**: Single instance sufficient for moderate load; cluster for high availability
- **DynamoDB**: Managed service with auto-scaling

### Session Affinity

- WebSocket connections are long-lived
- Use sticky sessions or connection draining for graceful updates
- TN3270 sessions persist across WebSocket reconnections

### Gateway Considerations

- TN3270 Gateway requires direct TCP access to mainframe
- Cannot run in serverless environments (Fargate, Lambda)
- Use EC2 or ECS on EC2 for gateway deployment
- See `docs/AWS_DEPLOYMENT.md` for detailed deployment guide

### Future Improvements

- [ ] Redis cluster support for Valkey
- [ ] Session persistence across gateway restarts
- [ ] Rate limiting on API endpoints
- [ ] Audit logging for terminal commands
- [ ] Multi-tenant support with user isolation
- [ ] Gateway health checks and auto-recovery
