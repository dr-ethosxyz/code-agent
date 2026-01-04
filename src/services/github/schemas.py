"""Pydantic schemas for GitHub service."""

from pydantic import BaseModel


class ManualReviewRequest(BaseModel):
    """Request schema for manual PR review trigger."""

    owner: str
    repo: str
    pr_number: int


class WebhookResponse(BaseModel):
    """Response schema for webhook events."""

    message: str
    pr: str | None = None
    action: str | None = None


class PingResponse(BaseModel):
    """Response schema for GitHub ping event."""

    message: str = "pong"
    zen: str = ""


class ReviewStartedResponse(BaseModel):
    """Response schema when review is started."""

    message: str = "Review started"
    pr: str


class ActionNotSupportedResponse(BaseModel):
    """Response schema for unsupported webhook actions."""

    message: str
    supported_actions: list[str] = ["opened", "synchronize"]
