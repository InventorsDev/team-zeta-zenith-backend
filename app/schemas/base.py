"""
Base Pydantic schemas for API responses and common models
"""

from typing import TypeVar, Generic, Optional, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class ResponseModel(BaseModel):
    """Base response model for API endpoints"""

    success: bool = Field(default=True, description="Whether the request was successful")
    message: Optional[str] = Field(default=None, description="Optional message")
    data: Optional[Any] = Field(default=None, description="Response data")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {}
            }
        }


class ErrorResponseModel(BaseModel):
    """Error response model"""

    success: bool = Field(default=False, description="Always False for errors")
    error: str = Field(..., description="Error message")
    details: Optional[Any] = Field(default=None, description="Error details")
    code: Optional[str] = Field(default=None, description="Error code")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "An error occurred",
                "details": None,
                "code": "ERROR_CODE"
            }
        }


T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response model"""

    items: List[T] = Field(default_factory=list, description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")

    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "size": 20,
                "pages": 5
            }
        }


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields"""

    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class IDMixin(BaseModel):
    """Mixin for ID field"""

    id: Optional[int] = Field(default=None, description="Unique identifier")


class BaseSchema(IDMixin, TimestampMixin):
    """Base schema combining ID and timestamp mixins"""

    class Config:
        from_attributes = True  # Allows ORM mode
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class StatusResponse(BaseModel):
    """Simple status response"""

    status: str = Field(..., description="Status message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class MessageResponse(BaseModel):
    """Simple message response"""

    message: str = Field(..., description="Response message")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation completed successfully"
            }
        }


class ValidationErrorDetail(BaseModel):
    """Validation error detail"""

    loc: List[str] = Field(..., description="Location of the error")
    msg: str = Field(..., description="Error message")
    type: str = Field(..., description="Error type")


class ValidationErrorResponse(BaseModel):
    """Validation error response"""

    success: bool = Field(default=False)
    error: str = Field(default="Validation Error")
    details: List[ValidationErrorDetail] = Field(..., description="Validation error details")
