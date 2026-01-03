"""Matter PR Reviewer - FastAPI entry point."""

from fastapi import FastAPI

from src.config import settings
from src.core.logging import get_logger

logger = get_logger("main")
from src.services.github.routes import router as github_router
from src.services.slack.routes import router as slack_router

app = FastAPI(
    title="Matter PR Reviewer",
    description="AI-powered GitHub PR reviewer",
    version="0.1.0",
)

# Include routes
app.include_router(github_router, prefix="/api")
app.include_router(slack_router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "matter-pr-reviewer",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Matter PR Reviewer on {settings.host}:{settings.port}")
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
