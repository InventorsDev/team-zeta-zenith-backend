from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate, UserLogin, TokenResponse, UserResponse
from app.core.security import decode_access_token
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    auth_service = AuthService(db)
    return auth_service.get_current_user(payload)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account"""
    auth_service = AuthService(db)
    return auth_service.register_user(user_data)


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return access token"""
    auth_service = AuthService(db)
    return auth_service.login_user(login_data)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user profile information"""
    return current_user


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(current_user: User = Depends(get_current_user)):
    """Refresh access token for current user"""
    from app.core.security import create_token_response
    return create_token_response(current_user.id, current_user.email)
