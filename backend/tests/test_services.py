"""Unit tests for services."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services import UserService, DocumentService, ConflictResolutionService
from backend.schemas import UserCreate, UserLogin, DocumentCreate, TextOperation, OperationType


class TestUserService:
    """Tests for UserService."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        return session
    
    @pytest.fixture
    def user_service(self, mock_session):
        """Create UserService instance with mocked dependencies."""
        return UserService(mock_session)
    
    @pytest.mark.asyncio
    async def test_register_user_success(self, user_service, mock_session):
        """Test successful user registration."""
        # Arrange
        user_data = UserCreate(
            email="test@example.com",
            username="testuser",
            password="securepassword123"
        )
        
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.id = 1
        
        user_service.user_repo.get_by_email = AsyncMock(return_value=None)
        user_service.user_repo.get_by_username = AsyncMock(return_value=None)
        user_service.user_repo.create = AsyncMock(return_value=mock_user)
        
        # Act
        result = await user_service.register_user(user_data)
        
        # Assert
        assert result.email == "test@example.com"
        assert result.username == "testuser"
        user_service.user_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_user_email_exists(self, user_service):
        """Test registration fails when email exists."""
        # Arrange
        user_data = UserCreate(
            email="existing@example.com",
            username="newuser",
            password="password123"
        )
        
        existing_user = MagicMock()
        user_service.user_repo.get_by_email = AsyncMock(return_value=existing_user)
        
        # Act & Assert
        with pytest.raises(ValueError, match="Email already registered"):
            await user_service.register_user(user_data)
    
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, user_service):
        """Test successful authentication."""
        # Arrange
        login_data = UserLogin(
            email="test@example.com",
            password="correctpassword"
        )
        
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.id = 1
        mock_user.hashed_password = "$2b$12$..."  # bcrypt hash
        
        user_service.user_repo.get_by_email = AsyncMock(return_value=mock_user)
        
        with patch('backend.services.verify_password', return_value=True):
            with patch('backend.services.create_access_token', return_value="fake_token"):
                # Act
                result = await user_service.authenticate_user(login_data)
                
                # Assert
                assert result is not None
                assert result["access_token"] == "fake_token"
                assert result["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_authenticate_user_invalid_password(self, user_service):
        """Test authentication fails with wrong password."""
        # Arrange
        login_data = UserLogin(
            email="test@example.com",
            password="wrongpassword"
        )
        
        mock_user = MagicMock()
        mock_user.email = "test@example.com"
        mock_user.hashed_password = "$2b$12$..."
        
        user_service.user_repo.get_by_email = AsyncMock(return_value=mock_user)
        
        with patch('backend.services.verify_password', return_value=False):
            # Act
            result = await user_service.authenticate_user(login_data)
            
            # Assert
            assert result is None


class TestConflictResolutionService:
    """Tests for ConflictResolutionService."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def conflict_service(self, mock_session):
        """Create ConflictResolutionService instance."""
        return ConflictResolutionService(mock_session)
    
    def test_apply_insert_operation(self, conflict_service):
        """Test applying insert operation."""
        # Arrange
        content = "Hello world"
        operation = TextOperation(
            type=OperationType.INSERT,
            position=6,
            text="beautiful ",
            timestamp=datetime.utcnow(),
            user_id=1,
            vector_clock={"1": 1}
        )
        
        # Act
        result = conflict_service.apply_operation(content, operation)
        
        # Assert
        assert result == "Hello beautiful world"
    
    def test_apply_delete_operation(self, conflict_service):
        """Test applying delete operation."""
        # Arrange
        content = "Hello beautiful world"
        operation = TextOperation(
            type=OperationType.DELETE,
            position=6,
            length=9,
            timestamp=datetime.utcnow(),
            user_id=1,
            vector_clock={"1": 1}
        )
        
        # Act
        result = conflict_service.apply_operation(content, operation)
        
        # Assert
        assert result == "Hello world"
    
    def test_transform_operations_same_position(self, conflict_service):
        """Test transforming operations at same position."""
        # Arrange
        now = datetime.utcnow()
        op1 = TextOperation(
            type=OperationType.INSERT,
            position=5,
            text="A",
            timestamp=now,
            user_id=1,
            vector_clock={"1": 1}
        )
        op2 = TextOperation(
            type=OperationType.INSERT,
            position=5,
            text="B",
            timestamp=now,
            user_id=2,
            vector_clock={"2": 1}
        )
        
        # Act
        op1_prime, op2_prime = conflict_service.transform_operations(op1, op2)
        
        # Assert - one should be adjusted
        assert op1_prime.position == 5
        assert op2_prime.position == 6  # Adjusted after op1's insertion
    
    def test_compare_vector_clocks_equal(self, conflict_service):
        """Test comparing equal vector clocks."""
        clock1 = {"1": 2, "2": 3}
        clock2 = {"1": 2, "2": 3}
        
        result = conflict_service.compare_vector_clocks(clock1, clock2)
        assert result == "equal"
    
    def test_compare_vector_clocks_before(self, conflict_service):
        """Test comparing clock that happened before."""
        clock1 = {"1": 1, "2": 2}
        clock2 = {"1": 2, "2": 3}
        
        result = conflict_service.compare_vector_clocks(clock1, clock2)
        assert result == "before"
    
    def test_compare_vector_clocks_concurrent(self, conflict_service):
        """Test comparing concurrent vector clocks."""
        clock1 = {"1": 3, "2": 1}
        clock2 = {"1": 1, "2": 3}
        
        result = conflict_service.compare_vector_clocks(clock1, clock2)
        assert result == "concurrent"


class TestDocumentService:
    """Tests for DocumentService."""
    
    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def document_service(self, mock_session):
        """Create DocumentService instance with mocked repos."""
        service = DocumentService(mock_session)
        # Mock all repositories
        service.doc_repo = MagicMock()
        service.version_repo = MagicMock()
        service.collab_repo = MagicMock()
        service.op_log_repo = MagicMock()
        return service
    
    @pytest.mark.asyncio
    async def test_create_document(self, document_service):
        """Test document creation."""
        # Arrange
        doc_data = DocumentCreate(title="Test Doc", content="Initial content")
        
        mock_doc = MagicMock()
        mock_doc.id = 1
        mock_doc.title = "Test Doc"
        mock_doc.content = "Initial content"
        mock_doc.owner_id = 1
        mock_doc.version = 1
        
        document_service.doc_repo.create = AsyncMock(return_value=mock_doc)
        document_service.version_repo.create_version = AsyncMock()
        
        # Act
        result = await document_service.create_document(doc_data, owner_id=1)
        
        # Assert
        assert result.id == 1
        assert result.title == "Test Doc"
        document_service.doc_repo.create.assert_called_once()
        document_service.version_repo.create_version.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_document_permission_check(self, document_service):
        """Test update checks permissions."""
        # Arrange
        document_service.collab_repo.check_permission = AsyncMock(return_value=False)
        
        # Act & Assert
        with pytest.raises(PermissionError):
            await document_service.update_document(
                document_id=1,
                user_id=2,
                doc_data=DocumentUpdate(title="New Title")
            )


# Run with: pytest backend/tests/test_services.py -v
