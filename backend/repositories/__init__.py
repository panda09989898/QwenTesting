"""Repository implementations for all models."""
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from backend.models import User, Document, DocumentVersion, DocumentCollaborator, OperationLog
from backend.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with additional query methods."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        return await self.get_by_field("email", email)
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return await self.get_by_field("username", username)
    
    async def get_user_documents(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Document]:
        """Get all documents owned or collaborated on by a user."""
        stmt = (
            select(Document)
            .where(
                and_(
                    Document.owner_id == user_id,
                    Document.id.in_(
                        select(DocumentCollaborator.document_id)
                        .where(DocumentCollaborator.user_id == user_id)
                    )
                )
            )
            .order_by(Document.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class DocumentRepository(BaseRepository[Document]):
    """Repository for Document model with additional query methods."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Document, session)
    
    async def get_with_versions(self, id: int) -> Optional[Document]:
        """Get document with its version history."""
        stmt = (
            select(Document)
            .where(Document.id == id)
        )
        result = await self.session.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc:
            await self.session.refresh(doc, ['versions'])
        return doc
    
    async def get_user_documents(
        self, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Document]:
        """Get documents owned or shared with a user."""
        # Get owned documents
        owned_stmt = select(Document).where(Document.owner_id == user_id)
        
        # Get collaborated documents
        collab_subquery = (
            select(DocumentCollaborator.document_id)
            .where(DocumentCollaborator.user_id == user_id)
        )
        collab_stmt = select(Document).where(Document.id.in_(collab_subquery))
        
        # Combine and execute
        combined_stmt = owned_stmt.union(collab_stmt).order_by(
            Document.updated_at.desc()
        ).offset(skip).limit(limit)
        
        result = await self.session.execute(combined_stmt)
        return list(result.scalars().all())
    
    async def count_user_documents(self, user_id: int) -> int:
        """Count documents owned or shared with a user."""
        owned_count_stmt = select(func.count()).where(Document.owner_id == user_id)
        
        collab_subquery = (
            select(DocumentCollaborator.document_id)
            .where(DocumentCollaborator.user_id == user_id)
        )
        collab_count_stmt = select(func.count()).where(Document.id.in_(collab_subquery))
        
        owned_result = await self.session.execute(owned_count_stmt)
        collab_result = await self.session.execute(collab_count_stmt)
        
        return (owned_result.scalar() or 0) + (collab_result.scalar() or 0)
    
    async def increment_version(self, id: int) -> Optional[int]:
        """Increment document version number atomically."""
        doc = await self.get(id)
        if not doc:
            return None
        
        doc.version += 1
        await self.session.flush()
        return doc.version


class DocumentVersionRepository(BaseRepository[DocumentVersion]):
    """Repository for DocumentVersion model."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(DocumentVersion, session)
    
    async def get_versions_for_document(
        self, 
        document_id: int, 
        skip: int = 0, 
        limit: int = 50
    ) -> List[DocumentVersion]:
        """Get version history for a document."""
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_latest_version(self, document_id: int) -> Optional[DocumentVersion]:
        """Get the latest version of a document."""
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def create_version(
        self, 
        document_id: int, 
        creator_id: int, 
        content: str,
        change_summary: Optional[str] = None
    ) -> DocumentVersion:
        """Create a new version snapshot."""
        # Get current max version
        max_version_stmt = (
            select(func.max(DocumentVersion.version_number))
            .where(DocumentVersion.document_id == document_id)
        )
        result = await self.session.execute(max_version_stmt)
        current_max = result.scalar() or 0
        
        return await self.create(
            document_id=document_id,
            creator_id=creator_id,
            content=content,
            version_number=current_max + 1,
            change_summary=change_summary
        )


class DocumentCollaboratorRepository(BaseRepository[DocumentCollaborator]):
    """Repository for DocumentCollaborator model."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(DocumentCollaborator, session)
    
    async def get_collaborators(self, document_id: int) -> List[DocumentCollaborator]:
        """Get all collaborators for a document."""
        stmt = (
            select(DocumentCollaborator)
            .where(DocumentCollaborator.document_id == document_id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def add_collaborator(
        self, 
        document_id: int, 
        user_id: int, 
        permission: str = "edit"
    ) -> DocumentCollaborator:
        """Add a collaborator to a document."""
        return await self.create(
            document_id=document_id,
            user_id=user_id,
            permission=permission
        )
    
    async def remove_collaborator(self, document_id: int, user_id: int) -> bool:
        """Remove a collaborator from a document."""
        stmt = (
            select(DocumentCollaborator)
            .where(
                and_(
                    DocumentCollaborator.document_id == document_id,
                    DocumentCollaborator.user_id == user_id
                )
            )
        )
        result = await self.session.execute(stmt)
        collab = result.scalar_one_or_none()
        
        if collab:
            await self.session.delete(collab)
            await self.session.flush()
            return True
        return False
    
    async def check_permission(
        self, 
        document_id: int, 
        user_id: int, 
        required_permission: str = "edit"
    ) -> bool:
        """Check if user has required permission for document."""
        doc = await self.session.get(Document, document_id)
        if not doc:
            return False
        
        # Owner has all permissions
        if doc.owner_id == user_id:
            return True
        
        # Check collaboration permission
        stmt = (
            select(DocumentCollaborator)
            .where(
                and_(
                    DocumentCollaborator.document_id == document_id,
                    DocumentCollaborator.user_id == user_id
                )
            )
        )
        result = await self.session.execute(stmt)
        collab = result.scalar_one_or_none()
        
        if not collab:
            return False
        
        permission_levels = {"view": 1, "edit": 2, "admin": 3}
        return permission_levels.get(collab.permission, 0) >= permission_levels.get(required_permission, 0)


class OperationLogRepository(BaseRepository[OperationLog]):
    """Repository for OperationLog model."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(OperationLog, session)
    
    async def get_operations_for_document(
        self, 
        document_id: int, 
        after_timestamp=None,
        limit: int = 1000
    ) -> List[OperationLog]:
        """Get operations for a document, optionally after a timestamp."""
        stmt = (
            select(OperationLog)
            .where(OperationLog.document_id == document_id)
            .order_by(OperationLog.timestamp.asc())
            .limit(limit)
        )
        
        if after_timestamp:
            stmt = stmt.where(OperationLog.timestamp > after_timestamp)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def log_operation(
        self,
        document_id: int,
        user_id: int,
        operation_type: str,
        operation_data: dict,
        vector_clock: Optional[dict] = None
    ) -> OperationLog:
        """Log an operation for conflict resolution."""
        return await self.create(
            document_id=document_id,
            user_id=user_id,
            operation_type=operation_type,
            operation_data=operation_data,
            vector_clock=vector_clock
        )
