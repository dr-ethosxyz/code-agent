"""GitHub API client - data layer."""

import hmac
import hashlib
from typing import Optional
from github import Github, GithubIntegration
from github.PullRequest import PullRequest
from loguru import logger

from src.config import settings

_github_client: Optional[Github] = None


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature using HMAC-SHA256."""
    if not settings.github_webhook_secret:
        logger.warning("No webhook secret configured, skipping verification")
        return True

    expected = hmac.new(
        settings.github_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    expected_signature = f"sha256={expected}"
    return hmac.compare_digest(expected_signature, signature)


def get_github_client() -> Github:
    """Get authenticated GitHub client using App installation."""
    global _github_client

    if _github_client:
        return _github_client

    if not all([settings.github_app_id, settings.github_private_key, settings.github_installation_id]):
        raise ValueError("GitHub App credentials not configured")

    private_key = settings.github_private_key.replace("\\n", "\n")

    integration = GithubIntegration(
        integration_id=int(settings.github_app_id),
        private_key=private_key,
    )

    access_token = integration.get_access_token(int(settings.github_installation_id)).token
    _github_client = Github(access_token)

    logger.info("GitHub App client initialized")
    return _github_client


def fetch_pull_request(owner: str, repo: str, pr_number: int) -> PullRequest:
    """Fetch a pull request from GitHub API."""
    client = get_github_client()
    repository = client.get_repo(f"{owner}/{repo}")
    return repository.get_pull(pr_number)


def fetch_pr_files(pr: PullRequest) -> list[dict]:
    """Fetch changed files from a PR."""
    files = []
    for f in pr.get_files():
        files.append({
            "filename": f.filename,
            "status": f.status,
            "additions": f.additions,
            "deletions": f.deletions,
            "patch": f.patch or "",
            "contents_url": f.contents_url,
        })
    return files


def create_review(
    pr: PullRequest,
    body: str,
    comments: list[dict],
    event: str = "COMMENT",
) -> None:
    """Create a review on a PR."""
    review_comments = []
    for c in comments:
        if c.get("line") and c.get("path"):
            review_comments.append({
                "path": c["path"],
                "line": c["line"],
                "body": c["message"],
            })

    pr.create_review(
        body=body,
        event=event,
        comments=review_comments if review_comments else None,
    )
    logger.info(f"Created review with {len(review_comments)} comments")


def fetch_file_contents(owner: str, repo: str, path: str, ref: str = "HEAD") -> str:
    """Fetch full file contents from repository."""
    client = get_github_client()
    repository = client.get_repo(f"{owner}/{repo}")
    try:
        content = repository.get_contents(path, ref=ref)
        if isinstance(content, list):
            raise ValueError(f"Path {path} is a directory, not a file")
        return content.decoded_content.decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to fetch file {path}: {e}")
        raise


def fetch_directory_contents(owner: str, repo: str, path: str = "") -> list[dict]:
    """List contents of a directory in the repository."""
    client = get_github_client()
    repository = client.get_repo(f"{owner}/{repo}")
    try:
        contents = repository.get_contents(path)
        if not isinstance(contents, list):
            contents = [contents]
        return [
            {
                "name": item.name,
                "path": item.path,
                "type": item.type,  # "file" or "dir"
                "size": item.size if item.type == "file" else None,
            }
            for item in contents
        ]
    except Exception as e:
        logger.error(f"Failed to list directory {path}: {e}")
        raise


def search_code_in_repo(owner: str, repo: str, query: str) -> list[dict]:
    """Search code in repository using GitHub search API."""
    client = get_github_client()
    search_query = f"{query} repo:{owner}/{repo}"
    try:
        results = client.search_code(search_query)
        items = []
        for item in results[:20]:  # Limit to 20 results
            items.append({
                "path": item.path,
                "name": item.name,
                "html_url": item.html_url,
                "repository": item.repository.full_name,
            })
        return items
    except Exception as e:
        logger.error(f"Code search failed for '{query}': {e}")
        raise
