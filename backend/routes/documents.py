"""API route handlers for documents."""
import logging
from datetime import datetime
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.base import get_db
from backend.services import DocumentService, ConflictResolutionService
from backend.schemas import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentListResponse,
    DocumentVersionResponse,
    VersionHistoryResponse,
    TextOperation,
    SyncRequest,
    SyncResponse,
    PresenceUpdate,
    ErrorResponse,
)
from backend.middleware import ws_manager, websocket_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


def get_document_service(session: Annotated[AsyncSession, Depends(get_db)]) -> DocumentService:
    """Dependency injection for DocumentService."""
    return DocumentService(session)


def get_conflict_service(session: Annotated[AsyncSession, Depends(get_db)]) -> ConflictResolutionService:
    """Dependency injection for ConflictResolutionService."""
    return ConflictResolutionService(session)


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_document(
    doc_data: DocumentCreate,
    service: Annotated[DocumentService, Depends(get_document_service)],
    user_id: int = Depends(lambda: 1)  # Will be set by auth middleware
) -> DocumentResponse:
    """Create a new document.
    
    Args:
        doc_data: Document creation data
        service: Injected DocumentService
        user_id: Current user ID from auth
        
    Returns:
        Created document
    """
    document = await service.create_document(doc_data, owner_id=user_id)
    return DocumentResponse.model_validate(document)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    service: Annotated[DocumentService, Depends(get_document_service)],
    page: int = Query(0, ge=0),
    page_size: int = Query(20, ge=1, le=100),
    user_id: int = Depends(lambda: 1)  # Will be set by auth middleware
) -> DocumentListResponse:
    """List all documents for the current user.
    
    Returns both owned documents and documents shared with the user.
    
    Args:
        service: Injected DocumentService
        page: Page number (0-indexed)
        page_size: Items per page
        user_id: Current user ID
        
    Returns:
        Paginated list of documents
    """
    documents, total = await service.get_user_documents(
        user_id=user_id,
        page=page,
        page_size=page_size
    )
    
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_document_service)]
) -> DocumentResponse:
    """Get a specific document by ID.
    
    Args:
        document_id: Document ID
        service: Injected DocumentService
        
    Returns:
        Document details
        
    Raises:
        HTTPException: 404 if not found
    """
    document = await service.get_document(document_id)
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    return DocumentResponse.model_validate(document)


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    doc_data: DocumentUpdate,
    service: Annotated[DocumentService, Depends(get_document_service)],
    user_id: int = Depends(lambda: 1)
) -> DocumentResponse:
    """Update a document.
    
    Args:
        document_id: Document ID
        doc_data: Update data
        service: Injected DocumentService
        user_id: Current user ID
        
    Returns:
        Updated document
        
    Raises:
        HTTPException: 404 if not found, 403 if no permission
    """
    try:
        document = await service.update_document(document_id, user_id, doc_data)
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        return DocumentResponse.model_validate(document)
    
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    service: Annotated[DocumentService, Depends(get_document_service)],
    user_id: int = Depends(lambda: 1)
):
    """Delete a document.
    
    Only the document owner can delete.
    
    Args:
        document_id: Document ID
        service: Injected DocumentService
        user_id: Current user ID
        
    Raises:
        HTTPException: 404 if not found, 403 if no permission
    """
    try:
        deleted = await service.delete_document(document_id, user_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/{document_id}/versions", response_model=VersionHistoryResponse)
async def get_version_history(
    document_id: int,
    page: int = Query(0, ge=0),
    page_size: int = Query(20, ge=1, le=50),
    service: Annotated[DocumentService, Depends(get_document_service)]
) -> VersionHistoryResponse:
    """Get version history for a document.
    
    Args:
        document_id: Document ID
        page: Page number
        page_size: Items per page
        service: Injected DocumentService
        
    Returns:
        Version history with current version number
    """
    versions, total = await service.get_version_history(
        document_id=document_id,
        page=page,
        page_size=page_size
    )
    
    # Get current document to find current version
    doc = await service.get_document(document_id)
    current_version = doc.version if doc else 1
    
    return VersionHistoryResponse(
        versions=[DocumentVersionResponse.model_validate(v) for v in versions],
        current_version=current_version
    )


@router.post("/{document_id}/versions/{version_id}/restore", response_model=DocumentResponse)
async def restore_version(
    document_id: int,
    version_id: int,
    service: Annotated[DocumentService, Depends(get_document_service)],
    user_id: int = Depends(lambda: 1)
) -> DocumentResponse:
    """Restore a document to a previous version.
    
    Args:
        document_id: Document ID
        version_id: Version ID to restore
        service: Injected DocumentService
        user_id: Current user ID
        
    Returns:
        Restored document
    """
    try:
        document = await service.restore_version(document_id, version_id, user_id)
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Version or document not found"
            )
        
        return DocumentResponse.model_validate(document)
    
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


# ============== WebSocket Real-time Collaboration ==============

@router.websocket("/ws/{document_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    document_id: int,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    conflict_service: Annotated[ConflictResolutionService, Depends(get_conflict_service)]
):
    """WebSocket endpoint for real-time collaborative editing.
    
    Handles:
    - Connection authentication
    - Operation broadcasting
    - Presence indicators
    - Cursor position updates
    - Conflict resolution
    
    Message types:
    - 'operation': Text edit operations
    - 'cursor': Cursor position updates
    - 'presence': Typing indicators
    - 'sync': Document synchronization requests
    """
    # Authenticate
    payload = await websocket_auth(websocket)
    if not payload:
        return
    
    user_id = int(payload.get("sub"))
    username = payload.get("email", f"User{user_id}")
    
    # Verify document access
    document = await document_service.get_document(document_id)
    if not document:
        await websocket.close(code=4004, reason="Document not found")
        return
    
    # Connect to room
    await ws_manager.connect(websocket, document_id, user_id, username)
    
    # Send initial sync
    active_users = ws_manager.get_active_users(document_id)
    await websocket.send_json({
        "type": "sync",
        "data": {
            "document_id": document_id,
            "content": document.content,
            "version": document.version,
            "active_users": active_users
        }
    })
    
    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")
            data = message.get("data", {})
            
            if msg_type == "operation":
                # Handle text operation
                try:
                    operation = TextOperation(**data)
                    
                    # Apply operation locally first (optimistic)
                    new_content = conflict_service.apply_operation(
                        document.content, 
                        operation
                    )
                    
                    # Broadcast to other users
                    await ws_manager.broadcast_to_document(
                        document_id=document_id,
                        message={
                            "type": "operation",
                            "data": {
                                "operation": operation.model_dump(),
                                "new_content": new_content,
                                "version": document.version + 1
                            }
                        },
                        exclude_user=user_id
                    )
                    
                    # Update presence (typing indicator)
                    ws_manager.update_presence(user_id, is_typing=True)
                    
                    # Broadcast typing indicator
                    await ws_manager.broadcast_to_document(
                        document_id=document_id,
                        message={
                            "type": "presence",
                            "data": {
                                "user_id": user_id,
                                "username": username,
                                "is_typing": True
                            }
                        },
                        exclude_user=user_id
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing operation: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "data": {"message": str(e)}
                    })
            
            elif msg_type == "cursor":
                # Handle cursor position update
                await ws_manager.broadcast_to_document(
                    document_id=document_id,
                    message={
                        "type": "cursor",
                        "data": {
                            "user_id": user_id,
                            "username": username,
                            "position": data.get("position"),
                            "selection_start": data.get("selection_start"),
                            "selection_end": data.get("selection_end")
                        }
                    },
                    exclude_user=user_id
                )
            
            elif msg_type == "presence":
                # Handle presence update (stop typing, etc.)
                is_typing = data.get("is_typing", False)
                ws_manager.update_presence(user_id, is_typing=is_typing)
                
                await ws_manager.broadcast_to_document(
                    document_id=document_id,
                    message={
                        "type": "presence",
                        "data": {
                            "user_id": user_id,
                            "username": username,
                            "is_typing": is_typing
                        }
                    },
                    exclude_user=user_id
                )
            
            elif msg_type == "sync":
                # Handle sync request
                base_version = data.get("base_version", 0)
                
                # If client is behind, send missing operations
                if base_version < document.version:
                    # For now, send full content
                    # In production, send delta operations
                    await websocket.send_json({
                        "type": "sync",
                        "data": {
                            "document_id": document_id,
                            "content": document.content,
                            "version": document.version,
                            "active_users": ws_manager.get_active_users(document_id)
                        }
                    })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up connection
        ws_manager.disconnect(websocket, user_id)
        
        # Notify others that user left
        await ws_manager.broadcast_to_document(
            document_id=document_id,
            message={
                "type": "presence",
                "data": {
                    "user_id": user_id,
                    "username": username,
                    "is_typing": False,
                    "left": True
                }
            }
        )
