"""
Zendesk API client with authentication and rate limiting
"""
import requests
import base64
import time
import logging
from typing import Dict, List, Any, Optional, Generator
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlencode

from app.integrations.base import BaseIntegration, RateLimiter, AuthenticationError, RateLimitError, IntegrationError
from app.integrations.zendesk.models import ZendeskAPIResponse, ZendeskSyncResult
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ZendeskClient(BaseIntegration):
    """
    Zendesk API client with rate limiting (700 requests/minute)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # IMPORTANT: Config should always come from the user's integration record in the database
        # Environment variables are only used for system-level default/fallback configuration
        if config is None:
            # Fallback to environment variables only for system/development use
            # Production integrations should ALWAYS provide explicit config from database
            config = {
                "subdomain": settings.zendesk_subdomain,
                "email": settings.zendesk_email,
                "token": settings.zendesk_token
            }
            logger.warning("ZendeskClient initialized with environment config - this should only happen in development or system operations")
        else:
            # Production path: Use config from user's integration record
            # Handle both 'token' and 'api_token' field names for backward compatibility
            if 'api_token' in config and 'token' not in config:
                config['token'] = config['api_token']
        
        super().__init__(config)
        
        # Zendesk rate limit: 700 requests per minute
        self.rate_limiter = RateLimiter(max_requests=700, time_window=60)
        
        # Only set up URLs and headers if properly configured
        if self.is_enabled:
            self.base_url = f"https://{self.config['subdomain']}.zendesk.com"
            self.api_url = f"{self.base_url}/api/v2"
            
            # Setup authentication headers
            self.auth_header = self._create_auth_header()
            self.headers = {
                "Authorization": self.auth_header,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Request session for connection pooling
            self.session = requests.Session()
            self.session.headers.update(self.headers)
        else:
            self.base_url = ""
            self.api_url = ""
            self.auth_header = ""
            self.headers = {}
            self.session = requests.Session()
    
    def _validate_config(self) -> bool:
        """Validate Zendesk configuration"""
        required_fields = ['subdomain', 'email', 'token']
        missing_fields = [field for field in required_fields if not self.config.get(field)]
        
        if missing_fields:
            logger.warning(f"Missing Zendesk config fields: {missing_fields}")
            return False
        
        return True
    
    def _create_auth_header(self) -> str:
        """Create Basic Auth header for Zendesk API"""
        if not self.is_enabled:
            return ""
        
        # Format: email/token:token
        auth_string = f"{self.config['email']}/token:{self.config['token']}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        return f"Basic {encoded_auth}"
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make rate-limited request to Zendesk API with retry logic
        """
        if not self.is_enabled:
            raise AuthenticationError("Zendesk client not properly configured")
        
        # Check rate limit
        if not self.rate_limiter.can_make_request():
            wait_time = self.rate_limiter.get_wait_time()
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                time.sleep(wait_time)
        
        url = urljoin(self.api_url + "/", endpoint.lstrip("/"))
        
        # Default timeout and retry settings
        kwargs.setdefault("timeout", 30)
        max_retries = kwargs.pop("max_retries", 3)
        retry_delay = kwargs.pop("retry_delay", 1)
        
        for attempt in range(max_retries + 1):
            try:
                # Record the request for rate limiting
                self.rate_limiter.record_request()
                
                response = self.session.request(method, url, **kwargs)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < max_retries:
                        logger.warning(f"Rate limited, retrying after {retry_after} seconds (attempt {attempt + 1})")
                        time.sleep(retry_after)
                        continue
                    else:
                        raise RateLimitError(f"Rate limit exceeded after {max_retries} retries")
                
                # Handle authentication errors
                if response.status_code == 401:
                    raise AuthenticationError("Invalid Zendesk credentials")
                
                # Handle other client errors
                if response.status_code >= 400:
                    error_msg = f"Zendesk API error {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    if attempt < max_retries and response.status_code >= 500:
                        # Retry on server errors
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                        continue
                    else:
                        raise IntegrationError(error_msg)
                
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    logger.warning(f"Request failed, retrying (attempt {attempt + 1}): {e}")
                    time.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    raise IntegrationError(f"Request failed after {max_retries} retries: {e}")
        
        raise IntegrationError("Unexpected error in request handling")
    
    def test_connection(self) -> bool:
        """Test connection to Zendesk API"""
        if not self.is_enabled:
            return False
        
        try:
            response = self._make_request("GET", "/users/me.json")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Zendesk connection test failed: {e}")
            return False
    
    def get_tickets(
        self, 
        page_size: int = 100, 
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        incremental: bool = False
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch tickets from Zendesk with pagination
        
        Args:
            page_size: Number of tickets per page (max 100)
            start_time: Filter tickets updated after this time
            end_time: Filter tickets updated before this time  
            incremental: Use incremental export API for better performance
        """
        page_size = min(page_size, 100)  # Zendesk max is 100
        
        if incremental:
            # Use incremental export API for better performance on large datasets
            endpoint = "/incremental/tickets.json"
            params = {"per_page": page_size}
            
            if start_time:
                # Convert to Unix timestamp
                params["start_time"] = int(start_time.timestamp())
            
        else:
            # Use regular tickets API
            endpoint = "/tickets.json"
            params = {
                "per_page": page_size,
                "sort_by": "updated_at",
                "sort_order": "asc"
            }
            
            # Add time filters if specified
            if start_time or end_time:
                query_parts = []
                if start_time:
                    query_parts.append(f"updated>={start_time.strftime('%Y-%m-%d')}")
                if end_time:
                    query_parts.append(f"updated<={end_time.strftime('%Y-%m-%d')}")
                if query_parts:
                    params["query"] = " ".join(query_parts)
        
        next_page = endpoint
        total_fetched = 0
        seen_pages = set()  # Track pages we've already fetched to prevent infinite loops
        max_pages = 1000  # Safety limit to prevent infinite loops
        page_count = 0
        
        while next_page and page_count < max_pages:
            try:
                page_count += 1
                
                # Add parameters to URL
                if params and "?" not in next_page:
                    next_page += "?" + urlencode(params)
                
                # Check if we've already seen this page (infinite loop protection)
                if next_page in seen_pages:
                    logger.info("Detected pagination loop, stopping sync")
                    break
                seen_pages.add(next_page)
                
                logger.info(f"Fetching tickets from: {next_page}")
                response = self._make_request("GET", next_page)
                data = response.json()
                
                # Extract tickets
                tickets = data.get("tickets", [])
                if not tickets:
                    logger.info("No more tickets found, ending pagination")
                    break
                
                total_fetched += len(tickets)
                logger.info(f"Fetched {len(tickets)} tickets (total: {total_fetched})")
                
                # Yield each ticket
                for ticket in tickets:
                    yield ticket
                
                # Get next page URL
                next_page_url = data.get("next_page")
                
                # For incremental API, check if we've reached the end
                if incremental:
                    # Check if end_time is present and we've reached it
                    end_of_stream = data.get("end_of_stream", False)
                    if end_of_stream or not next_page_url:
                        logger.info("Reached end of incremental stream")
                        break
                    
                    # Also check if next_page is the same as current (another loop indicator)
                    if next_page_url and next_page_url == next_page:
                        logger.info("Next page URL same as current, ending pagination")
                        break
                
                next_page = next_page_url
                params = {}  # Params are included in next_page URL
                
                # Respect rate limiting between pages
                if next_page and not self.rate_limiter.can_make_request():
                    wait_time = self.rate_limiter.get_wait_time()
                    if wait_time > 0:
                        logger.info(f"Rate limiting: waiting {wait_time:.1f} seconds")
                        time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Error fetching tickets page: {e}")
                break
        
        # Log if we hit the safety limit
        if page_count >= max_pages:
            logger.warning(f"Reached maximum page limit ({max_pages}), stopping pagination")
        
        logger.info(f"Pagination completed: {page_count} pages processed, {total_fetched} tickets total")
    
    def get_ticket(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific ticket by ID"""
        try:
            response = self._make_request("GET", f"/tickets/{ticket_id}.json")
            data = response.json()
            return data.get("ticket")
        except Exception as e:
            logger.error(f"Error fetching ticket {ticket_id}: {e}")
            return None
    
    def create_ticket(self, ticket_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new ticket in Zendesk"""
        try:
            payload = {"ticket": ticket_data}
            response = self._make_request("POST", "/tickets.json", json=payload)
            data = response.json()
            return data.get("ticket")
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            return None
    
    def update_ticket(self, ticket_id: int, ticket_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing ticket in Zendesk"""
        try:
            payload = {"ticket": ticket_data}
            response = self._make_request("PUT", f"/tickets/{ticket_id}.json", json=payload)
            data = response.json()
            return data.get("ticket")
        except Exception as e:
            logger.error(f"Error updating ticket {ticket_id}: {e}")
            return None
    
    def get_ticket_comments(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Get comments for a specific ticket"""
        try:
            response = self._make_request("GET", f"/tickets/{ticket_id}/comments.json")
            data = response.json()
            return data.get("comments", [])
        except Exception as e:
            logger.error(f"Error fetching comments for ticket {ticket_id}: {e}")
            return []
    
    def get_users(self, page_size: int = 100) -> Generator[Dict[str, Any], None, None]:
        """Fetch users from Zendesk with pagination"""
        page_size = min(page_size, 100)
        next_page = f"/users.json?per_page={page_size}"
        
        while next_page:
            try:
                response = self._make_request("GET", next_page)
                data = response.json()
                
                users = data.get("users", [])
                for user in users:
                    yield user
                
                next_page = data.get("next_page")
                
            except Exception as e:
                logger.error(f"Error fetching users: {e}")
                break
    
    def sync_tickets(self, full_sync: bool = False) -> ZendeskSyncResult:
        """
        Synchronize tickets from Zendesk
        Implementation will be in the sync.py module
        """
        from app.integrations.zendesk.sync import ZendeskSyncService
        sync_service = ZendeskSyncService(self)
        return sync_service.sync_tickets(full_sync=full_sync)
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        return {
            "max_requests": self.rate_limiter.max_requests,
            "time_window": self.rate_limiter.time_window,
            "current_requests": len(self.rate_limiter.requests),
            "requests_remaining": self.rate_limiter.max_requests - len(self.rate_limiter.requests),
            "wait_time": self.rate_limiter.get_wait_time(),
            "can_make_request": self.rate_limiter.can_make_request()
        }