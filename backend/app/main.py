import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.routes_documents import router as documents_router
from app.api.v1.routes_facts import router as facts_router
from app.api.v1.routes_jobs import router as jobs_router
from app.api.v1.routes_relationships import router as relationships_router
from app.api.v1.routes_schema import router as schema_router
from app.api.v1.routes_compare import router as compare_router
from app.api.v1.routes_entities import router as entities_router
from app.api.v1.routes_analytics import router as analytics_router
from app.config import settings
from app.core.logging import setup_logging


setup_logging()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "A grounded fact knowledge layer for extracting, linking, "
        "and comparing facts across documents."
    ),
)

# Build CORS origins list.
# ALLOWED_ORIGINS env var accepts comma-separated URLs (set on Railway/Vercel).
_default_origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]
_extra = os.environ.get("ALLOWED_ORIGINS", "")
_extra_origins = [o.strip() for o in _extra.split(",") if o.strip()]
_allowed_origins = _default_origins + _extra_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health_check() -> dict:
    """
    Basic API health endpoint.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


app.include_router(
    documents_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    facts_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    jobs_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    relationships_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    schema_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    compare_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    entities_router,
    prefix=settings.api_v1_prefix,
)

app.include_router(
    analytics_router,
    prefix=settings.api_v1_prefix,
)
