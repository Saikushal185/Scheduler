"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import engine, session_scope
from app.core.exceptions import AppError
from app.core.logging_config import configure_logging, get_logger
from app.models import Base
from app.services.bootstrap import bootstrap_database

logger = get_logger(__name__)

DESCRIPTION = """
Automated interview scheduling and evaluation management.

* **Excel/CSV ingestion** with per-column validation
* **Faculty free-slot calculation** derived from availability and bookings
* **Constraint-based scheduling engine** (greedy and backtracking strategies)
* **Manual overrides** with conflict re-checks and full history
* **Configurable evaluation metrics** with weighted scoring and analytics
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("Starting %s v%s (%s)", settings.APP_NAME, settings.APP_VERSION,
                settings.ENVIRONMENT)
    Base.metadata.create_all(bind=engine)
    with session_scope() as db:
        bootstrap_database(db)
    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning("%s %s -> %s: %s", request.method, request.url.path, exc.code,
                   exc.message)
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request,
                             exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error",
                 "message": "The request payload is invalid",
                 "details": [{"field": ".".join(str(p) for p in err["loc"][1:]),
                              "message": err["msg"]} for err in exc.errors()]})


@app.exception_handler(IntegrityError)
async def integrity_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.error("Database integrity error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=409,
        content={"error": "integrity_error",
                 "message": "The change conflicts with existing data",
                 "details": str(exc.orig) if exc.orig else None})


@app.get("/health", tags=["System"], summary="Liveness probe")
def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT}


@app.get("/", tags=["System"], summary="Service metadata")
def root() -> dict[str, str]:
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION,
            "docs": "/docs", "api": settings.API_V1_PREFIX}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
