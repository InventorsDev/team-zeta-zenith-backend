from typing import TypeVar, Generic, List, Dict, Any
from math import ceil
from pydantic import BaseModel

T = TypeVar('T')

class PaginationParams(BaseModel):
    """Base pagination parameters"""
    page: int = 1
    size: int = 50
    
    def __post_init__(self):
        if self.page < 1:
            self.page = 1
        if self.size < 1 or self.size > 100:
            self.size = 50

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response"""
    items: List[T]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool

def create_pagination_response(
    items: List[T], 
    total: int, 
    page: int, 
    size: int
) -> PaginatedResponse[T]:
    """Create a paginated response from items and metadata"""
    pages = ceil(total / size) if size > 0 else 1
    has_next = page < pages
    has_prev = page > 1
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
        has_next=has_next,
        has_prev=has_prev
    )

def get_skip_limit(page: int, size: int) -> tuple[int, int]:
    """Calculate skip and limit values for database queries"""
    if page < 1:
        page = 1
    if size < 1 or size > 100:
        size = 50
    
    skip = (page - 1) * size
    return skip, size

class FilterParams(BaseModel):
    """Base filter parameters"""
    search: str = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    
    def get_sort_params(self) -> tuple[str, str]:
        """Get validated sort parameters"""
        sort_order = self.sort_order.lower()
        if sort_order not in ["asc", "desc"]:
            sort_order = "desc"
        return self.sort_by, sort_order