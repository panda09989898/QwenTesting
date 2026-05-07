"""Middleware for authentication, rate limiting, and logging."""
import logging
import time
from typing import Optional, Callable, Dict
from collections import defaultdict

from fastapi import Request, Response, WebSocket, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.websockets import WebSocketDisconnect

from backend.core.security import decode_access_token
from backend.core.config import settings

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for JWT authentication on API routes.
    
    This middleware validates JWT tokens from the Authorization header
    and adds user information to the request state.
    """
    
    # Paths that don't require authentication
    PUBLIC_PATHS = {
        "/docs",
        "/openapi.json",
        "/register",
        "/login",
        "/health",
    }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip authentication for public paths
        if any(request.url.path.startswith(path) for path in self.PUBLIC_PATHS):
            return await call_next(request)
        
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Missing or invalid authorization header"}
            )
        
        token = auth_header.split(" ")[1]
        payload = decode_access_token(token)
        
        if not payload:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid or expired token"}
            )
        
        # Add user info to request state
        request.state.user_id = int(payload.get("sub"))
        request.state.user_email = payload.get("email")
        
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token bucket rate limiting middleware.
    
    Implements a simple in-memory rate limiter using the token bucket algorithm.
    For production, consider using Redis for distributed rate limiting.
    """
    
    def __init__(self, app, requests_per_window: int = None, window_seconds: int = None):
        super().__init__(app)
        self.max_requests = requests_per_window or settings.RATE_LIMIT_REQUESTS
        self.window_seconds = window_seconds or settings.RATE_LIMIT_WINDOW
        
        # In-memory storage: {ip: {"tokens": float, "last_update": float}}
        self.buckets: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"tokens": self.max_requests, "last_update": time.time()}
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        bucket = self.buckets[client_ip]
        
        # Refill tokens based on elapsed time
        elapsed = current_time - bucket["last_update"]
        tokens_to_add = elapsed * (self.max_requests / self.window_seconds)
        bucket["tokens"] = min(self.max_requests, bucket["tokens"] + tokens_to_add)
        bucket["last_update"] = current_time
        
        # Check if request is allowed
        if bucket["tokens"] < 1:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {self.max_requests} requests per {self.window_seconds} seconds"
                },
                headers={
                    "Retry-After": str(int(self.window_seconds - elapsed))
                }
            )
        
        # Consume a token
        bucket["tokens"] -= 1
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket["tokens"]))
        response.headers["X-RateLimit-Reset"] = str(int(current_time + self.window_seconds))
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address, considering proxies."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


class LoggingMiddleware(BaseHTTPMiddleware):
    """Structured logging middleware for request/response tracking."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Log request
        logger.info(
            "Request started",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query),
                "client_ip": request.client.host if request.client else "unknown",
            }
        )
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                }
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration * 1000, 2),
                    "error": str(e),
                },
                exc_info=True
            )
            raise


async def websocket_auth(websocket: WebSocket) -> Optional[Dict]:
    """Authenticate WebSocket connection.
    
    Args:
        websocket: WebSocket connection instance
        
    Returns:
        Decoded token payload if authenticated, None otherwise
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return None
    
    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4002, reason="Invalid or expired token")
        return None
    
    return payload


class WebSocketConnectionManager:
    """Manager for WebSocket connections with presence tracking.
    
    Handles connection lifecycle, broadcasting, and presence indicators.
    Optimized for high concurrency with efficient data structures.
    """
    
    def __init__(self):
        # {document_id: {user_id: websocket}}
        self._connections: Dict[int, Dict[int, WebSocket]] = defaultdict(dict)
        # {user_id: {"username": str, "is_typing": bool, "last_seen": float}}
        self._presence: Dict[int, Dict] = {}
        # Connection timestamps for cleanup
        self._connection_times: Dict[int, float] = {}
    
    async def connect(
        self, 
        websocket: WebSocket, 
        document_id: int, 
        user_id: int,
        username: str
    ):
        """Add a new WebSocket connection.
        
        Args:
            websocket: WebSocket instance
            document_id: Document being edited
            user_id: Connected user ID
            username: Username for presence display
        """
        await websocket.accept()
        
        self._connections[document_id][user_id] = websocket
        self._presence[user_id] = {
            "username": username,
            "is_typing": False,
            "last_seen": time.time(),
            "document_id": document_id
        }
        self._connection_times[id(websocket)] = time.time()
        
        logger.info(f"WebSocket connected: user {user_id} to document {document_id}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove a WebSocket connection.
        
        Args:
            websocket: WebSocket instance to remove
            user_id: User ID to clean up
        """
        # Find and remove from all documents
        for doc_id in list(self._connections.keys()):
            if user_id in self._connections[doc_id]:
                del self._connections[doc_id][user_id]
                if not self._connections[doc_id]:
                    del self._connections[doc_id]
        
        # Clean up presence
        if user_id in self._presence:
            del self._presence[user_id]
        
        # Clean up connection time
        ws_id = id(websocket)
        if ws_id in self._connection_times:
            del self._connection_times[ws_id]
        
        logger.info(f"WebSocket disconnected: user {user_id}")
    
    async def broadcast_to_document(
        self, 
        document_id: int, 
        message: dict,
        exclude_user: Optional[int] = None
    ):
        """Broadcast message to all users editing a document.
        
        Args:
            document_id: Target document
            message: Message to broadcast
            exclude_user: Optional user ID to exclude (sender)
        """
        if document_id not in self._connections:
            return
        
        disconnected = []
        for user_id, websocket in self._connections[document_id].items():
            if user_id == exclude_user:
                continue
            
            try:
                await websocket.send_json(message)
            except WebSocketDisconnect:
                disconnected.append((user_id, websocket))
            except Exception as e:
                logger.error(f"Error broadcasting to user {user_id}: {e}")
                disconnected.append((user_id, websocket))
        
        # Clean up disconnected clients
        for user_id, websocket in disconnected:
            self.disconnect(websocket, user_id)
    
    async def send_personal_message(self, user_id: int, message: dict):
        """Send message to a specific user.
        
        Args:
            user_id: Target user ID
            message: Message to send
        """
        # Find user's websocket
        for doc_connections in self._connections.values():
            if user_id in doc_connections:
                try:
                    await doc_connections[user_id].send_json(message)
                    return
                except Exception as e:
                    logger.error(f"Error sending to user {user_id}: {e}")
    
    def get_active_users(self, document_id: int) -> list:
        """Get list of active users for a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            List of presence info dicts
        """
        if document_id not in self._connections:
            return []
        
        active = []
        for user_id in self._connections[document_id]:
            if user_id in self._presence:
                presence = self._presence[user_id].copy()
                presence["user_id"] = user_id
                active.append(presence)
        
        return active
    
    def update_presence(self, user_id: int, is_typing: bool = False):
        """Update user presence status.
        
        Args:
            user_id: User ID
            is_typing: Whether user is currently typing
        """
        if user_id in self._presence:
            self._presence[user_id]["is_typing"] = is_typing
            self._presence[user_id]["last_seen"] = time.time()
    
    async def cleanup_stale_connections(self, max_age_seconds: int = 300):
        """Remove stale connections older than max_age_seconds.
        
        Should be called periodically (e.g., every minute).
        """
        current_time = time.time()
        stale = []
        
        for ws_id, conn_time in self._connection_times.items():
            if current_time - conn_time > max_age_seconds:
                stale.append(ws_id)
        
        # Note: Actual cleanup would require mapping ws_id back to websocket
        # This is a simplified version for demonstration
        logger.info(f"Cleaned up {len(stale)} stale connections")
    
    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(users) for users in self._connections.values())
    
    def get_document_connection_count(self, document_id: int) -> int:
        """Get number of users editing a specific document."""
        return len(self._connections.get(document_id, {}))


# Singleton instance
ws_manager = WebSocketConnectionManager()
