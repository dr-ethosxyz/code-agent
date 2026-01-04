"""Reviewer service - orchestration layer."""

from src.config import settings
from src.core.logging import get_logger
from src.services.github.service import get_pr_files, get_pull_request, submit_review
from src.services.reviewer.graph import review_files_parallel
from src.services.reviewer.patch_parser import filter_comments_by_valid_lines
from src.services.slack.service import send_review_notification

logger = get_logger("reviewer.service")


async def review_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
) -> dict:
    """Review a complete pull request using parallel file processing."""
    logger.info(f"Starting parallel review: {owner}/{repo}#{pr_number}")

    # Fetch PR metadata and files
    pr = get_pull_request(owner, repo, pr_number)
    files = get_pr_files(owner, repo, pr_number)

    logger.info(f"Found {len(files)} files to review")

    # Filter to reviewable files (those with patches)
    reviewable_files = [f for f in files if f.get("patch")]

    if len(reviewable_files) > settings.max_files_per_review:
        logger.warning(f"Limiting review to {settings.max_files_per_review} files")
        reviewable_files = reviewable_files[: settings.max_files_per_review]

    if not reviewable_files:
        logger.info("No files with patches to review")
        return {
            "success": True,
            "pr": f"{owner}/{repo}#{pr_number}",
            "files_reviewed": 0,
            "comments": 0,
            "summary": "No reviewable changes found.",
        }

    # Run parallel file reviews
    all_comments, overall_summary = await review_files_parallel(
        files=reviewable_files,
        pr_title=pr.title,
        pr_description=pr.body,
        owner=owner,
        repo=repo,
        head_ref=pr.head.ref,
        max_concurrency=5,
    )

    logger.info(f"Parallel review completed: {len(all_comments)} comments")

    # Filter comments to only valid line numbers
    patches = {f["filename"]: f["patch"] for f in reviewable_files}
    valid_comments, invalid_comments = filter_comments_by_valid_lines(all_comments, patches)

    if invalid_comments:
        logger.warning(f"Filtered {len(invalid_comments)} comments with invalid line numbers")

    # Submit review to GitHub
    try:
        submit_review(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            body=overall_summary,
            comments=valid_comments,
            invalid_comments=invalid_comments,
            event="COMMENT",
        )
        logger.info(f"Review submitted with {len(valid_comments)} inline comments")
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
