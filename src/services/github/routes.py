"""GitHub webhook routes - HTTP layer only."""

from fastapi import APIRouter, BackgroundTasks, Request

from src.core.logging import get_logger
from src.core.security import require_github_signature
from src.services.github.schemas import (
    ManualReviewRequest,
    PingResponse,
    ReviewStartedResponse,
)
from src.services.github.service import handle_pull_request_event, run_review

logger = get_logger("github.routes")
router = APIRouter()


@router.post("/review", response_model=ReviewStartedResponse)
async def manual_review(
    req: ManualReviewRequest,
    background_tasks: BackgroundTasks,
) -> ReviewStartedResponse:
    """Trigger a manual PR review."""
    logger.info(f"Manual review requested: {req.owner}/{req.repo}#{req.pr_number}")
    background_tasks.add_task(run_review, req.owner, req.repo, req.pr_number)
    return ReviewStartedResponse(pr=f"{req.owner}/{req.repo}#{req.pr_number}")


@router.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle GitHub webhook events."""
    event = request.headers.get("X-GitHub-Event")
    signature = request.headers.get("X-Hub-Signature-256", "")
    delivery_id = request.headers.get("X-GitHub-Delivery")

    logger.info(f"Webhook received: event={event}, delivery={delivery_id}")

    body = await request.body()
    require_github_signature(body, signature)

    payload = await request.json()

    if event == "pull_request":
        return await handle_pull_request_event(payload, background_tasks)
    elif event == "ping":
        return PingResponse(zen=payload.get("zen", ""))
    else:
        logger.info(f"Unhandled event type: {event}")
        return {"message": f"Event {event} not handled"}
