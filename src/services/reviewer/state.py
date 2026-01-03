"""Agent state schema for the code reviewer."""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class ReviewState(TypedDict):
    """State for the code review agent."""

    # PR Context (immutable)
    owner: str
    repo: str
    pr_number: int
    pr_title: str
    pr_description: str | None

    # Files to review
    files: list[dict]  # [{filename, patch, additions, deletions}]
    current_file_index: int

    # Agent conversation
    messages: Annotated[list, add_messages]

    # Accumulated results
    file_comments: list[dict]  # [{path, line, message}]
    file_summaries: list[str]

    # Final output
    overall_summary: str | None
    review_complete: bool
