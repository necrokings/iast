# Terminal Architecture Diagrams

## System Architecture

```mermaid
flowchart TB
    subgraph Browser["` **Browser** _(Client)_ `"]
        direction LR
        React["`**React 19** + Vite 7
        + TanStack Router`"]
        XTerm["`**xterm.js** Terminal`"]
        Zustand["`**Zustand** Store
        _(AST State)_`"]
        Auth["`**MSAL** Auth
        _(Entra ID SSO)_`"]
    end

    subgraph EntraID["` **Azure Entra ID** `"]
        direction TB
        JWKS["`JWKS Endpoint`"]
        TokenEndpoint["`Token Endpoint`"]
    end

    subgraph API["` **API Server** _(Node.js)_ `"]
        direction TB
        Fastify["`**Fastify 5**`"]
        WS["`WebSocket Handler`"]
        AuthService["`Auth Service
        _(jose + JWKS)_`"]
        HistoryAPI["`History API`"]
        SessionAPI["`Session API`"]
        ValkeyClient1["`Valkey Client`"]
        DynamoDBClient1["`DynamoDB Client`"]
    end

    subgraph Valkey["` **Valkey** _(Redis-compatible)_ `"]
        direction TB
        PubSub["`**Pub/Sub Channels**`"]
        GatewayCtrl["`gateway.control`"]
        Tn3270Input["`tn3270.input.*`"]
        Tn3270Output["`tn3270.output.*`"]
        Tn3270Control["`tn3270.control.*`"]
    end

    subgraph DynamoDB["` **DynamoDB** _(AWS/Local)_ `"]
        direction TB
        UsersTable["`Users Table`"]
        SessionsTable["`Sessions Table`"]
        ExecutionsTable["`Executions Table`"]
        PoliciesTable["`Policies Table`"]
    end

    subgraph Gateway["` **TN3270 Gateway** _(Python)_ `"]
        direction TB
        AsyncIO["`**asyncio** Runtime`"]
        ValkeyClient2["`Valkey Client`"]
        DynamoDBClient2["`DynamoDB Client`"]
        ASTEngine["`AST Engine`"]
        Tn3270Manager["`TN3270 Manager`"]
        Tn3270Session1["`TN3270 Session 1`"]
        Tn3270Session2["`TN3270 Session 2`"]
        Tn3270SessionN["`TN3270 Session N`"]
    end

    subgraph Mainframe["` **Mainframe** _(TN3270 Host)_ `"]
        direction TB
        TSO["`IBM z/OS
        TSO/ISPF`"]
    end

    React --> Auth & XTerm & Zustand

    Auth -->|"`**MSAL OAuth**`"| TokenEndpoint
    AuthService -->|"`**Validate Token**`"| JWKS
    XTerm -->|"`**WebSocket**`"| WS
    Zustand -.->|"`State sync`"| XTerm

    WS --> SessionAPI & ValkeyClient1
    AuthService --> DynamoDBClient1
    HistoryAPI --> DynamoDBClient1
    SessionAPI --> DynamoDBClient1
    DynamoDBClient1 -->|"`_Read/Write_`"| UsersTable & SessionsTable

    ValkeyClient1 -->|"`_Publish_`"| PubSub
    PubSub -->|"`_Subscribe_`"| ValkeyClient2

    ValkeyClient2 --> Tn3270Manager & ASTEngine
    ASTEngine --> DynamoDBClient2
    DynamoDBClient2 -->|"`_Read/Write_`"| ExecutionsTable & PoliciesTable
    Tn3270Manager --> Tn3270Session1 & Tn3270Session2 & Tn3270SessionN
    Tn3270Session1 & Tn3270Session2 & Tn3270SessionN -->|"`**TN3270 TCP**`"| TSO
```

## Frontend State Architecture

```mermaid
flowchart TB
    subgraph Browser["` **Browser** `"]
        direction TB
        
        subgraph Router["` **TanStack Router** `"]
            RootLayout["`Root Layout
            _(AuthGuard, Navbar)_`"]
            TerminalPage["`Terminal Page
            _/_ `"]
            HistoryPage["`History Page
            _/history_ `"]
        end

        subgraph ZustandStore["` **Zustand Store** _(astStore)_ `"]
            TabsState["`tabs: Record<tabId, TabState>`"]
            ActiveTabId["`activeTabId: string`"]
            TabState1["`Tab State 1
            - selectedASTId
            - status
            - progress
            - itemResults
            - lastResult`"]
            TabState2["`Tab State 2
            - ...`"]
        end

        subgraph Components["` **Components** `"]
            Terminal["`Terminal Component
            _(useTerminal hook)_`"]
            ASTPanel["`AST Panel
            _(useAST hook)_`"]
            HistoryList["`History List
            _(useExecutionObserver)_`"]
        end
    end

    RootLayout --> TerminalPage & HistoryPage
    TerminalPage --> Terminal & ASTPanel
    HistoryPage --> HistoryList

    Terminal -->|"`setRunCallback`"| ZustandStore
    ASTPanel -->|"`executeAST, setSelectedASTId`"| ZustandStore
    ZustandStore -->|"`state per tab`"| TabState1 & TabState2
    
    TabsState --> TabState1 & TabState2
```

## Authentication Flow (Azure Entra ID)

```mermaid
sequenceDiagram
    autonumber
    
    participant B as 🌐 Browser
    participant M as 🔐 Azure Entra ID
    participant A as ⚡ API Server
    participant DB as 💾 DynamoDB

    rect rgb(50, 40, 50)
        Note over B,DB: User Login (MSAL Redirect)
        B->>B: User visits app (not authenticated)
        B->>M: Redirect to Microsoft login
        M->>M: User authenticates
        M-->>B: Redirect with authorization code
        B->>M: MSAL exchanges code for tokens
        M-->>B: Access token + ID token
    end

    rect rgb(40, 50, 50)
        Note over B,DB: User Info & Provisioning
        B->>+A: GET /auth/me<br/>Authorization: Bearer {entra_token}
        A->>M: Fetch JWKS (cached)
        A->>A: Validate token signature
        A->>A: Extract claims (oid, email, name)
        A->>DB: GetItem (Users)
        alt User exists
            DB-->>A: User record
        else User not found
            A->>DB: PutItem (new user)
            DB-->>A: Success
        end
        A-->>-B: {id, email, displayName}
    end

    rect rgb(40, 40, 60)
        Note over B,DB: Token Refresh (automatic)
        B->>B: MSAL detects token expiring
        B->>M: acquireTokenSilent
        M-->>B: New access token
    end
```

## Terminal Session Lifecycle

```mermaid
sequenceDiagram
    autonumber
    
    participant B as 🌐 Browser
    participant A as ⚡ API Server
    participant V as 📡 Valkey
    participant G as 🐍 Gateway
    participant T as 🖥️ TN3270 Host

    rect rgb(40, 60, 40)
        Note over B,T: Session Creation
        B->>+A: WebSocket Connect<br/>/terminal/:sessionId?token=xxx
        A->>A: Validate JWT
        A->>-A: Create session record

        B->>+A: session.create message
        A->>V: PUBLISH gateway.control
        V->>+G: MESSAGE
        G->>+T: connect(host, port)
        G->>G: Subscribe to tn3270.input/:id
        G->>V: PUBLISH tn3270.output/:id<br/>(session.created)
        V->>A: MESSAGE
        A-->>-B: session.created message
    end

    rect rgb(40, 50, 60)
        Note over B,T: Data Exchange
        B->>A: data message (keystroke)
        A->>V: PUBLISH tn3270.input/:id
        V->>G: MESSAGE
        G->>T: send(data)
        T->>G: receive(output)
        G->>V: PUBLISH tn3270.output/:id
        V->>A: MESSAGE
        A->>B: data message (output)
    end

    rect rgb(50, 50, 40)
        Note over B,T: Navigation Away (Session Persists)
        B->>A: WebSocket Close
        Note over A,G: Session remains active<br/>No destroy message sent
        B->>B: Navigate to /history
    end

    rect rgb(40, 50, 60)
        Note over B,T: Navigate Back (Reconnect)
        B->>+A: WebSocket Connect<br/>/terminal/:sessionId?token=xxx
        A->>A: Validate JWT
        A->>V: SUBSCRIBE tn3270.output/:id
        Note over A,G: Reconnect to existing session
        A-->>-B: Receive buffered output
    end

    rect rgb(60, 40, 40)
        Note over B,T: Explicit Session Close (Tab Close)
        B->>A: session.destroy message
        A->>V: PUBLISH gateway.control
        V->>G: MESSAGE
        G->>T: disconnect
        deactivate T
        G->>G: Unsubscribe channels
        deactivate G
        G->>V: PUBLISH tn3270.output/:id<br/>(session.destroyed)
    end
```

## AST Execution Flow

```mermaid
sequenceDiagram
    autonumber
    
    participant B as 🌐 Browser
    participant A as ⚡ API Server
    participant V as 📡 Valkey
    participant G as 🐍 Gateway
    participant T as 🖥️ TN3270 Host
    participant DB as 💾 DynamoDB

    rect rgb(40, 50, 60)
        Note over B,DB: AST Execution Start
        B->>A: ast.run {name: "login", params: {...}}
        A->>V: PUBLISH tn3270.input/:id
        V->>G: MESSAGE
        G->>DB: PutItem (Executions) - status: running
        G->>V: PUBLISH tn3270.output/:id (ast.status: running)
        V->>A: MESSAGE
        A->>B: ast.status {status: running}
    end

    rect rgb(40, 60, 50)
        Note over B,DB: Policy Processing Loop
        loop For each policy
            G->>T: Execute TN3270 commands
            T->>G: Response
            G->>DB: PutItem (Policies)
            G->>V: PUBLISH tn3270.output/:id (ast.item_result)
            V->>A: MESSAGE
            A->>B: ast.item_result {itemId, status}
            G->>V: PUBLISH tn3270.output/:id (ast.progress)
            V->>A: MESSAGE
            A->>B: ast.progress {current, total}
        end
    end

    rect rgb(40, 50, 60)
        Note over B,DB: AST Completion
        G->>DB: UpdateItem (Executions) - status: success
        G->>V: PUBLISH tn3270.output/:id (ast.status: success)
        V->>A: MESSAGE
        A->>B: ast.status {status: success, duration}
    end
```

## Message Flow

```mermaid
flowchart LR
    subgraph Browser["` **Browser** `"]
        XT["`📺 **xterm.js**`"]
        AST["`🔧 **AST Panel**`"]
    end

    subgraph API["` **API Server** `"]
        direction TB
        WSH["`🔌 WebSocket Handler`"]
        VC1["`Valkey Client`"]
    end

    subgraph Valkey["` **Valkey Pub/Sub** `"]
        direction TB
        GC["`📣 gateway.control`"]
        PI["`⌨️ tn3270.input.*`"]
        PO["`📤 tn3270.output.*`"]
        PC["`🎛️ tn3270.control.*`"]
    end

    subgraph Gateway["` **Python Gateway** `"]
        direction TB
        VC2["`Valkey Client`"]
        PM["`🔧 TN3270 Manager`"]
        AE["`🤖 AST Engine`"]
        PTY["`🖥️ TN3270 Host`"]
    end

    XT -->|"`_session.create_
    _data_
    _resize_`"| WSH
    AST -->|"`_ast.run_
    _ast.control_`"| WSH
    WSH -->|"`Publish`"| VC1
    VC1 --> GC & PI & PC
    
    GC & PI & PC -->|"`Subscribe`"| VC2
    
    VC2 <--> PM & AE
    PM <--> PTY
    AE <--> PM
    PM -->|"`Publish`"| VC2
    AE -->|"`Publish`"| VC2
    VC2 --> PO
    
    PO -->|"`Subscribe`"| VC1
    VC1 --> WSH
    WSH -->|"`_session.created_
    _data_
    _ast.status_
    _ast.progress_`"| XT & AST
```

## Component Dependencies

```mermaid
flowchart BT
    subgraph Packages["` **📦 Packages** `"]
        Shared["`**@terminal/shared**
        _Types & Utils_`"]
    end

    subgraph Apps["` **🚀 Apps** `"]
        Web["`**@terminal/web**
        _React + Zustand_`"]
        API["`**@terminal/api**
        _Fastify Backend_`"]
    end

    subgraph External["` **🔧 External** `"]
        Gateway["`**gateway**
        _Python TN3270_`"]
        Valkey["`**Valkey**
        _Docker_`"]
        DynamoDB["`**DynamoDB**
        _AWS/Local_`"]
        Mainframe["`**Mainframe**
        _TN3270 Host_`"]
    end

    Web --> Shared
    API --> Shared
    API <--> Valkey <--> Gateway
    API --> DynamoDB
    Gateway --> DynamoDB
    Gateway --> Mainframe
    Web --> API
```

## State Management

```mermaid
stateDiagram-v2
    direction LR
    
    [*] --> Disconnected
    
    Disconnected --> Connecting: connect()
    Connecting --> Connected: WebSocket open
    Connecting --> Error: Connection failed
    
    Connected --> Disconnected: disconnect()
    Connected --> Reconnecting: Connection lost
    Connected --> Error: Fatal error
    
    Reconnecting --> Connected: ✅ Reconnect success
    Reconnecting --> Error: ❌ Max retries exceeded
    
    Error --> Connecting: 🔄 Retry
    Error --> [*]: Give up

    note right of Connected
        Active terminal session
        Sending/receiving data
        Session persists on navigation
    end note

    note left of Reconnecting
        Auto-reconnect with
        exponential backoff
    end note
```

## TN3270 Session States

```mermaid
stateDiagram-v2
    direction TB

    [*] --> Creating: session.create received

    Creating --> Active: ✅ connect success
    Creating --> Failed: ❌ connection error

    state Active {
        direction LR
        [*] --> Idle
        Idle --> Running: ast.run
        Running --> Running: I/O operations
        Running --> Paused: ast.control(pause)
        Paused --> Running: ast.control(resume)
        Running --> Idle: ast complete
        Idle --> Idle: data I/O
    }

    Active --> WebSocketDisconnected: WS close (navigation)
    WebSocketDisconnected --> Active: WS reconnect
    
    Active --> Destroying: session.destroy (tab close)
    WebSocketDisconnected --> Destroying: session.destroy

    Destroying --> Cleanup: disconnect sent
    Cleanup --> [*]: Resources freed

    Failed --> [*]: Error sent to client
```

## AWS Deployment Architecture (Production)

```mermaid
flowchart TB
    subgraph Users["` **👥 Users** `"]
        U1["`👤 User 1`"]
        U2["`👤 User 2`"]
        UN["`👤 User N`"]
    end

    subgraph AWS["` **☁️ AWS Cloud** `"]
        subgraph VPC["` **VPC** `"]
            subgraph PublicSubnet["` **Public Subnets** `"]
                ALB["`**Application Load Balancer**
                _HTTPS + WebSocket_
                _Sticky Sessions_`"]
            end

            subgraph PrivateSubnet["` **Private Subnets** `"]
                subgraph ECSAPI["` **ECS Cluster (API)** `"]
                    API1["`API Task 1`"]
                    API2["`API Task 2`"]
                end

                subgraph EC2Gateway["` **EC2 Auto Scaling** `"]
                    GW1["`Gateway Instance 1
                    _(10 sessions)_`"]
                    GW2["`Gateway Instance 2
                    _(10 sessions)_`"]
                end

                ElastiCache["`**ElastiCache**
                _(Valkey/Redis)_`"]
            end
        end

        DynamoDB2["`**DynamoDB**
        _(On-Demand)_`"]
        
        S3["`**S3 + CloudFront**
        _(Static Assets)_`"]
    end

    subgraph OnPrem["` **On-Premises / Direct Connect** `"]
        Mainframe2["`🖥️ **Mainframe**
        _(TN3270)_`"]
    end

    U1 & U2 & UN --> S3
    U1 & U2 & UN --> ALB

    ALB --> API1 & API2
    API1 & API2 <--> ElastiCache
    API1 & API2 --> DynamoDB2
    
    ElastiCache <--> GW1 & GW2
    GW1 & GW2 --> DynamoDB2
    GW1 & GW2 -->|"`Direct Connect / VPN`"| Mainframe2
```

## Development Architecture

```mermaid
flowchart TB
    subgraph Dev["` **Development Environment** `"]
        subgraph Local["` **localhost** `"]
            WebDev["`**Vite Dev Server**
            _:5173_`"]
            APIDev["`**Fastify**
            _:3001_`"]
            GatewayDev["`**Python Gateway**
            _asyncio_`"]
        end

        subgraph Docker["` **Docker Compose** `"]
            ValkeyDev["`**Valkey**
            _:6379_`"]
            DynamoDBLocal["`**DynamoDB Local**
            _:8042_`"]
        end

        subgraph External2["` **External** `"]
            TK4["`**TK4- Mainframe**
            _(Hercules)_
            _:3270_`"]
        end
    end

    WebDev -->|"`HTTP/WS`"| APIDev
    APIDev <--> ValkeyDev <--> GatewayDev
    APIDev --> DynamoDBLocal
    GatewayDev --> DynamoDBLocal
    GatewayDev -->|"`TN3270`"| TK4
```
