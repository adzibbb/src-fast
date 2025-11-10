# main.py
import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from sqlalchemy import text

from app.api.routes import auth, posts, comments, votes, notifications, leaderboard
from app.websocket.endpoints import router as websocket_router
from app.database import engine
from app.models import user, post, comment, vote, notification
from app.core.config import settings

logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Stress Relief Chatter API")

    # Don't create tables in production - use migrations instead
    if settings.ENVIRONMENT == "development":
        logger.info("Creating database tables (development mode)")
        user.Base.metadata.create_all(bind=engine)
        post.Base.metadata.create_all(bind=engine)
        comment.Base.metadata.create_all(bind=engine)
        vote.Base.metadata.create_all(bind=engine)
        notification.Base.metadata.create_all(bind=engine)

    yield

    # Shutdown
    logger.info("Shutting down Stress Relief Chatter API")
    # Engine cleanup happens automatically


app = FastAPI(
    title="Stress Relief Chatter API",
    version="1.0.0",
    lifespan=lifespan,  # Use lifespan instead of deprecated events
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None
)

# Security middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# CORS middleware with production settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # Don't use ["*"] in production!
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Compression middleware for performance
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])
app.include_router(comments.router, prefix="/api/posts", tags=["comments"])
app.include_router(votes.router, prefix="/api/posts", tags=["votes"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(leaderboard.router, prefix="/api/leaderboard", tags=["leaderboard"])
app.include_router(websocket_router, prefix="/ws", tags=["websocket"])


@app.get("/")
def read_root():
    return {"message": "Stress Relief Chatter API"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/deep-health")
async def deep_health_check():
    """Deep health check that verifies database connectivity"""
    try:
        # Test database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")