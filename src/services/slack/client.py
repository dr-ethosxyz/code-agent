"""Slack API client - data layer."""

from typing import Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from src.config import settings
from src.core.logging import get_logger

logger = get_logger("slack.data")

_slack_client: Optional[WebClient] = None


def get_slack_client() -> WebClient:
    """Get Slack client instance."""
    global _slack_client

    if _slack_client:
        return _slack_client

    if not settings.slack_bot_token:
        raise ValueError("SLACK_BOT_TOKEN not configured")

    _slack_client = WebClient(token=settings.slack_bot_token)
    return _slack_client


def post_message(
    channel: str,
    blocks: list[dict],
    text: str,
) -> None:
    """Post a message to Slack."""
    client = get_slack_client()
    client.chat_postMessage(
        channel=channel,
        blocks=blocks,
        text=text,
    )
    logger.info(f"Posted message to {channel}")
