"""Reviewer service - orchestration layer."""

from src.services.github.service import get_pull_request, get_pr_files, submit_review
from src.services.slack.service import send_review_notification
from src.services.reviewer.graph import create_review_graph
from src.services.reviewer.state import ReviewState
from src.core.logging import get_logger
from src.config import settings

logger = get_logger("reviewer.service")


async def review_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
) -> dict:
    """Review a complete pull request using the agentic reviewer."""
    logger.info(f"Starting agentic review: {owner}/{repo}#{pr_number}")

    # Fetch PR metadata and files
    pr = get_pull_request(owner, repo, pr_number)
    files = get_pr_files(owner, repo, pr_number)

    logger.info(f"Found {len(files)} files to review")

    # Filter to reviewable files (those with patches)
    reviewable_files = [f for f in files if f.get("patch")]

    if len(reviewable_files) > settings.max_files_per_review:
        logger.warning(f"Limiting review to {settings.max_files_per_review} files")
        reviewable_files = reviewable_files[:settings.max_files_per_review]

    if not reviewable_files:
        logger.info("No files with patches to review")
        return {
            "success": True,
            "pr": f"{owner}/{repo}#{pr_number}",
            "files_reviewed": 0,
            "comments": 0,
            "summary": "No reviewable changes found.",
        }

    # Initialize agent state
    initial_state: ReviewState = {
        "owner": owner,
        "repo": repo,
        "pr_number": pr_number,
        "pr_title": pr.title,
        "pr_description": pr.body,
        "files": reviewable_files,
        "current_file_index": 0,
        "messages": [],
        "file_comments": [],
        "file_summaries": [],
        "overall_summary": None,
        "review_complete": False,
    }

    # Create and run the agent graph
    graph = create_review_graph(owner, repo)
    final_state = await graph.ainvoke(initial_state)

    overall_summary = final_state.get("overall_summary") or "Review completed."
    all_comments = final_state.get("file_comments", [])

    logger.info(f"Agent review completed: {len(all_comments)} comments")

    # Submit review to GitHub
    try:
        submit_review(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            body=overall_summary,
            comments=all_comments,
            event="COMMENT",
        )
        logger.info(f"Review submitted with {len(all_comments)} comments")
    except Exception as e:
        logger.error(f"Failed to submit review: {e}")

    # Send Slack notification
    try:
        send_review_notification(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            pr_title=pr.title,
            pr_author=pr.user.login,
            summary=overall_summary[:500],
            comments_count=len(all_comments),
            pr_url=pr.html_url,
        )
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")

    return {
        "success": True,
        "pr": f"{owner}/{repo}#{pr_number}",
        "files_reviewed": len(reviewable_files),
        "comments": len(all_comments),
        "summary": overall_summary,
    }
