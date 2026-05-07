"""Database session management and repository base class."""
import logging
from typing import AsyncGenerator, Type, TypeVar, Generic, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

T = TypeVar("T")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session.
    
    Yields:
        AsyncSession: Database session instance
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        await session.close()


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations.
    
    This implements the Repository pattern, abstracting database operations
    and providing a clean interface for the service layer.
    """
    
    def __init__(self, model: Type[T], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def get(self, id: int) -> Optional[T]:
        """Get a single record by ID.
        
        Args:
            id: Primary key ID
            
        Returns:
            Model instance or None if not found
        """
        try:
            result = await self.session.get(self.model, id)
            return result
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model.__name__} by id {id}: {e}")
            raise
    
    async def get_by_field(self, field: str, value) -> Optional[T]:
        """Get a single record by a specific field.
        
        Args:
            field: Field name to search by
            value: Value to match
            
        Returns:
            Model instance or None if not found
        """
        try:
            stmt = select(self.model).where(getattr(self.model, field) == value)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model.__name__} by {field}: {e}")
            raise
    
    async def list(
        self, 
        skip: int = 0, 
        limit: int = 100,
        order_by: Optional[str] = None,
        desc: bool = False
    ) -> List[T]:
        """List records with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Field to order by
            desc: Order in descending order if True
            
        Returns:
            List of model instances
        """
        try:
            stmt = select(self.model)
            
            if order_by:
                order_column = getattr(self.model, order_by)
                if desc:
                    stmt = stmt.order_by(order_column.desc())
                else:
                    stmt = stmt.order_by(order_column)
            
            stmt = stmt.offset(skip).limit(limit)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Error listing {self.model.__name__}: {e}")
            raise
    
    async def count(self) -> int:
        """Count total records.
        
        Returns:
            Total count of records
        """
        try:
            stmt = select(func.count()).select_from(self.model)
            result = await self.session.execute(stmt)
            return result.scalar() or 0
        except SQLAlchemyError as e:
            logger.error(f"Error counting {self.model.__name__}: {e}")
            raise
    
    async def create(self, **kwargs) -> T:
        """Create a new record.
        
        Args:
            **kwargs: Model attributes
            
        Returns:
            Created model instance
        """
        try:
            obj = self.model(**kwargs)
            self.session.add(obj)
            await self.session.flush()
            await self.session.refresh(obj)
            return obj
        except SQLAlchemyError as e:
            logger.error(f"Error creating {self.model.__name__}: {e}")
            raise
    
    async def update(self, id: int, **kwargs) -> Optional[T]:
        """Update an existing record.
        
        Args:
            id: Primary key ID
            **kwargs: Attributes to update
            
        Returns:
            Updated model instance or None if not found
        """
        try:
            obj = await self.get(id)
            if not obj:
                return None
            
            for key, value in kwargs.items():
                setattr(obj, key, value)
            
            await self.session.flush()
            await self.session.refresh(obj)
            return obj
        except SQLAlchemyError as e:
            logger.error(f"Error updating {self.model.__name__} id {id}: {e}")
            raise
    
    async def delete(self, id: int) -> bool:
        """Delete a record by ID.
        
        Args:
            id: Primary key ID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            obj = await self.get(id)
            if not obj:
                return False
            
            await self.session.delete(obj)
            await self.session.flush()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error deleting {self.model.__name__} id {id}: {e}")
            raise
    
    async def exists(self, id: int) -> bool:
        """Check if a record exists.
        
        Args:
            id: Primary key ID
            
        Returns:
            True if exists, False otherwise
        """
        try:
            obj = await self.get(id)
            return obj is not None
        except SQLAlchemyError as e:
            logger.error(f"Error checking existence of {self.model.__name__} id {id}: {e}")
            raise
