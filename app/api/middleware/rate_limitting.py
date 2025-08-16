import time
from typing import Dict, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from collections import defaultdict, deque


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for API endpoints"""
    
    def __init__(self, app, calls: int = 100, period: int = 60):
        """
        Initialize rate limiter
        
        Args:
            app: FastAPI application
            calls: Number of allowed calls per period
            period: Time period in seconds
        """
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.clients: Dict[str, deque] = defaultdict(deque)
        
        # Special rate limits for auth endpoints
        self.auth_limits = {
            "/api/v1/auth/login": {"calls": 5, "period": 60},  # 5 attempts per minute
            "/api/v1/auth/register": {"calls": 3, "period": 60},  # 3 registrations per minute
        }

    def get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded headers in case of proxy
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        return request.client.host

    def is_rate_limited(self, client_ip: str, path: str) -> Tuple[bool, Dict]:
        """Check if client is rate limited"""
        current_time = time.time()
        
        # Get limits for this path
        if path in self.auth_limits:
            limits = self.auth_limits[path]
            calls = limits["calls"]
            period = limits["period"]
        else:
            calls = self.calls
            period = self.period
        
        # Create a unique key for this client and path combination
        key = f"{client_ip}:{path}"
        
        # Clean old entries
        client_requests = self.clients[key]
        while client_requests and client_requests[0] < current_time - period:
            client_requests.popleft()
        
        # Check if limit exceeded
        if len(client_requests) >= calls:
            # Calculate time until reset
            oldest_request = client_requests[0]
            reset_time = oldest_request + period
            retry_after = int(reset_time - current_time)
            
            return True, {
                "retry_after": max(retry_after, 1),
                "limit": calls,
                "period": period
            }
        
        # Add current request
        client_requests.append(current_time)
        
        return False, {
            "remaining": calls - len(client_requests),
            "limit": calls,
            "period": period
        }

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting"""
        client_ip = self.get_client_ip(request)
        path = request.url.path
        
        # Check rate limit
        is_limited, info = self.is_rate_limited(client_ip, path)
        
        if is_limited:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"Rate limit exceeded. Try again in {info['retry_after']} seconds."
                },
                headers={
                    "Retry-After": str(info["retry_after"]),
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Reset": str(int(time.time()) + info["retry_after"]),
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + info["period"])
        
        return response


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """Specific rate limiting middleware for authentication endpoints"""
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = RateLimitMiddleware(app)

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting only to auth endpoints"""
        path = request.url.path
        
        # Only apply to auth endpoints
        if path.startswith("/api/v1/auth/"):
            return await self.rate_limiter.dispatch(request, call_next)
        
        return await call_next(request)
