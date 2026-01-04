"""Shared response schemas for API endpoints."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard API success response wrapper."""

    success: bool = True
    data: T | None = None
    message: str | None = None


class ErrorResponse(BaseModel):
    """Standard API error response."""

    success: bool = False
    error: str
    details: dict | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    service: str = "pr-reviewer"
