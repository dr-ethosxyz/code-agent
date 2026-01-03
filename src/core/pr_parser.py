"""Parse PR references from text."""

import re
from dataclasses import dataclass
from typing import Optional

from src.config import settings


@dataclass
class PRReference:
    """Parsed PR reference."""

    owner: str
    repo: str
    pr_number: int


def parse_pr_reference(text: str) -> Optional[PRReference]:
    """
    Parse PR reference from text.

    Supported formats:
    - #123 -> uses default owner/repo from settings
    - owner/repo#123 -> specific repo
    - https://github.com/owner/repo/pull/123 -> full URL
    """
    # Pattern 1: Full GitHub URL
    url_pattern = r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.search(url_pattern, text)
    if match:
        return PRReference(
            owner=match.group(1),
            repo=match.group(2),
            pr_number=int(match.group(3)),
        )

    # Pattern 2: owner/repo#123
    full_ref_pattern = r"([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)#(\d+)"
    match = re.search(full_ref_pattern, text)
    if match:
        return PRReference(
            owner=match.group(1),
            repo=match.group(2),
            pr_number=int(match.group(3)),
        )

    # Pattern 3: #123 (use defaults)
    short_pattern = r"(?:^|\s)#(\d+)(?:\s|$)"
    match = re.search(short_pattern, text)
    if match:
        if not settings.default_repo_owner or not settings.default_repo_name:
            return None
        return PRReference(
            owner=settings.default_repo_owner,
            repo=settings.default_repo_name,
            pr_number=int(match.group(1)),
        )

    # Pattern 4: "review 123" or "PR 123"
    number_pattern = r"(?:review|pr|pull\s*request)\s+(\d+)"
    match = re.search(number_pattern, text, re.IGNORECASE)
    if match:
        if not settings.default_repo_owner or not settings.default_repo_name:
            return None
        return PRReference(
            owner=settings.default_repo_owner,
            repo=settings.default_repo_name,
            pr_number=int(match.group(1)),
        )

    return None


def extract_review_intent(text: str) -> bool:
    """Check if the message is asking for a review."""
    review_keywords = [
        "review",
        "check",
        "look at",
        "examine",
        "analyze",
        "inspect",
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in review_keywords)
