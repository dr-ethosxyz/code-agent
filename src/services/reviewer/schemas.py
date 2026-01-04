"""Pydantic schemas for reviewer service."""

from pydantic import BaseModel


class ReviewResult(BaseModel):
    """Result of a PR review."""

    success: bool = True
    pr: str
    files_reviewed: int
    comments: int
    summary: str


class FileReview(BaseModel):
    """Review of a single file."""

    path: str
    comments: list[dict] = []
    summary: str = ""
