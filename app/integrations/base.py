"""
Base integration classes and utilities
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseIntegration(ABC):
    """Base class for all external platform integrations"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.is_enabled = self._validate_config()
        
    @abstractmethod
    def _validate_config(self) -> bool:
        """Validate integration configuration"""
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """Test connection to the external service"""
        pass
    
    @abstractmethod
    def sync_tickets(self, full_sync: bool = False) -> Dict[str, Any]:
        """Synchronize tickets from external service"""
        pass
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get integration health status"""
        return {
            "enabled": self.is_enabled,
            "connected": self.test_connection() if self.is_enabled else False,
            "last_check": datetime.utcnow().isoformat()
        }


class RateLimiter:
    """Rate limiting utility for API calls"""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        """
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds (default: 60 seconds)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def can_make_request(self) -> bool:
        """Check if we can make a request without exceeding rate limit"""
        now = datetime.utcnow()
        # Remove requests outside the time window
        cutoff = now.timestamp() - self.time_window
        self.requests = [req for req in self.requests if req > cutoff]
        
        return len(self.requests) < self.max_requests
    
    def record_request(self):
        """Record a request being made"""
        self.requests.append(datetime.utcnow().timestamp())
    
    def get_wait_time(self) -> float:
        """Get seconds to wait before making next request"""
        if self.can_make_request():
            return 0
        
        # Find oldest request in current window
        if self.requests:
            oldest_request = min(self.requests)
            wait_time = self.time_window - (datetime.utcnow().timestamp() - oldest_request)
            return max(0, wait_time)
        
        return 0


class IntegrationError(Exception):
    """Base exception for integration errors"""
    pass


class RateLimitError(IntegrationError):
    """Exception raised when rate limit is exceeded"""
    pass


class AuthenticationError(IntegrationError):
    """Exception raised when authentication fails"""
    pass


class SyncError(IntegrationError):
    """Exception raised during synchronization"""
    pass