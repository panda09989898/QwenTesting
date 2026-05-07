"""Business logic services for the application."""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import User, Document, DocumentVersion
from backend.repositories import (
    UserRepository,
    DocumentRepository,
    DocumentVersionRepository,
    DocumentCollaboratorRepository,
    OperationLogRepository,
)
from backend.core.security import get_password_hash, verify_password, create_access_token
from backend.schemas import UserCreate, UserLogin, DocumentCreate, DocumentUpdate, TextOperation

logger = logging.getLogger(__name__)


class UserService:
    """Service layer for user-related business logic.
    
    Handles user registration, authentication, and profile management.
    Follows Single Responsibility Principle by focusing only on user operations.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
    
    async def register_user(self, user_data: UserCreate) -> User:
        """Register a new user.
        
        Args:
            user_data: User registration data
            
        Returns:
            Created user instance
            
        Raises:
            ValueError: If email or username already exists
        """
        # Check for existing user
        existing_email = await self.user_repo.get_by_email(user_data.email)
        if existing_email:
            raise ValueError("Email already registered")
        
        existing_username = await self.user_repo.get_by_username(user_data.username)
        if existing_username:
            raise ValueError("Username already taken")
        
        # Create user with hashed password
        hashed_pw = get_password_hash(user_data.password)
        user = await self.user_repo.create(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_pw
        )
        
        logger.info(f"User registered: {user.email}")
        return user
    
    async def authenticate_user(self, login_data: UserLogin) -> Optional[Dict[str, Any]]:
        """Authenticate user and return token.
        
        Args:
            login_data: User login credentials
            
        Returns:
            Dict with access_token and token_type if successful, None otherwise
        """
        user = await self.user_repo.get_by_email(login_data.email)
        if not user:
            logger.warning(f"Authentication failed: user not found - {login_data.email}")
            return None
        
        if not verify_password(login_data.password, user.hashed_password):
            logger.warning(f"Authentication failed: invalid password - {login_data.email}")
            return None
        
        # Generate JWT token
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        
        logger.info(f"User authenticated: {user.email}")
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 1800  # 30 minutes
        }
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return await self.user_repo.get(user_id)
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return await self.user_repo.get_by_email(email)


class DocumentService:
    """Service layer for document-related business logic.
    
    Handles document CRUD operations, version history, and collaboration.
    Implements conflict resolution for concurrent edits.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.version_repo = DocumentVersionRepository(session)
        self.collab_repo = DocumentCollaboratorRepository(session)
        self.op_log_repo = OperationLogRepository(session)
    
    async def create_document(
        self, 
        doc_data: DocumentCreate, 
        owner_id: int
    ) -> Document:
        """Create a new document.
        
        Args:
            doc_data: Document creation data
            owner_id: ID of the document owner
            
        Returns:
            Created document instance
        """
        document = await self.doc_repo.create(
            title=doc_data.title,
            content=doc_data.content,
            owner_id=owner_id,
            version=1
        )
        
        # Create initial version snapshot
        await self.version_repo.create_version(
            document_id=document.id,
            creator_id=owner_id,
            content=doc_data.content,
            change_summary="Initial document creation"
        )
        
        logger.info(f"Document created: {document.id} by user {owner_id}")
        return document
    
    async def get_document(self, document_id: int) -> Optional[Document]:
        """Get a document by ID."""
        return await self.doc_repo.get(document_id)
    
    async def get_user_documents(
        self, 
        user_id: int, 
        page: int = 0, 
        page_size: int = 20
    ) -> Tuple[List[Document], int]:
        """Get all documents for a user (owned and collaborated).
        
        Args:
            user_id: User ID
            page: Page number (0-indexed)
            page_size: Number of items per page
            
        Returns:
            Tuple of (documents list, total count)
        """
        skip = page * page_size
        docs = await self.doc_repo.get_user_documents(
            user_id=user_id,
            skip=skip,
            limit=page_size
        )
        total = await self.doc_repo.count_user_documents(user_id)
        return docs, total
    
    async def update_document(
        self, 
        document_id: int, 
        user_id: int,
        doc_data: DocumentUpdate
    ) -> Optional[Document]:
        """Update a document.
        
        Args:
            document_id: Document ID to update
            user_id: User performing the update
            doc_data: Update data
            
        Returns:
            Updated document or None if not found
        """
        # Check permission
        has_permission = await self.collab_repo.check_permission(
            document_id=document_id,
            user_id=user_id,
            required_permission="edit"
        )
        
        if not has_permission:
            raise PermissionError("User does not have edit permission")
        
        update_data = {}
        if doc_data.title is not None:
            update_data["title"] = doc_data.title
        if doc_data.content is not None:
            update_data["content"] = doc_data.content
        
        if not update_data:
            return await self.doc_repo.get(document_id)
        
        document = await self.doc_repo.update(document_id, **update_data)
        
        if document and doc_data.content is not None:
            # Create new version snapshot
            await self.version_repo.create_version(
                document_id=document_id,
                creator_id=user_id,
                content=doc_data.content,
                change_summary="Manual update"
            )
            # Increment version
            await self.doc_repo.increment_version(document_id)
        
        logger.info(f"Document updated: {document_id} by user {user_id}")
        return document
    
    async def delete_document(self, document_id: int, user_id: int) -> bool:
        """Delete a document.
        
        Args:
            document_id: Document ID to delete
            user_id: User performing the deletion
            
        Returns:
            True if deleted, False otherwise
        """
        document = await self.doc_repo.get(document_id)
        if not document:
            return False
        
        # Only owner can delete
        if document.owner_id != user_id:
            raise PermissionError("Only document owner can delete")
        
        result = await self.doc_repo.delete(document_id)
        logger.info(f"Document deleted: {document_id} by user {user_id}")
        return result
    
    async def get_version_history(
        self, 
        document_id: int, 
        page: int = 0, 
        page_size: int = 20
    ) -> Tuple[List[DocumentVersion], int]:
        """Get version history for a document.
        
        Args:
            document_id: Document ID
            page: Page number
            page_size: Items per page
            
        Returns:
            Tuple of (versions list, total count)
        """
        skip = page * page_size
        versions = await self.version_repo.get_versions_for_document(
            document_id=document_id,
            skip=skip,
            limit=page_size
        )
        total = len(versions)  # Could be optimized with count query
        return versions, total
    
    async def restore_version(
        self, 
        document_id: int, 
        version_id: int, 
        user_id: int
    ) -> Optional[Document]:
        """Restore a document to a previous version.
        
        Args:
            document_id: Document ID
            version_id: Version ID to restore
            user_id: User performing the restore
            
        Returns:
            Updated document or None
        """
        version = await self.version_repo.get(version_id)
        if not version or version.document_id != document_id:
            return None
        
        # Check permission
        has_permission = await self.collab_repo.check_permission(
            document_id=document_id,
            user_id=user_id,
            required_permission="edit"
        )
        
        if not has_permission:
            raise PermissionError("User does not have edit permission")
        
        # Update document content
        document = await self.doc_repo.update(
            document_id,
            content=version.content
        )
        
        if document:
            # Create new version with restore note
            await self.version_repo.create_version(
                document_id=document_id,
                creator_id=user_id,
                content=version.content,
                change_summary=f"Restored to version {version.version_number}"
            )
            await self.doc_repo.increment_version(document_id)
        
        logger.info(f"Document restored: {document_id} to version {version_id} by user {user_id}")
        return document


class ConflictResolutionService:
    """Service for handling concurrent edit conflicts.
    
    Implements Operational Transformation (OT) inspired conflict resolution
    with vector clocks for ordering operations.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.op_log_repo = OperationLogRepository(session)
    
    def apply_operation(self, content: str, operation: TextOperation) -> str:
        """Apply a text operation to content.
        
        Args:
            content: Current document content
            operation: Text operation to apply
            
        Returns:
            Updated content string
        """
        try:
            if operation.type == "insert":
                return content[:operation.position] + operation.text + content[operation.position:]
            
            elif operation.type == "delete":
                return content[:operation.position] + content[operation.position + operation.length:]
            
            elif operation.type == "update":
                return content[:operation.position] + operation.text + content[operation.position + operation.length:]
            
            return content
        except (IndexError, TypeError) as e:
            logger.error(f"Error applying operation: {e}")
            return content
    
    def transform_operations(
        self, 
        op1: TextOperation, 
        op2: TextOperation
    ) -> Tuple[TextOperation, TextOperation]:
        """Transform two concurrent operations against each other.
        
        This implements a simple OT algorithm for insert/delete operations.
        
        Args:
            op1: First operation
            op2: Second operation
            
        Returns:
            Tuple of transformed operations (op1', op2')
        """
        # Create copies to avoid mutating originals
        op1_prime = op1.model_copy()
        op2_prime = op2.model_copy()
        
        # If same position, use timestamp to decide order
        if op1.position == op2.position:
            if op1.timestamp > op2.timestamp:
                # op1 happened first, adjust op2
                if op1.type == "insert":
                    op2_prime.position += len(op1.text)
                elif op1.type == "delete":
                    op2_prime.position -= op1.length
            else:
                # op2 happened first, adjust op1
                if op2.type == "insert":
                    op1_prime.position += len(op2.text)
                elif op2.type == "delete":
                    op1_prime.position -= op2.length
        else:
            # Different positions
            if op1.position < op2.position:
                # op1 is before op2
                if op1.type == "insert":
                    op2_prime.position += len(op1.text)
                elif op1.type == "delete":
                    op2_prime.position = max(0, op2_prime.position - op1.length)
            else:
                # op2 is before op1
                if op2.type == "insert":
                    op1_prime.position += len(op2.text)
                elif op2.type == "delete":
                    op1_prime.position = max(0, op1_prime.position - op2.length)
        
        return op1_prime, op2_prime
    
    async def merge_changes(
        self, 
        document_id: int, 
        base_content: str,
        operations: List[TextOperation]
    ) -> Tuple[str, List[TextOperation]]:
        """Merge multiple operations into document content.
        
        Args:
            document_id: Document ID
            base_content: Base content to apply operations to
            operations: List of operations to merge
            
        Returns:
            Tuple of (merged content, rejected operations)
        """
        content = base_content
        rejected = []
        
        # Sort operations by timestamp
        sorted_ops = sorted(operations, key=lambda x: x.timestamp)
        
        for op in sorted_ops:
            try:
                # Validate operation
                if op.position < 0 or op.position > len(content):
                    logger.warning(f"Invalid operation position: {op.position}")
                    rejected.append(op)
                    continue
                
                # Apply operation
                content = self.apply_operation(content, op)
                
                # Log operation for audit trail
                await self.op_log_repo.log_operation(
                    document_id=document_id,
                    user_id=op.user_id,
                    operation_type=op.type,
                    operation_data=op.model_dump(),
                    vector_clock=op.vector_clock
                )
                
            except Exception as e:
                logger.error(f"Error merging operation: {e}")
                rejected.append(op)
        
        return content, rejected
    
    def compute_vector_clock(
        self, 
        current_clock: Dict[str, int], 
        user_id: str
    ) -> Dict[str, int]:
        """Compute next vector clock value.
        
        Args:
            current_clock: Current vector clock
            user_id: User making the change
            
        Returns:
            Updated vector clock
        """
        clock = current_clock.copy() if current_clock else {}
        clock[user_id] = clock.get(user_id, 0) + 1
        return clock
    
    def compare_vector_clocks(
        self, 
        clock1: Dict[str, int], 
        clock2: Dict[str, int]
    ) -> str:
        """Compare two vector clocks.
        
        Returns:
            'before' if clock1 < clock2
            'after' if clock1 > clock2
            'concurrent' if neither dominates
            'equal' if identical
        """
        if not clock1 and not clock2:
            return "equal"
        
        all_keys = set(clock1.keys()) | set(clock2.keys())
        
        less = False
        greater = False
        
        for key in all_keys:
            v1 = clock1.get(key, 0)
            v2 = clock2.get(key, 0)
            
            if v1 < v2:
                less = True
            elif v1 > v2:
                greater = True
        
        if less and greater:
            return "concurrent"
        elif less:
            return "before"
        elif greater:
            return "after"
        else:
            return "equal"
