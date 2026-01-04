"""Slack event routes - HTTP layer only."""

from fastapi import APIRouter, BackgroundTasks, Request

from src.core.logging import get_logger
from src.core.security import require_slack_signature
from src.services.slack.schemas import SlackChallengeResponse, SlackEventResponse
from src.services.slack.service import handle_app_mention

logger = get_logger("slack.routes")
router = APIRouter()


@router.post("/slack/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
) -> SlackEventResponse | SlackChallengeResponse:
    """Handle Slack events (app mentions)."""
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    body = await request.body()
    require_slack_signature(body, timestamp, signature)

    payload = await request.json()

    # URL verification challenge
    if payload.get("type") == "url_verification":
        return SlackChallengeResponse(challenge=payload.get("challenge", ""))

    # Event callback
    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        event_type = event.get("type")

        logger.info(f"Slack event: {event_type}")

        if event_type == "app_mention":
            background_tasks.add_task(
                handle_app_mention,
                text=event.get("text", ""),
                channel=event.get("channel"),
                thread_ts=event.get("thread_ts") or event.get("ts"),
                user=event.get("user"),
            )
            return SlackEventResponse(message="Processing mention")

    return SlackEventResponse()
