from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.security import decode_access_token


class JWTMiddleware(BaseHTTPMiddleware):
    """Middleware to validate JWT tokens on protected routes"""
    
    # Routes that don't require authentication
    EXEMPT_PATHS = {
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/status",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/",
    }

    async def dispatch(self, request: Request, call_next):
        """Process the request and validate JWT if required"""
        path = request.url.path
        
        # Skip authentication for exempt paths
        if path in self.EXEMPT_PATHS or path.startswith("/static/"):
            return await call_next(request)
        
        # Extract token from Authorization header
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        scheme, token = get_authorization_scheme_param(authorization)
        if not token or scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Validate token
        payload = decode_access_token(token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Add user info to request state
        request.state.user_id = payload.get("sub")
        request.state.user_email = payload.get("email")
        
        return await call_next(request)


def get_current_user_id(request: Request) -> Optional[str]:
    """Helper function to get current user ID from request state"""
    return getattr(request.state, "user_id", None)


def get_current_user_email(request: Request) -> Optional[str]:
    """Helper function to get current user email from request state"""
    return getattr(request.state, "user_email", None)
