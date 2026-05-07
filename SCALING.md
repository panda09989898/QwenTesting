# Scaling Guide for CollabNotes

This guide explains how to scale the application from development to production with 10,000+ concurrent users.

## Current Architecture Limitations

The current implementation uses:
- SQLite (single-file database)
- In-memory WebSocket connection tracking
- Single-instance deployment

These work well for development and small-scale deployments but need changes for high concurrency.

## Phase 1: Database Upgrade (100-1,000 users)

### Replace SQLite with PostgreSQL

```python
# Update DATABASE_URL in environment
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/collabnotes
```

### Install asyncpg driver
```bash
pip install asyncpg
```

### Update requirements.txt
```
asyncpg==0.29.0
```

### Benefits
- Better concurrency (MVCC)
- Connection pooling
- Better query optimization
- Horizontal read scaling with replicas

## Phase 2: WebSocket Scaling (1,000-5,000 users)

### Problem
Current WebSocket manager stores connections in memory. Multiple backend instances won't share state.

### Solution: Redis Pub/Sub

```python
# Add to requirements.txt
redis==5.0.1
aioredis==2.0.1

# New service: services/websocket_pubsub.py
import aioredis
import json

class RedisWebSocketManager:
    def __init__(self, redis_url: str):
        self.redis = aioredis.from_url(redis_url)
        
    async def publish(self, channel: str, message: dict):
        await self.redis.publish(channel, json.dumps(message))
        
    async def subscribe(self, channel: str):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        return pubsub
```

### Implementation Steps
1. Deploy Redis instance
2. Replace in-memory `ws_manager` with Redis-backed version
3. Each backend instance subscribes to document channels
4. Broadcast messages via Redis Pub/Sub

## Phase 3: Load Balancing (5,000-10,000 users)

### Architecture
```
                    ┌─────────────┐
                    │   Nginx/    │
Users ─────────────►│   HAProxy   │
                    │   (LB)      │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
    │Backend 1│      │Backend 2│      │Backend N│
    └────┬────┘      └────┬────┘      └────┬────┘
         │                │                │
         └────────────────┼────────────────┘
                          │
                    ┌─────▼─────┐
                    │   Redis   │
                    │  Cluster  │
                    └───────────┘
```

### Sticky Sessions Required
WebSockets require sticky sessions so a user's reconnects go to the same backend.

### Nginx Configuration
```nginx
upstream backend {
    ip_hash;  # Sticky sessions by IP
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
}
```

## Phase 4: Performance Optimizations

### 1. Message Compression
```python
import msgpack
import gzip

# Compress WebSocket messages
def compress_message(msg: dict) -> bytes:
    packed = msgpack.packb(msg)
    return gzip.compress(packed)

# Decompress on receive
def decompress_message(data: bytes) -> dict:
    unpacked = gzip.decompress(data)
    return msgpack.unpackb(unpacked)
```

### 2. Delta Operations
Instead of sending full content, send only changes:

```python
# Use diff-match-patch or similar
from difflib import SequenceMatcher

def compute_delta(old: str, new: str) -> list:
    matcher = SequenceMatcher(None, old, new)
    return matcher.get_opcodes()
```

### 3. Operation Batching
```python
# Batch multiple operations before broadcasting
class OperationBatcher:
    def __init__(self, batch_size=10, timeout_ms=50):
        self.batch = []
        self.batch_size = batch_size
        self.timeout_ms = timeout_ms
        
    async def add_operation(self, op):
        self.batch.append(op)
        if len(self.batch) >= self.batch_size:
            await self.flush()
            
    async def flush(self):
        if self.batch:
            await self.broadcast(self.batch)
            self.batch = []
```

### 4. Database Query Optimization
```python
# Add indexes
CREATE INDEX idx_documents_owner_updated ON documents(owner_id, updated_at DESC);
CREATE INDEX idx_versions_doc_created ON document_versions(document_id, created_at DESC);

# Use connection pooling
engine = create_async_engine(
    DATABASE_URL,
    pool_size=50,
    max_overflow=100,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

## Phase 5: Monitoring & Observability

### Metrics to Track
```python
# Add Prometheus metrics
from prometheus_fastapi_instrumentator import Instrumentator

instrumentator.expose(app)

# Key metrics:
# - http_request_duration_seconds
# - websocket_connections_total
# - operation_latency_seconds
# - db_query_duration_seconds
```

### Logging Aggregation
- Use structured logging (JSON format)
- Ship logs to ELK stack or Loki
- Set up alerts for error rates

### Distributed Tracing
```python
# Add OpenTelemetry
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

FastAPIInstrumentor.instrument_app(app)
```

## Production Deployment Checklist

### Infrastructure
- [ ] PostgreSQL database with backups
- [ ] Redis cluster for caching and pub/sub
- [ ] Load balancer with SSL termination
- [ ] Multiple backend instances (min 3)
- [ ] CDN for static assets
- [ ] Database connection pooling (PgBouncer)

### Security
- [ ] HTTPS everywhere
- [ ] WAF (Web Application Firewall)
- [ ] DDoS protection
- [ ] Rate limiting per user + per IP
- [ ] Regular security audits
- [ ] Secrets management (Vault/AWS Secrets Manager)

### Reliability
- [ ] Health checks on all services
- [ ] Auto-scaling based on CPU/memory
- [ ] Circuit breakers for external services
- [ ] Graceful shutdown handling
- [ ] Database replication and failover
- [ ] Regular backup testing

### Performance Targets
- API response time: < 100ms (p95)
- WebSocket latency: < 50ms (p95)
- Sync delay: < 200ms end-to-end
- Availability: 99.9% uptime

## Cost Estimation (10,000 concurrent users)

| Resource | Specification | Monthly Cost |
|----------|--------------|--------------|
| Backend Instances | 4x 4GB RAM, 2 vCPU | $160 |
| PostgreSQL | 8GB RAM, managed | $150 |
| Redis | 2GB RAM, managed | $50 |
| Load Balancer | Basic tier | $20 |
| Bandwidth | 1TB estimated | $100 |
| **Total** | | **~$480/month** |

*Costs vary by provider (AWS, GCP, DigitalOcean, Railway)*

## Horizontal Scaling Strategy

### When to Scale
- CPU usage > 70% sustained
- Memory usage > 80%
- WebSocket connection count approaching limit
- Increased latency percentiles

### Auto-scaling Rules
```yaml
# Example Kubernetes HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## Disaster Recovery

### Backup Strategy
- Database: Continuous WAL archiving + daily snapshots
- Redis: RDB snapshots every hour
- Config: Version controlled in Git

### Recovery Time Objective (RTO): < 1 hour
### Recovery Point Objective (RPO): < 15 minutes

### Failover Procedure
1. Detect failure via health checks
2. Route traffic to healthy instances
3. Promote read replica if primary fails
4. Spin up replacement instances
5. Investigate root cause

## Contact & Support

For scaling questions or issues:
- Review monitoring dashboards first
- Check application logs
- Profile slow queries
- Consider vertical scaling before horizontal
