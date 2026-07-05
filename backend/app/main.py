"""FastAPI entry point for Video-Generate backend."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import engine, Base
from .routers import auth, tasks, videos, voices, prompts, health, analysis
from .routers import admin, api_keys, webhooks, billing
from .routers import remake
from .middleware import RateLimitMiddleware

app = FastAPI(
    title="Video-Generate API",
    version="0.1.0",
    description="AI-powered video generation platform",
)

# CORS — allow frontend origins (must be added before other middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8082",
        "http://10.190.0.222:3000",
        "http://10.190.0.222:8082",
        "http://10.190.0.222:8001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware
app.add_middleware(
    RateLimitMiddleware,
    default_limit=60,
    window_seconds=60,
)

# Existing routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(videos.router, prefix="/api/v1/videos", tags=["videos"])
app.include_router(voices.router, prefix="/api/v1/voices", tags=["voices"])
app.include_router(prompts.router, prefix="/api/v1/prompts", tags=["prompts"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["analysis"])

# Phase 3 routers
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(api_keys.router, prefix="/api/v1/api-keys", tags=["api-keys"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["billing"])

# Path B: Face swap + voice clone

# Serve task output files
app.mount("/api/v1/remake/files", StaticFiles(directory="/data/output/tasks"), name="output_files")
app.include_router(remake.router, prefix="/api/v1/remake", tags=["remake"])


@app.on_event("startup")
async def startup():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        # ENUM type may already exist from another worker
        pass
