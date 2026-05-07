"""API route handlers for authentication."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.base import get_db
from backend.services import UserService
from backend.schemas import UserCreate, UserLogin, Token, UserResponse, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_user_service(session: Annotated[AsyncSession, Depends(get_db)]) -> UserService:
    """Dependency injection for UserService."""
    return UserService(session)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "User already exists"}
    }
)
async def register(
    user_data: UserCreate,
    service: Annotated[UserService, Depends(get_user_service)]
) -> UserResponse:
    """Register a new user account.
    
    Creates a new user with the provided email, username, and password.
    The password is securely hashed before storage.
    
    Args:
        user_data: Registration data including email, username, password
        service: Injected UserService instance
        
    Returns:
        Created user information (excluding password)
        
    Raises:
        HTTPException: 400 if email or username already exists
    """
    try:
        user = await service.register_user(user_data)
        logger.info(f"New user registered: {user.email}")
        return UserResponse.model_validate(user)
    except ValueError as e:
        logger.warning(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/login",
    response_model=Token,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"}
    }
)
async def login(
    login_data: UserLogin,
    service: Annotated[UserService, Depends(get_user_service)]
) -> Token:
    """Authenticate user and return JWT token.
    
    Validates user credentials and returns an access token for authenticated requests.
    
    Args:
        login_data: Login credentials (email and password)
        service: Injected UserService instance
        
    Returns:
        JWT access token and metadata
        
    Raises:
        HTTPException: 401 if credentials are invalid
    """
    result = await service.authenticate_user(login_data)
    
    if not result:
        logger.warning("Login attempt with invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(f"User logged in: {login_data.email}")
    return Token(**result)


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db)],
    user_id: int = Depends(lambda: None)  # Will be set by auth middleware
) -> UserResponse:
    """Get current authenticated user information.
    
    Requires valid JWT token in Authorization header.
    
    Args:
        session: Database session
        user_id: User ID from auth middleware
        
    Returns:
        Current user information
        
    Raises:
        HTTPException: 404 if user not found
    """
    # Note: Actual user_id comes from middleware, this is simplified
    service = UserService(session)
    user = await service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.model_validate(user)
