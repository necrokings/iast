# Terminal Monorepo Architecture

## Overview

This is a full-stack web-based terminal application that provides secure, real-time TN3270 terminal emulation through a browser. The architecture follows a microservices pattern with clear separation of concerns.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Browser (Client)                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                     React + Vite + xterm.js                             │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │ │
│  │  │   Auth UI    │  │ Theme Toggle │  │     Terminal Component       │   │ │
│  │  │ (Login/Reg)  │  │ (Light/Dark) │  │    (xterm.js + WebSocket)    │   │ │
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
│  │  │  Auth Routes │  │   Session    │  │    WebSocket Terminal        │   │ │
│  │  │ (JWT/bcrypt) │  │  Management  │  │       Handler                │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────────┘   │ │
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
│                          TN3270 Gateway (Python)                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    asyncio + redis-py + tn3270                          │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐   │ │
│  │  │ Valkey Client│  │ TN3270 Manager│  │      TN3270 Sessions         │   │ │
│  │  │  (Pub/Sub)   │  │ (connect)    │  │   (TN3270 connections)       │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
terminal/
├── apps/
│   ├── api/                    # Fastify backend server
│   │   └── src/
│   │       ├── routes/         # HTTP endpoints (auth)
│   │       ├── ws/             # WebSocket handlers
│   │       ├── services/       # Business logic (auth, session)
│   │       ├── models/         # Data models (user)
│   │       └── valkey/         # Valkey pub/sub client
│   │
│   └── web/                    # React frontend
│       └── src/
│           ├── components/     # UI components (Terminal, LoginForm, etc.)
│           ├── hooks/          # React hooks (useAuth, useTerminal, useTheme)
│           ├── services/       # API client, WebSocket service
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
│       ├── tn3270_manager.py   # TN3270 session management
│       ├── valkey_client.py    # Async Valkey client
│       ├── models.py           # Pydantic message models
│       ├── config.py           # Gateway configuration
│       └── tn3270_client.py    # TN3270 protocol client
│
├── infra/
│   └── docker-compose.dev.yml  # Valkey container for development
│
├── scripts/
│   └── dev.sh                  # Development startup script
│
└── docs/
    └── ARCHITECTURE.md         # This document
```

## Components

### 1. Web Frontend (`apps/web`)

**Technology**: React 19, Vite 7, TypeScript 5.9, Tailwind CSS v4, xterm.js

**Responsibilities**:

- User authentication (login/register forms)
- Terminal UI rendering with xterm.js
- WebSocket connection management with auto-reconnect
- Theme switching (light/dark mode)
- Session persistence via localStorage

**Key Files**:

- `hooks/useTerminal.ts` - xterm.js integration and WebSocket handling
- `hooks/useAuth.ts` - Authentication state management
- `hooks/useTheme.ts` - Theme state with localStorage persistence
- `services/websocket.ts` - WebSocket client with reconnection logic
- `components/Terminal.tsx` - Terminal UI component

### 2. API Server (`apps/api`)

**Technology**: Fastify 5, TypeScript, ioredis, JWT, bcrypt

**Responsibilities**:

- REST API for authentication (login, register, token refresh)
- WebSocket endpoint for terminal connections
- JWT token validation
- Session management
- Message routing between browser and TN3270 gateway via Valkey

**Key Files**:

- `routes/auth.ts` - Authentication endpoints
- `ws/terminal.ts` - WebSocket terminal handler
- `services/auth.ts` - JWT generation and password hashing
- `valkey/client.ts` - Valkey pub/sub client

**Endpoints**:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create new user account |
| POST | `/auth/login` | Authenticate and get JWT |
| GET | `/auth/me` | Get current user info |
| POST | `/auth/refresh` | Refresh JWT token |
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
                 | 'session.created' | 'session.destroyed';

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

**Technology**: Python 3.12+, asyncio, Pydantic v2, redis-py, structlog

**Responsibilities**:

- Establish and manage TN3270 connections to mainframe systems
- Handle TN3270 protocol communication
- Handle terminal resize events
- Stream I/O between TN3270 and Valkey pub/sub

**Key Files**:

- `app.py` - Main entry point with signal handling
- `tn3270_manager.py` - TN3270 session lifecycle management
- `tn3270_client.py` - TN3270 protocol client
- `valkey_client.py` - Async Valkey client for pub/sub
- `models.py` - Pydantic models matching TypeScript types

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
| `tn3270.control.<sessionId>` | API → Gateway | Resize events |

## Data Flow

### 1. Authentication Flow

```
Browser                    API Server                  
   │                           │                       
   │  POST /auth/login         │                       
   │  {email, password}        │                       
   │──────────────────────────>│                       
   │                           │ Verify password       
   │                           │ Generate JWT          
   │  {token, user}            │                       
   │<──────────────────────────│                       
   │                           │                       
   │  Store token in           │                       
   │  localStorage             │                       
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
   │                     │                     │ connect TN3270
   │                     │                     │ establish session
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

## Security

### Authentication

- Passwords hashed with bcrypt (10 rounds)
- JWT tokens with configurable expiration (default: 24h)
- Tokens stored in localStorage (consider HttpOnly cookies for production)

### WebSocket Security

- JWT token required in query parameter for WebSocket connections
- Token validated before establishing connection
- Invalid tokens result in immediate connection close (code 1008)

### TN3270 Security

- Each session establishes secure TN3270 connections
- Sessions tied to authenticated users
- Graceful cleanup on disconnect

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

# Start all services
pnpm dev

# Services will be available at:
# - Web:    http://localhost:5173
# - API:    http://localhost:3000
# - Valkey: localhost:6379
# - DynamoDB: localhost:8042
```

### Demo User

A demo user is automatically created on API startup:

- Email: `demo@example.com`
- Password: `demo1234`

## Scaling Considerations

### Horizontal Scaling

- **API Servers**: Stateless, can run multiple instances behind load balancer
- **Gateways**: Each gateway handles multiple TN3270 sessions; add more for capacity
- **Valkey**: Single instance sufficient for moderate load; cluster for high availability

### Session Affinity

- WebSocket connections are long-lived
- Use sticky sessions or connection draining for graceful updates

### Future Improvements

- [ ] Redis cluster support for Valkey
- [ ] Session persistence across gateway restarts
- [ ] Rate limiting on API endpoints
- [ ] Audit logging for terminal commands
- [ ] Multi-tenant support with user isolation
