"""
Search Schemas - Pydantic models for advanced search functionality
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SearchOperator(str, Enum):
    """Search operators for conditions"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN_OR_EQUAL = "lte"
    IN = "in"
    NOT_IN = "not_in"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"


class SearchLogic(str, Enum):
    """Logical operators for combining conditions"""
    AND = "AND"
    OR = "OR"


class SearchCondition(BaseModel):
    """Individual search condition"""
    field: str = Field(..., description="Field to search on")
    operator: SearchOperator
    value: Any = Field(None, description="Value to compare against")
    logic: Optional[SearchLogic] = Field(None, description="Logic operator (AND/OR)")


class AdvancedSearchRequest(BaseModel):
    """Advanced search with multiple conditions"""
    query: Optional[str] = Field(None, max_length=500, description="Full-text search query")
    conditions: List[SearchCondition] = Field(default_factory=list)
    page: int = Field(1, ge=1)
    size: int = Field(50, ge=1, le=100)
    sort_by: Optional[str] = Field("created_at", description="Field to sort by")
    sort_order: Optional[str] = Field("desc", pattern="^(asc|desc)$")


class SearchSuggestion(BaseModel):
    """Search suggestion/autocomplete item"""
    text: str
    field: str
    count: Optional[int] = None
    type: str = Field("suggestion", description="Type of suggestion")


class SearchSuggestionsResponse(BaseModel):
    """Response for search suggestions"""
    suggestions: List[SearchSuggestion]
    query: str


class SavedSearchBase(BaseModel):
    """Base saved search schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    query: Optional[str] = None
    conditions: List[SearchCondition] = Field(default_factory=list)
    is_default: bool = Field(False, description="Set as default search")
    is_shared: bool = Field(False, description="Share with organization")


class SavedSearchCreate(SavedSearchBase):
    """Schema for creating a saved search"""
    pass


class SavedSearchUpdate(BaseModel):
    """Schema for updating a saved search"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    query: Optional[str] = None
    conditions: Optional[List[SearchCondition]] = None
    is_default: Optional[bool] = None
    is_shared: Optional[bool] = None


class SavedSearchResponse(SavedSearchBase):
    """Schema for saved search response"""
    id: int
    user_id: int
    organization_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    use_count: int = 0

    class Config:
        from_attributes = True


class SearchResultHighlight(BaseModel):
    """Highlighted search result"""
    field: str
    value: str
    highlighted: str


class TicketSearchResult(BaseModel):
    """Enhanced ticket search result with highlights"""
    id: int
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    category: Optional[str] = None
    channel: str
    customer_email: str
    customer_name: Optional[str] = None
    created_at: datetime
    highlights: List[SearchResultHighlight] = Field(default_factory=list)
    score: Optional[float] = Field(None, description="Search relevance score")

    class Config:
        from_attributes = True


class SearchResultsResponse(BaseModel):
    """Paginated search results with highlights"""
    items: List[TicketSearchResult]
    total: int
    page: int
    size: int
    pages: int
    query: Optional[str] = None
    took_ms: Optional[int] = Field(None, description="Search execution time in milliseconds")


class SearchHistory(BaseModel):
    """User search history item"""
    query: str
    timestamp: datetime
    results_count: int


class SearchHistoryResponse(BaseModel):
    """User search history"""
    history: List[SearchHistory]
    total: int
