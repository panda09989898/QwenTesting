"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ============== User Schemas ==============

class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, max_length=100)


class UserResponse(UserBase):
    """Schema for user response (excludes sensitive data)."""
    id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Schema for authentication token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Schema for decoded token data."""
    user_id: Optional[int] = None
    email: Optional[str] = None


# ============== Document Schemas ==============

class DocumentBase(BaseModel):
    """Base document schema."""
    title: str = Field(default="Untitled Document", max_length=255)
    content: str = Field(default="")


class DocumentCreate(DocumentBase):
    """Schema for creating a new document."""
    pass


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None


class DocumentResponse(DocumentBase):
    """Schema for document response."""
    id: int
    owner_id: int
    version: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """Schema for paginated document list."""
    documents: List[DocumentResponse]
    total: int
    page: int
    page_size: int


# ============== Version History Schemas ==============

class DocumentVersionBase(BaseModel):
    """Base version schema."""
    content: str
    change_summary: Optional[str] = Field(None, max_length=500)


class DocumentVersionResponse(BaseModel):
    """Schema for version history response."""
    id: int
    document_id: int
    creator_id: int
    version_number: int
    content: str
    change_summary: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class VersionHistoryResponse(BaseModel):
    """Schema for version history list."""
    versions: List[DocumentVersionResponse]
    current_version: int


# ============== WebSocket Schemas ==============

class OperationType(str):
    """Enumeration of operation types."""
    INSERT = "insert"
    DELETE = "delete"
    UPDATE = "update"
    CURSOR = "cursor"
    PRESENCE = "presence"


class TextOperation(BaseModel):
    """Schema for text editing operations."""
    type: OperationType
    position: int
    text: str = ""
    length: int = 0
    timestamp: datetime
    user_id: int
    vector_clock: Dict[str, int]


class CursorPosition(BaseModel):
    """Schema for cursor position updates."""
    user_id: int
    username: str
    position: int
    selection_start: Optional[int] = None
    selection_end: Optional[int] = None
    color: str = "#3B82F6"


class PresenceUpdate(BaseModel):
    """Schema for presence/typing indicators."""
    user_id: int
    username: str
    is_typing: bool = False
    last_seen: datetime


class WebSocketMessage(BaseModel):
    """Schema for WebSocket messages."""
    type: str  # 'operation', 'cursor', 'presence', 'sync', 'error'
    data: Dict[str, Any]
    document_id: int
    user_id: int
    timestamp: datetime


class SyncRequest(BaseModel):
    """Schema for sync requests."""
    document_id: int
    base_version: int
    operations: Optional[List[TextOperation]] = None


class SyncResponse(BaseModel):
    """Schema for sync responses."""
    document_id: int
    current_version: int
    content: str
    operations: List[TextOperation]
    active_users: List[PresenceUpdate]


# ============== Error Schemas ==============

class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str
    message: str
    detail: Optional[Any] = None
    code: Optional[str] = None


class ValidationErrorDetail(BaseModel):
    """Schema for validation error details."""
    loc: List[str]
    msg: str
    type: str
