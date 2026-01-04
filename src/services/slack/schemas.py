"""Pydantic schemas for Slack service."""

from pydantic import BaseModel


class SlackEventResponse(BaseModel):
    """Response schema for Slack events."""

    ok: bool = True
    message: str | None = None
    challenge: str | None = None


class SlackChallengeResponse(BaseModel):
    """Response for Slack URL verification."""

    challenge: str


class ReviewNotificationRequest(BaseModel):
    """Request to send review notification."""

    owner: str
    repo: str
    pr_number: int
    pr_title: str
    pr_author: str
    summary: str
    comments_count: int
    pr_url: str
    channel_id: str | None = None


class ParsedReviewSummary(BaseModel):
    """Parsed review summary components."""

    changes: str = ""
    risk_level: str = "🟡 Medium"
    issues: list[str] = []
    verdict: str = "⚠️ Needs Review"
