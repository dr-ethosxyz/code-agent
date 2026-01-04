"""GitHub service - business logic layer."""

from fastapi import BackgroundTasks
from github.PullRequest import PullRequest

from src.core.logging import get_logger
from src.services.github.client import create_review, fetch_pr_files, fetch_pull_request

logger = get_logger("github.service")


def get_pull_request(owner: str, repo: str, pr_number: int) -> PullRequest:
    """Get a pull request by owner/repo and number."""
    logger.info(f"Fetching PR: {owner}/{repo}#{pr_number}")
    return fetch_pull_request(owner, repo, pr_number)


def get_pr_files(owner: str, repo: str, pr_number: int) -> list[dict]:
    """Get changed files from a PR."""
    pr = fetch_pull_request(owner, repo, pr_number)
    files = fetch_pr_files(pr)
    logger.info(f"Found {len(files)} files in PR")
    return files


def submit_review(
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
    comments: list[dict],
    invalid_comments: list[dict] | None = None,
    event: str = "COMMENT",
) -> None:
    """Submit a review to a PR."""
    pr = fetch_pull_request(owner, repo, pr_number)
    try:
        create_review(pr, body, comments, invalid_comments or [], event)
        logger.info(f"Submitted review with {len(comments)} comments")
    except Exception as e:
        logger.error(f"Failed to submit review: {e}")
        raise


def get_file_contents(owner: str, repo: str, path: str, ref: str = "HEAD") -> str:
    """Get full file contents from repository."""
    from src.services.github.client import fetch_file_contents

    logger.info(f"Fetching file: {owner}/{repo}/{path}@{ref}")
    return fetch_file_contents(owner, repo, path, ref)


def list_directory(owner: str, repo: str, path: str = "") -> list[dict]:
    """List contents of a directory in the repository."""
    from src.services.github.client import fetch_directory_contents

    logger.info(f"Listing directory: {owner}/{repo}/{path}")
    return fetch_directory_contents(owner, repo, path)


def search_code(owner: str, repo: str, query: str) -> list[dict]:
    """Search code in repository."""
    from src.services.github.client import search_code_in_repo

    logger.info(f"Searching code in {owner}/{repo}: {query}")
    return search_code_in_repo(owner, repo, query)


async def handle_pull_request_event(
    payload: dict,
    background_tasks: BackgroundTasks,
) -> dict:
    """Handle pull_request webhook events."""
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})

    owner = repo.get("owner", {}).get("login")
    repo_name = repo.get("name")
    pr_number = pr.get("number")

    logger.info(f"PR event: {action} on {owner}/{repo_name}#{pr_number}")

    if action not in ("opened", "synchronize"):
        return {
            "message": f"Action {action} not reviewed",
            "supported_actions": ["opened", "synchronize"],
        }

    background_tasks.add_task(run_review, owner, repo_name, pr_number)

    return {
        "message": "Review started",
        "pr": f"{owner}/{repo_name}#{pr_number}",
        "action": action,
    }


async def run_review(owner: str, repo: str, pr_number: int) -> dict:
    """Run the review in background."""
    from src.services.reviewer.service import review_pull_request

    try:
        result = await review_pull_request(owner, repo, pr_number)
        logger.info(f"Review completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Review failed: {e}")
        raise
