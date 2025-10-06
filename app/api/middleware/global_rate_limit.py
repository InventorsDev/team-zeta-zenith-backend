"""
Global Rate Limiting Middleware - Apply rate limits to all API endpoints per organization
"""

import time
from typing import Dict, Tuple, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from starlette import status
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Global rate limiting middleware with tiered limits per organization

    Implements three levels of rate limiting:
    1. Per-IP rate limiting (anonymous users)
    2. Per-user rate limiting (authenticated users)
    3. Per-organization rate limiting (organization-wide quotas)
    """

    def __init__(
        self,
        app,
        # Anonymous/IP-based limits
        ip_calls: int = 60,
        ip_period: int = 60,
        # Authenticated user limits
        user_calls: int = 300,
        user_period: int = 60,
        # Organization-wide limits
        org_calls: int = 5000,
        org_period: int = 60,
    ):
        """
        Initialize global rate limiter

        Args:
            app: FastAPI application
            ip_calls: Calls per period for anonymous users (per IP)
            ip_period: Time period for IP limits (seconds)
            user_calls: Calls per period for authenticated users
            user_period: Time period for user limits (seconds)
            org_calls: Calls per period for organization (shared quota)
            org_period: Time period for org limits (seconds)
        """
        super().__init__(app)

        # Rate limit configurations
        self.ip_calls = ip_calls
        self.ip_period = ip_period
        self.user_calls = user_calls
        self.user_period = user_period
        self.org_calls = org_calls
        self.org_period = org_period

        # Storage for request timestamps
        self.ip_requests: Dict[str, deque] = defaultdict(deque)
        self.user_requests: Dict[int, deque] = defaultdict(deque)
        self.org_requests: Dict[int, deque] = defaultdict(deque)

        # Paths excluded from rate limiting
        self.excluded_paths = [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/",
        ]

        # Stricter limits for sensitive endpoints
        self.strict_limits = {
            "/api/v1/auth/login": {"calls": 5, "period": 60},
            "/api/v1/auth/register": {"calls": 3, "period": 60},
            "/api/v1/data/export": {"calls": 10, "period": 3600},  # 10 exports per hour
        }

    def get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        if request.client:
            return request.client.host

        return "unknown"

    def check_rate_limit(
        self,
        key: str,
        storage: Dict,
        calls: int,
        period: int
    ) -> Tuple[bool, Dict]:
        """
        Check if rate limit is exceeded

        Args:
            key: Identifier (IP, user_id, org_id)
            storage: Request storage dict
            calls: Max calls allowed
            period: Time period in seconds

        Returns:
            (is_limited, info_dict)
        """
        current_time = time.time()
        requests = storage[key]

        # Clean old entries outside the time window
        while requests and requests[0] < current_time - period:
            requests.popleft()

        # Check if limit exceeded
        if len(requests) >= calls:
            oldest_request = requests[0]
            reset_time = oldest_request + period
            retry_after = int(reset_time - current_time)

            return True, {
                "retry_after": max(retry_after, 1),
                "limit": calls,
                "remaining": 0,
                "reset": int(reset_time)
            }

        # Add current request
        requests.append(current_time)

        return False, {
            "limit": calls,
            "remaining": calls - len(requests),
            "reset": int(current_time + period)
        }

    async def dispatch(self, request: Request, call_next):
        """Process request with tiered rate limiting"""
        path = request.url.path

        # Skip excluded paths
        if any(path.startswith(excluded) for excluded in self.excluded_paths):
            return await call_next(request)

        # Get client context
        client_ip = self.get_client_ip(request)
        user_id = getattr(request.state, "user_id", None)
        org_id = getattr(request.state, "organization_id", None)

        # Determine rate limit parameters
        if path in self.strict_limits:
            # Use strict limits for sensitive endpoints
            calls = self.strict_limits[path]["calls"]
            period = self.strict_limits[path]["period"]
            storage_key = f"{client_ip}:{path}"
            is_limited, info = self.check_rate_limit(
                storage_key,
                self.ip_requests,
                calls,
                period
            )
            limit_type = "endpoint"
        elif user_id and org_id:
            # Authenticated request - check org, then user, then IP
            # 1. Organization-wide limit
            is_limited, org_info = self.check_rate_limit(
                org_id,
                self.org_requests,
                self.org_calls,
                self.org_period
            )

            if is_limited:
                limit_type = "organization"
                info = org_info
            else:
                # 2. User-specific limit
                is_limited, user_info = self.check_rate_limit(
                    user_id,
                    self.user_requests,
                    self.user_calls,
                    self.user_period
                )
                limit_type = "user"
                info = user_info
        else:
            # Anonymous request - IP-based limit
            is_limited, info = self.check_rate_limit(
                client_ip,
                self.ip_requests,
                self.ip_calls,
                self.ip_period
            )
            limit_type = "ip"

        # If rate limited, return 429 error
        if is_limited:
            logger.warning(
                f"Rate limit exceeded - Type: {limit_type}, "
                f"User: {user_id}, Org: {org_id}, IP: {client_ip}, Path: {path}"
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": f"Rate limit exceeded. Try again in {info['retry_after']} seconds.",
                    "limit_type": limit_type,
                },
                headers={
                    "Retry-After": str(info["retry_after"]),
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset"]),
                }
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to successful responses
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])

        return response
