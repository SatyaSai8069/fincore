import time
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import Base, engine
from app.models import user as _user_models  # noqa: F401
from app.models import ledger as _ledger_models  # noqa: F401
from app.models import beneficiary as _beneficiary_models  # noqa: F401
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.accounts import router as accounts_router
from app.api.v1.transactions import router as transactions_router

settings = get_settings()
setup_logging(debug=settings.DEBUG)
logger = logging.getLogger("finora.middleware")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FINORA Digital Banking Platform API")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    logger.info("Shutting down FINORA Digital Banking Platform API")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="FINORA — International-Standard Digital Banking & Financial Intelligence Platform",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_and_tracing_headers(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(accounts_router, prefix=settings.API_V1_PREFIX)
app.include_router(transactions_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root() -> dict:
    return {
        "platform": "FINORA",
        "message": "Welcome to FINORA Digital Banking & Financial Intelligence API",
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
    }