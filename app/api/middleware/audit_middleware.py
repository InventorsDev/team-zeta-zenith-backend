"""
Audit Logging Middleware - Automatically logs API requests
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable
import logging
import time

from app.database.connection import SessionLocal
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically logs API requests to audit log

    Logs:
    - All authenticated requests
    - Failed authentication attempts
    - Unauthorized access attempts
    - Data modification operations (POST, PUT, DELETE)
    """

    # Exclude these paths from audit logging (too noisy)
    EXCLUDED_PATHS = [
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    ]

    # Only log these methods for read-only endpoints (to avoid noise)
    LOGGED_METHODS = ["POST", "PUT", "DELETE", "PATCH"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log to audit trail"""

        # Skip excluded paths
        if any(request.url.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return await call_next(request)

        # Get request context
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        endpoint = request.url.path
        http_method = request.method

        # Track request timing
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # Only log write operations or failed requests
        should_log = (
            http_method in self.LOGGED_METHODS or
            response.status_code >= 400
        )

        if should_log:
            self._create_audit_log(
                request=request,
                response=response,
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint=endpoint,
                http_method=http_method,
                duration=duration,
            )

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check X-Forwarded-For header (for proxies/load balancers)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client
        if request.client:
            return request.client.host

        return "unknown"

    def _create_audit_log(
        self,
        request: Request,
        response: Response,
        ip_address: str,
        user_agent: str,
        endpoint: str,
        http_method: str,
        duration: float,
    ):
        """Create audit log entry in database"""
        db = SessionLocal()
        try:
            audit_service = AuditService(db)

            # Extract user info from request state (set by auth dependency)
            user_id = getattr(request.state, "user_id", None)
            organization_id = getattr(request.state, "organization_id", None)

            # Determine action based on endpoint and method
            action = self._determine_action(endpoint, http_method)

            # Determine status
            if response.status_code < 300:
                status = "success"
            elif response.status_code == 401 or response.status_code == 403:
                status = "unauthorized"
            else:
                status = "failure"

            # Determine severity
            severity = "info"
            if response.status_code >= 500:
                severity = "critical"
            elif response.status_code == 401 or response.status_code == 403:
                severity = "warning"

            # Extract resource info from endpoint
            resource_type, resource_id = self._extract_resource_info(endpoint)

            # Create audit log
            audit_service.log_action(
                action=action,
                status=status,
                user_id=user_id,
                organization_id=organization_id,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint=endpoint,
                http_method=http_method,
                severity=severity,
                details={
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                },
            )

        except Exception as e:
            # Don't fail the request if audit logging fails
            logger.error(f"Error creating audit log: {e}")
        finally:
            db.close()

    def _determine_action(self, endpoint: str, method: str) -> str:
        """Determine action identifier from endpoint and method"""
        # Extract base resource from endpoint
        parts = endpoint.strip("/").split("/")

        # Remove "api" and version prefix
        if parts and parts[0] == "api":
            parts = parts[1:]
        if parts and parts[0].startswith("v"):
            parts = parts[1:]

        if not parts:
            return f"{method.lower()}.unknown"

        resource = parts[0] if parts else "unknown"

        # Map method to action verb
        action_map = {
            "GET": "read",
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete",
        }

        action_verb = action_map.get(method, method.lower())

        return f"{resource}.{action_verb}"

    def _extract_resource_info(self, endpoint: str) -> tuple:
        """Extract resource type and ID from endpoint"""
        parts = endpoint.strip("/").split("/")

        # Remove "api" and version prefix
        if parts and parts[0] == "api":
            parts = parts[1:]
        if parts and parts[0].startswith("v"):
            parts = parts[1:]

        resource_type = parts[0] if parts else None

        # Look for numeric ID in path
        resource_id = None
        for part in parts:
            if part.isdigit():
                resource_id = part
                break

        return resource_type, resource_id
