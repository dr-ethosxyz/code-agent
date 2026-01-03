"""Slack service - business logic layer."""

from typing import Optional
from slack_sdk.errors import SlackApiError

from src.config import settings
from src.services.slack.client import post_message
from src.core.logging import get_logger

logger = get_logger("slack.service")


def send_review_notification(
    owner: str,
    repo: str,
    pr_number: int,
    pr_title: str,
    pr_author: str,
    summary: str,
    comments_count: int,
    pr_url: str,
    channel_id: Optional[str] = None,
) -> None:
    """Send PR review notification to Slack."""
    target_channel = channel_id or settings.slack_channel_id

    if not target_channel:
        logger.warning("No Slack channel configured, skipping notification")
        return

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"PR Review: {owner}/{repo}#{pr_number}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{pr_url}|{pr_title}>*\nby @{pr_author}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Summary:*\n{summary}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f":speech_balloon: {comments_count} comments",
                },
            ],
        },
    ]

    try:
        post_message(
            channel=target_channel,
            blocks=blocks,
            text=f"PR Review: {pr_title} - {comments_count} comments",
        )
        logger.info(f"Sent review notification to {target_channel}")
    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
