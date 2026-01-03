"""Slack event routes."""

import hashlib
import hmac
import time
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from src.config import settings
from src.core.logging import get_logger
from src.core.pr_parser import parse_pr_reference, extract_review_intent
from src.services.reviewer.service import review_pull_request
from src.services.slack.client import get_slack_client

logger = get_logger("slack.routes")

router = APIRouter()


def verify_slack_signature(
    body: bytes,
    timestamp: str,
    signature: str,
) -> bool:
    """Verify Slack request signature using HMAC-SHA256."""
    if not settings.slack_signing_secret:
        logger.warning("No Slack signing secret configured, skipping verification")
        return True

    current_time = int(time.time())
    if abs(current_time - int(timestamp)) > 300:
        logger.warning("Slack request timestamp too old")
        return False

    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    expected = (
        "v0="
        + hmac.new(
            settings.slack_signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(expected, signature)


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


async def send_thread_reply(channel: str, thread_ts: str, text: str) -> None:
    """Send a reply in a thread."""
    try:
        client = get_slack_client()
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=text)
    except Exception as e:
        logger.error(f"Failed to send thread reply: {e}")


async def handle_review_request(
    channel: str,
    thread_ts: str,
    text: str,
    user: str,
) -> None:
    """Handle a review request from Slack."""
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

        await send_thread_reply(
            channel=channel,
            thread_ts=thread_ts,
            text=(
                f"Reviewed *{pr_ref.owner}/{pr_ref.repo}#{pr_ref.pr_number}*\n\n"
                f"* Files reviewed: {result.get('files_reviewed', 0)}\n"
                f"* Comments: {result.get('comments', 0)}\n\n"
                f"{result.get('summary', '')[:500]}"
            ),
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


@router.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack events (app mentions)."""
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    body = await request.body()

    if not verify_slack_signature(body, timestamp, signature):
        logger.warning("Invalid Slack signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        event_type = event.get("type")

        logger.info(f"Slack event: {event_type}")

        if event_type == "app_mention":
            text = event.get("text", "")
            channel = event.get("channel")
            thread_ts = event.get("thread_ts") or event.get("ts")
            user = event.get("user")

            if extract_review_intent(text):
                background_tasks.add_task(
                    handle_review_request,
                    channel=channel,
                    thread_ts=thread_ts,
                    text=text,
                    user=user,
                )
                return {"ok": True, "message": "Processing review request"}
            else:
                background_tasks.add_task(
                    send_thread_reply,
                    channel=channel,
                    thread_ts=thread_ts,
                    text=(
                        "Hi! I can help you review PRs. Try:\n"
                        "* `@bot review #123`\n"
                        "* `@bot review owner/repo#123`\n"
                        "* `@bot review <github-pr-url>`"
                    ),
                )
                return {"ok": True, "message": "Sent help message"}

    return {"ok": True}
