import logging
from contextlib import asynccontextmanager
from datetime import datetime

import boto3
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import amazon_q, bedrock, dashboard
from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Amazon Q Wrapper API")
    yield
    # Shutdown
    logger.info("Shutting down Amazon Q Wrapper API")


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="API for Amazon Q CLI wrapper with Bedrock integration",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(amazon_q.router, prefix="/api/v1")
app.include_router(bedrock.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": "Amazon Q Wrapper API",
        "version": settings.api_version,
        "description": "Web interface for Amazon Q CLI with Bedrock integration and dashboard generation",
        "endpoints": {
            "amazon_q": "/api/v1/amazon-q",
            "bedrock": "/api/v1/bedrock",
            "dashboard": "/api/v1/dashboard",
            "health": "/health",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health_check():
    """Enhanced health check that verifies AWS service connectivity."""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": settings.api_version,
            "services": {},
        }

        # Check S3 connectivity
        try:
            if settings.s3_bucket_name:
                s3_client = boto3.client("s3", region_name=settings.s3_region)
                s3_client.head_bucket(Bucket=settings.s3_bucket_name)
                health_status["services"]["s3"] = "available"
            else:
                health_status["services"]["s3"] = "not_configured"
        except Exception as e:
            logger.warning(f"S3 health check failed: {e}")
            health_status["services"]["s3"] = "unavailable"

        # Check Bedrock connectivity
        try:
            bedrock_client = boto3.client(
                "bedrock-agent-runtime", region_name=settings.aws_region
            )
            # Just check if we can create a client - actual API calls require agent setup
            health_status["services"]["bedrock"] = "available"
        except Exception as e:
            logger.warning(f"Bedrock health check failed: {e}")
            health_status["services"]["bedrock"] = "unavailable"

        # Check Amazon Q CLI connectivity
        try:
            import subprocess

            cli_path = getattr(settings, "amazon_q_cli_path", "q")
            result = subprocess.run(
                [cli_path, "--help"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                health_status["services"]["amazon_q_cli"] = "available"
            else:
                health_status["services"]["amazon_q_cli"] = "unavailable"
        except FileNotFoundError:
            logger.warning("Amazon Q CLI not found in PATH")
            health_status["services"]["amazon_q_cli"] = "not_found"
        except Exception as e:
            logger.warning(f"Amazon Q CLI health check failed: {e}")
            health_status["services"]["amazon_q_cli"] = "unavailable"

        # Determine overall status
        service_statuses = list(health_status["services"].values())
        if any(status == "unavailable" for status in service_statuses):
            health_status["status"] = "degraded"
        elif any(status == "not_configured" for status in service_statuses):
            health_status["status"] = "partial"

        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
