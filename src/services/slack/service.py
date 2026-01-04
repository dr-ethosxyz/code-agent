"""Slack service - business logic layer."""

import re
from typing import Optional

from slack_sdk.errors import SlackApiError

from src.config import settings
from src.core.logging import get_logger
from src.services.slack.client import get_slack_client, post_message

logger = get_logger("slack.service")

# GitHub username -> Slack user ID mapping
GITHUB_TO_SLACK = {
    "jim302": "U09MVBGQ4H3",  # Tim
    "vishnu-matter": "U09BQ6MDRM4",  # Vishnu Kumar
    "thomascloarec": "U09S291SWJK",  # Thomas Cloarec
    "wongww": "U08D9Q7MG8G",  # Will WG
    # Add more:
    # "github_username": "SLACK_USER_ID",
}


def _parse_review_summary(summary: str) -> dict:
    """Parse the structured review summary into components."""
    result = {
        "changes": "",
        "risk_level": "🟡 Medium",
        "issues": [],
        "verdict": "⚠️ Needs Review",
    }

    # Extract changes
    changes_match = re.search(r"\*\*Changes:\*\*\s*(.+?)(?=\n\*\*|\n\n|$)", summary)
    if changes_match:
        result["changes"] = changes_match.group(1).strip()

    # Extract risk level
    risk_match = re.search(r"\*\*Risk Level:\*\*\s*(.+?)(?=\n|$)", summary)
    if risk_match:
        result["risk_level"] = risk_match.group(1).strip()

    # Extract issues
    issues_match = re.search(
        r"\*\*Issues Found:\*\*\s*\n?(.*?)(?=\n\*\*|\n---|\n\n|$)", summary, re.DOTALL
    )
    if issues_match:
        issues_text = issues_match.group(1).strip()
        if issues_text.lower() != "none":
            issues = re.findall(r"[•\-\*]\s*(.+)", issues_text)
            result["issues"] = [i.strip() for i in issues if i.strip()]

    # Extract verdict
    verdict_match = re.search(r"\*\*Verdict:\*\*\s*(.+?)(?=\n|$)", summary)
    if verdict_match:
        result["verdict"] = verdict_match.group(1).strip()

    return result


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

    # Parse the structured summary
    parsed = _parse_review_summary(summary)

    # Build issues text
    issues_text = "None" if not parsed["issues"] else "\n".join(f"• {i}" for i in parsed["issues"])

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"⚡ PR Review: {owner}/{repo}#{pr_number}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{pr_url}|{pr_title}>*\nby `@{pr_author}`",
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "View PR", "emoji": True},
                "url": pr_url,
                "action_id": "view_pr",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Risk Level*\n{parsed['risk_level']}"},
                {"type": "mrkdwn", "text": f"*Verdict*\n{parsed['verdict']}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Changes*\n{parsed['changes'] or 'No description'}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Issues Found*\n{issues_text}",
            },
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f":speech_balloon: *{comments_count}* inline comments"},
                {"type": "mrkdwn", "text": "|"},
                {"type": "mrkdwn", "text": "_Reviewed by Matter Code Agent_"},
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

    # DM the PR author if mapped
    _send_author_dm(
        pr_author=pr_author,
        pr_title=pr_title,
        pr_url=pr_url,
        parsed=parsed,
        comments_count=comments_count,
    )


def _send_author_dm(
    pr_author: str,
    pr_title: str,
    pr_url: str,
    parsed: dict,
    comments_count: int,
) -> None:
    """Send a DM to the PR author if they're mapped."""
    slack_user_id = GITHUB_TO_SLACK.get(pr_author)

    if not slack_user_id:
        logger.info(f"No Slack mapping for GitHub user: {pr_author}")
        return

    try:
        client = get_slack_client()

        # Open DM channel
        dm = client.conversations_open(users=[slack_user_id])
        dm_channel = dm["channel"]["id"]

        # Build issues text
        issues_text = (
            "None" if not parsed["issues"] else "\n".join(f"• {i}" for i in parsed["issues"])
        )

        # Send rich DM with full details
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚡ Your PR was reviewed",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{pr_url}|{pr_title}>*",
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "View PR", "emoji": True},
                    "url": pr_url,
                    "action_id": "view_pr_dm",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Risk Level*\n{parsed['risk_level']}"},
                    {"type": "mrkdwn", "text": f"*Verdict*\n{parsed['verdict']}"},
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Changes*\n{parsed['changes'] or 'No description'}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Issues Found*\n{issues_text}",
                },
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":speech_balloon: *{comments_count}* inline comments",
                    },
                ],
            },
        ]

        client.chat_postMessage(
            channel=dm_channel,
            blocks=blocks,
            text=f"Your PR was reviewed: {pr_title}",
        )
        logger.info(f"Sent DM to {pr_author} ({slack_user_id})")

    except SlackApiError as e:
        logger.error(f"Failed to DM {pr_author}: {e.response['error']}")
    except Exception as e:
        logger.error(f"Failed to DM {pr_author}: {e}")
