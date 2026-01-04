"""Matter PR Reviewer - FastAPI entry point."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.config import settings
from src.core.exceptions import ApiException
from src.core.logging import get_logger
from src.core.schemas.responses import ErrorResponse, HealthResponse
from src.services.github.routes import router as github_router
from src.services.slack.routes import router as slack_router

logger = get_logger("main")

app = FastAPI(
    title="Matter PR Reviewer",
    description="AI-powered GitHub PR reviewer",
    version="0.1.0",
)


@app.exception_handler(ApiException)
async def api_exception_handler(request: Request, exc: ApiException) -> JSONResponse:
    """Handle custom API exceptions and return structured error response."""
    logger.warning(f"API error: {exc.message} (status={exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.message,
            details=exc.details if exc.details else None,
        ).model_dump(),
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


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting Matter PR Reviewer on {settings.host}:{settings.port}")
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
