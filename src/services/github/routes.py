"""GitHub webhook routes."""

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from loguru import logger

from src.services.github.client import verify_webhook_signature
from src.services.reviewer.service import review_pull_request

router = APIRouter()


@router.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle GitHub webhook events."""
    event = request.headers.get("X-GitHub-Event")
    signature = request.headers.get("X-Hub-Signature-256", "")
    delivery_id = request.headers.get("X-GitHub-Delivery")

    logger.info(f"Webhook received: event={event}, delivery={delivery_id}")

    body = await request.body()

    if not verify_webhook_signature(body, signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    if event == "pull_request":
        return await handle_pull_request(payload, background_tasks)
    elif event == "ping":
        return {"message": "pong", "zen": payload.get("zen", "")}
    else:
        logger.info(f"Unhandled event type: {event}")
        return {"message": f"Event {event} not handled"}


async def handle_pull_request(payload: dict, background_tasks: BackgroundTasks):
    """Handle pull_request events."""
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})

    owner = repo.get("owner", {}).get("login")
    repo_name = repo.get("name")
    pr_number = pr.get("number")

    logger.info(f"PR event: {action} on {owner}/{repo_name}#{pr_number}")

    if action not in ("opened", "synchronize"):
        return {
            "message": f"Action {action} not reviewed",
            "supported_actions": ["opened", "synchronize"],
        }

    background_tasks.add_task(
        run_review,
        owner=owner,
        repo=repo_name,
        pr_number=pr_number,
    )

    return {
        "message": "Review started",
        "pr": f"{owner}/{repo_name}#{pr_number}",
        "action": action,
    }


async def run_review(owner: str, repo: str, pr_number: int):
    """Run the review in background."""
    try:
        result = await review_pull_request(owner, repo, pr_number)
        logger.info(f"Review completed: {result}")
    except Exception as e:
        logger.error(f"Review failed: {e}")
