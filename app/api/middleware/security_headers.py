"""
Security Headers Middleware - Adds security headers to all responses
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all HTTP responses

    Headers added:
    - Content-Security-Policy: Prevents XSS and injection attacks
    - X-Frame-Options: Prevents clickjacking
    - X-Content-Type-Options: Prevents MIME-type sniffing
    - Strict-Transport-Security: Enforces HTTPS (production only)
    - X-XSS-Protection: Legacy XSS protection
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Controls browser features
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add security headers to response"""

        response = await call_next(request)

        # Content Security Policy - Restrict resource loading
        # Allow same-origin for most resources, specific domains for external resources
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # Allow inline scripts for dev (tighten in prod)
            "style-src 'self' 'unsafe-inline'",  # Allow inline styles
            "img-src 'self' data: https:",  # Allow images from self, data URIs, and HTTPS
            "font-src 'self' data:",
            "connect-src 'self' https://api.openai.com https://api.slack.com",  # API endpoints
            "frame-ancestors 'none'",  # Equivalent to X-Frame-Options: DENY
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Prevent page from being displayed in iframe/frame (clickjacking protection)
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Strict Transport Security - Force HTTPS (only in production)
        if settings.environment == "production":
            # max-age=31536000 = 1 year, includeSubDomains applies to all subdomains
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Legacy XSS protection (modern browsers use CSP instead)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information sent to external sites
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy - Disable potentially dangerous browser features
        permissions_directives = [
            "geolocation=()",  # Disable geolocation
            "microphone=()",   # Disable microphone
            "camera=()",       # Disable camera
            "payment=()",      # Disable payment APIs
            "usb=()",          # Disable USB
            "magnetometer=()", # Disable magnetometer
            "gyroscope=()",    # Disable gyroscope
            "accelerometer=()",# Disable accelerometer
        ]
        response.headers["Permissions-Policy"] = ", ".join(permissions_directives)

        return response
