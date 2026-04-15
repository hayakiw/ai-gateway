"""Health check router."""

from fastapi import APIRouter, Request

from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """Health check endpoint."""
    try:
        await request.app.state.mapping_store._redis.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    return HealthResponse(status="ok", redis=redis_status)
