"""
Real-time Collaborative Note Editor - Backend

Architecture Overview:
======================
This application follows Clean Architecture principles with clear separation of concerns:

1. **Models Layer** (models/): Database models using SQLAlchemy ORM
2. **Schemas Layer** (schemas/): Pydantic models for request/response validation
3. **Repositories Layer** (repositories/): Data access layer, abstracting database operations
4. **Services Layer** (services/): Business logic, conflict resolution, version history
5. **Routes Layer** (routes/): API endpoints and WebSocket handlers
6. **Middleware Layer** (middleware/): Authentication, rate limiting, logging
7. **Core Layer** (core/): Configuration, security utilities, dependencies

Key Design Decisions:
=====================
1. **Conflict Resolution**: Operational Transformation (OT) inspired approach with timestamp-based
   last-write-wins for simple conflicts, with merge strategies for complex edits.

2. **WebSocket Management**: Connection pool with heartbeat mechanism for detecting stale connections.

3. **Version History**: Immutable snapshots stored with each change, enabling full audit trail.

4. **Rate Limiting**: Token bucket algorithm implemented in middleware for efficient throttling.

5. **Dependency Injection**: FastAPI's Depends() used throughout for testability and loose coupling.

Performance Optimizations:
==========================
1. **Delta Sync**: Only send changes, not full documents
2. **Batching**: Micro-batching changes within 50ms windows
3. **Connection Pooling**: Reusable database connections
4. **Async Operations**: Non-blocking I/O throughout
5. **Efficient Serialization**: ORJSON for fast JSON processing
"""

# Backend package initialization
__version__ = "1.0.0"
