# CollabNotes - Real-time Collaborative Note Editor

A production-quality real-time collaborative note editor similar to Google Docs.

## Features

### Backend (FastAPI + Python)
- ✅ JWT authentication with bcrypt password hashing
- ✅ WebSocket-based real-time sync
- ✅ Document version history with immutable snapshots
- ✅ OT-inspired conflict resolution with vector clocks
- ✅ Rate limiting middleware (token bucket algorithm)
- ✅ SQLite with async SQLAlchemy ORM
- ✅ Clean architecture: routes/, services/, repositories/, models/, middleware/

### Frontend (React + TypeScript)
- ✅ Live collaborative editing with optimistic UI updates
- ✅ Presence indicators showing active users and typing status
- ✅ Auto-reconnect with exponential backoff for WebSockets
- ✅ Dark mode toggle with persistent preference
- ✅ Zustand for state management
- ✅ TailwindCSS for styling

### API Endpoints
- `POST /auth/register` - Register new user
- `POST /auth/login` - Authenticate and get JWT token
- `GET /documents` - List user's documents
- `POST /documents` - Create new document
- `GET /documents/{id}` - Get document by ID
- `PUT /documents/{id}` - Update document
- `DELETE /documents/{id}` - Delete document
- `GET /documents/{id}/versions` - Get version history
- `POST /documents/{id}/versions/{vid}/restore` - Restore version
- `WebSocket /documents/ws/{id}` - Real-time collaboration

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (optional)

### Local Development

#### Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run with uvicorn
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Start development server
npm run dev
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Deploy to Railway

Railway is recommended for deploying this application due to full WebSocket support.

### Option 1: One-Click Deploy

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/collabnotes)

### Option 2: Manual Deploy

1. **Install Railway CLI**
   ```bash
   npm install -g @railway/cli
   railway login
   ```

2. **Initialize Project**
   ```bash
   railway init
   ```

3. **Add Services**
   ```bash
   # Add backend service
   railway add --name backend
   
   # Add frontend service
   railway add --name frontend
   ```

4. **Set Environment Variables**
   ```bash
   # Backend variables
   railway variables set SECRET_KEY=your-secret-key-here
   railway variables set DATABASE_URL=sqlite+aiosqlite:///./collab_notes.db
   railway variables set CORS_ORIGINS=["https://your-frontend.railway.app"]
   
   # Frontend variables
   railway variables set VITE_API_URL=https://your-backend.railway.app
   railway variables set VITE_WS_URL=wss://your-backend.railway.app
   ```

5. **Deploy**
   ```bash
   railway up
   ```

### Railway Configuration

The project includes `railway.toml` with automatic configuration:

```toml
[backend]
buildCommand = "pip install -r requirements.txt"
startCommand = "uvicorn backend.main:app --host 0.0.0.0 --port $PORT"
watchPatterns = ["backend/**/*", "requirements.txt"]

[frontend]
buildCommand = "npm install && npm run build"
startCommand = "npx serve dist"
watchPatterns = ["frontend/**/*", "package.json"]
```

## Architecture

### Backend Architecture

```
backend/
├── main.py                 # FastAPI app factory
├── core/
│   ├── config.py          # Settings & configuration
│   └── security.py        # JWT & password hashing
├── models/                # SQLAlchemy ORM models
├── repositories/          # Data access layer
├── services/              # Business logic layer
├── routes/                # API endpoints
├── schemas/               # Pydantic models
└── middleware/            # Auth, rate limiting, logging
```

### Key Design Decisions

1. **Repository Pattern**: Abstracts database operations, making testing easier
2. **Service Layer**: Contains business logic, separate from routes
3. **Dependency Injection**: FastAPI's Depends() for clean DI
4. **Async/Await**: Full async stack for better concurrency
5. **WebSocket Manager**: Centralized connection management

### Conflict Resolution

Uses Operational Transformation (OT) inspired approach:
- Vector clocks for operation ordering
- Transform concurrent operations
- Optimistic UI with server reconciliation

## Performance Optimizations

### For 10,000 Concurrent Users

1. **WebSocket Optimization**
   - Connection pooling
   - Binary message format (MessagePack)
   - Delta compression for operations
   - Selective broadcasting

2. **Database Optimization**
   - Connection pooling (20 connections, 40 max overflow)
   - Indexed queries on frequently accessed fields
   - Async I/O to prevent blocking

3. **Caching Strategy**
   - Redis for session storage (production)
   - In-memory presence tracking
   - Document content caching

4. **Horizontal Scaling**
   - Stateless backend instances
   - Redis pub/sub for cross-instance messaging
   - Load balancer with sticky sessions

### Bandwidth Optimization

- Send only delta operations, not full content
- Compress WebSocket messages
- Throttle cursor updates (100ms intervals)
- Batch multiple operations

### Latency Optimization

- Edge deployment for global users
- WebSocket keep-alive (30s ping)
- Optimistic UI updates
- Connection pre-warming

## Security Review

### Identified Vulnerabilities & Mitigations

| Vulnerability | Risk | Mitigation |
|--------------|------|------------|
| XSS in document content | High | Content sanitization, CSP headers |
| CSRF attacks | Medium | JWT in Authorization header, not cookies |
| SQL Injection | High | Parameterized queries via SQLAlchemy |
| Rate Limiting Bypass | Medium | IP-based + user-based limiting |
| WebSocket Hijacking | High | Token authentication on connect |
| JWT Token Theft | High | Short expiry (30min), HTTPS only |
| Information Disclosure | Low | Proper error handling, no stack traces |

### Secure Coding Improvements

1. **Input Validation**
   - Pydantic schemas for all inputs
   - Length limits on text fields
   - Email validation

2. **Authentication**
   - Bcrypt password hashing (cost factor 12)
   - JWT with expiration
   - Token refresh mechanism

3. **Authorization**
   - Permission checks on all document operations
   - Owner-only deletion
   - Collaborator permission levels

4. **Rate Limiting**
   - Token bucket algorithm
   - Different limits for auth vs regular endpoints
   - Per-IP and per-user tracking

## Testing

### Run Tests

```bash
# Backend unit tests
cd backend
pytest tests/test_services.py -v

# Backend integration tests
pytest tests/test_integration.py -v

# With coverage
pytest --cov=backend --cov-report=html
```

### Test Coverage

- UserService: Registration, authentication
- DocumentService: CRUD operations, permissions
- ConflictResolutionService: OT operations, vector clocks
- API Endpoints: Auth flow, document operations

## Bug Fix: merge_changes Function

### Original Buggy Code

```python
def merge_changes(old, new):
    result = {}
    for k in old:
        result[k] = old[k]

    for k in new:
        if type(new[k]) == dict:
            result[k] = merge_changes(result[k], new[k])
        else:
            result[k] = new[k]

    return result
```

### Bugs Identified

1. **KeyError**: Accesses `result[k]` without checking if key exists in old
2. **Type Check**: Uses `type(x) == dict` instead of `isinstance()`
3. **Mutable Reference**: Directly assigns nested dicts, causing mutation issues
4. **None Handling**: Crashes if old or new is None
5. **List Handling**: Doesn't handle lists or other collection types
6. **Deep Copy**: No deep copy, leading to shared references

### Fixed Implementation

```python
import copy
from typing import Any, Dict

def merge_changes(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safely merge two dictionaries with proper handling of edge cases.
    
    Args:
        old: Original dictionary
        new: Dictionary with changes to apply
        
    Returns:
        New merged dictionary without mutating inputs
    """
    # Handle None inputs
    if old is None:
        old = {}
    if new is None:
        new = {}
        
    # Validate input types
    if not isinstance(old, dict) or not isinstance(new, dict):
        raise TypeError("Both arguments must be dictionaries")
    
    # Create deep copy to avoid mutation
    result = copy.deepcopy(old)
    
    for key, new_value in new.items():
        if key in result:
            old_value = result[key]
            
            # Recursively merge nested dicts
            if isinstance(old_value, dict) and isinstance(new_value, dict):
                result[key] = merge_changes(old_value, new_value)
            # Handle lists - replace entirely (could be customized)
            elif isinstance(new_value, list):
                result[key] = copy.deepcopy(new_value)
            else:
                # Simple value - replace
                result[key] = copy.deepcopy(new_value)
        else:
            # New key - add with deep copy
            result[key] = copy.deepcopy(new_value)
    
    return result
```

### Edge Cases Handled

- Empty dictionaries
- None values
- Nested structures
- Mixed types (dict, list, primitives)
- New keys not in original
- Type mismatches between old and new

## Tradeoff Analysis

### Database Choice: SQLite vs PostgreSQL

| Aspect | SQLite | PostgreSQL |
|--------|--------|------------|
| Setup Complexity | Low | Medium |
| Concurrency | Limited | Excellent |
| Scalability | Single node | Horizontal |
| Maintenance | Minimal | Requires DBA |
| Best For | Dev/Small prod | Large scale |

**Decision**: SQLite for simplicity, but PostgreSQL recommended for production with >1000 concurrent users.

### WebSocket vs HTTP Polling

| Aspect | WebSocket | HTTP Polling |
|--------|-----------|--------------|
| Latency | Real-time | Delayed |
| Bandwidth | Efficient | Wasteful |
| Complexity | Higher | Lower |
| Scaling | Challenging | Easy |

**Decision**: WebSocket for real-time collaboration, essential for Google Docs-like experience.

### State Management: Zustand vs Redux

| Aspect | Zustand | Redux |
|--------|---------|-------|
| Bundle Size | ~1KB | ~8KB |
| Boilerplate | Minimal | Significant |
| Learning Curve | Low | Medium |
| DevTools | Basic | Excellent |

**Decision**: Zustand for simplicity and small bundle size.

## Monitoring & Observability

### Health Checks
- `/health` - Application health endpoint
- Structured logging with request IDs
- Error tracking with stack traces

### Metrics to Track
- WebSocket connection count
- Operation latency (p50, p95, p99)
- Database query performance
- Rate limit hits
- Authentication failures

## Future Enhancements

1. **Rich Text Editing**
   - Quill.js or TipTap integration
   - Formatting operations
   - Image/file attachments

2. **Advanced Collaboration**
   - Comments and suggestions
   - User mentions
   - Activity feed

3. **Mobile Support**
   - React Native app
   - Touch-optimized editor
   - Offline sync

4. **Enterprise Features**
   - SSO integration
   - Audit logs
   - Document templates
   - Team workspaces

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: [Create an issue]
- Documentation: `/docs` endpoint on running server
