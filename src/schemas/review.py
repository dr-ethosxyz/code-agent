"""Review-related schemas."""

from pydantic import BaseModel


class FileReviewComment(BaseModel):
    line: int
    message: str


class FileReviewResult(BaseModel):
    comments: list[FileReviewComment]
    summary: str
