"""AI Gateway - PII Detection & Masking Proxy for LLM."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import gateway, health
from app.services.llm_client import LlmClient
from app.services.pii_detector import PiiDetector
from app.stores.mapping_store import MappingStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup."""
    logger.info("Initializing PII Detector (loading spaCy models)...")
    app.state.pii_detector = PiiDetector()
    app.state.mapping_store = MappingStore()
    app.state.llm_client = LlmClient()
    logger.info("AI Gateway ready.")
    yield
    # Cleanup
    await app.state.mapping_store.close()


app = FastAPI(
    title="AI Gateway",
    description="PII Detection & Masking Proxy for LLM",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(gateway.router)

_tests_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests")
if os.path.isdir(_tests_dir):
    app.mount("/tests", StaticFiles(directory=_tests_dir, html=True), name="tests")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.gateway_host,
        port=settings.gateway_port,
        reload=True,
    )
