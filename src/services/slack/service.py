"""Slack service - business logic layer."""

import re
from typing import Optional

from slack_sdk.errors import SlackApiError

from src.config import settings
from src.core.logging import get_logger
from src.core.pr_parser import extract_review_intent, parse_pr_reference
from src.services.slack.client import get_slack_client, post_message

logger = get_logger("slack.service")

# GitHub username -> Slack user ID mapping
GITHUB_TO_SLACK = {
    "jim302": "U09MVBGQ4H3",  # Tim
    "vishnu-matter": "U09BQ6MDRM4",  # Vishnu Kumar
    "thomascloarec": "U09S291SWJK",  # Thomas Cloarec
    "wongww": "U08D9Q7MG8G",  # Will WG
}


def _parse_review_summary(summary: str) -> dict:
    """Parse the structured review summary into components."""
    result = {
        "changes": "",
        "risk_level": "🟡 Medium",
        "issues": [],
        "verdict": "⚠️ Needs Review",
    }

    changes_match = re.search(r"\*\*Changes:\*\*\s*(.+?)(?=\n\*\*|\n\n|$)", summary)
    if changes_match:
        result["changes"] = changes_match.group(1).strip()

    risk_match = re.search(r"\*\*Risk Level:\*\*\s*(.+?)(?=\n|$)", summary)
    if risk_match:
        result["risk_level"] = risk_match.group(1).strip()

    issues_match = re.search(
        r"\*\*Issues Found:\*\*\s*\n?(.*?)(?=\n\*\*|\n---|\n\n|$)", summary, re.DOTALL
    )
    if issues_match:
        issues_text = issues_match.group(1).strip()
        if issues_text.lower() != "none":
            issues = re.findall(r"[•\-\*]\s*(.+)", issues_text)
            result["issues"] = [i.strip() for i in issues if i.strip()]

    verdict_match = re.search(r"\*\*Verdict:\*\*\s*(.+?)(?=\n|$)", summary)
    if verdict_match:
        result["verdict"] = verdict_match.group(1).strip()

    return result


def _build_review_blocks(
    pr_url: str,
    pr_ref_text: str,
    parsed: dict,
    files_reviewed: int = 0,
    comments_count: int = 0,
) -> list[dict]:
    """Build Slack blocks for review notification."""
    issues_text = (
        "None" if not parsed["issues"] else "\n".join(f"• {i}" for i in parsed["issues"])
    )

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*<{pr_url}|{pr_ref_text}>*"},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "View PR", "emoji": True},
                "url": pr_url,
                "action_id": "view_pr_thread",
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
            "text": {"type": "mrkdwn", "text": f"*Issues Found*\n{issues_text}"},
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f":page_facing_up: *{files_reviewed}* files  |  :speech_balloon: *{comments_count}* comments",
                },
            ],
        },
    ]
    return blocks


async def add_reaction(channel: str, timestamp: str, emoji: str) -> None:
    """Add emoji reaction to a message."""
    try:
        client = get_slack_client()
        client.reactions_add(channel=channel, timestamp=timestamp, name=emoji)
    except Exception as e:
        logger.error(f"Failed to add reaction: {e}")


async def remove_reaction(channel: str, timestamp: str, emoji: str) -> None:
    """Remove emoji reaction from a message."""
    try:
        client = get_slack_client()
        client.reactions_remove(channel=channel, timestamp=timestamp, name=emoji)
    except Exception as e:
        logger.debug(f"Failed to remove reaction (may not exist): {e}")


async def send_thread_reply(
    channel: str,
    thread_ts: str,
    text: str,
    blocks: list | None = None,
) -> None:
    """Send a reply in a thread."""
    try:
        client = get_slack_client()
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=text,
            blocks=blocks,
        )
    except Exception as e:
        logger.error(f"Failed to send thread reply: {e}")


async def handle_app_mention(
    text: str,
    channel: str,
    thread_ts: str,
    user: str,
) -> None:
    """Handle an app mention event from Slack."""
    if extract_review_intent(text):
        await handle_review_request(channel, thread_ts, text, user)
    else:
        await send_thread_reply(
            channel=channel,
            thread_ts=thread_ts,
            text=(
                "Hi! I can help you review PRs. Try:\n"
                "* `@bot review #123`\n"
                "* `@bot review owner/repo#123`\n"
                "* `@bot review <github-pr-url>`"
            ),
        )


async def handle_review_request(
    channel: str,
    thread_ts: str,
    text: str,
    user: str,
) -> None:
    """Handle a review request from Slack."""
    from src.services.reviewer.service import review_pull_request

    pr_ref = parse_pr_reference(text)

    if not pr_ref:
        await send_thread_reply(
            channel=channel,
            thread_ts=thread_ts,
            text=(
                "I couldn't find a PR reference. Try:\n"
                "* `@bot review #123`\n"
                "* `@bot review owner/repo#123`\n"
                "* `@bot review https://github.com/owner/repo/pull/123`"
            ),
        )
        return

    await add_reaction(channel, thread_ts, "runner")

    try:
        result = await review_pull_request(
            owner=pr_ref.owner,
            repo=pr_ref.repo,
            pr_number=pr_ref.pr_number,
        )

        await remove_reaction(channel, thread_ts, "runner")
        await add_reaction(channel, thread_ts, "white_check_mark")

        summary = result.get("summary", "")
        parsed = _parse_review_summary(summary)
        pr_url = f"https://github.com/{pr_ref.owner}/{pr_ref.repo}/pull/{pr_ref.pr_number}"
        pr_ref_text = f"{pr_ref.owner}/{pr_ref.repo}#{pr_ref.pr_number}"

        blocks = _build_review_blocks(
            pr_url=pr_url,
            pr_ref_text=pr_ref_text,
            parsed=parsed,
            files_reviewed=result.get("files_reviewed", 0),
            comments_count=result.get("comments", 0),
        )

        await send_thread_reply(
            channel=channel,
            thread_ts=thread_ts,
            text=f"Reviewed {pr_ref_text}",
            blocks=blocks,
        )

    except Exception as e:
        logger.error(f"Review failed: {e}")
        await remove_reaction(channel, thread_ts, "runner")
        await add_reaction(channel, thread_ts, "x")
        await send_thread_reply(
            channel=channel,
            thread_ts=thread_ts,
            text=f"Review failed: {str(e)[:200]}",
        )


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
    """Send PR review notification to Slack channel."""
    target_channel = channel_id or settings.slack_channel_id

    if not target_channel:
        logger.warning("No Slack channel configured, skipping notification")
        return

    parsed = _parse_review_summary(summary)
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
            "text": {"type": "mrkdwn", "text": f"*Issues Found*\n{issues_text}"},
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
        dm = client.conversations_open(users=[slack_user_id])
        dm_channel = dm["channel"]["id"]

        issues_text = (
            "None" if not parsed["issues"] else "\n".join(f"• {i}" for i in parsed["issues"])
        )

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
                "text": {"type": "mrkdwn", "text": f"*<{pr_url}|{pr_title}>*"},
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
                "text": {"type": "mrkdwn", "text": f"*Issues Found*\n{issues_text}"},
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
