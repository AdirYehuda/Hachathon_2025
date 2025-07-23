from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.config import settings
from src.services.amazon_q_service import AmazonQService
from src.services.bedrock_service import BedrockService
from src.services.dashboard_service import DashboardService
from src.services.s3_service import S3Service

# Security
security = HTTPBearer(auto_error=False)


# Service dependencies
@lru_cache()
def get_amazon_q_service() -> AmazonQService:
    """Get Amazon Q service instance."""
    return AmazonQService(
        cli_path=getattr(settings, "amazon_q_cli_path", None),
        aws_profile=getattr(settings, "aws_profile", None),
        region=settings.aws_region,
    )


@lru_cache()
def get_bedrock_service() -> BedrockService:
    """Get Bedrock service instance."""
    return BedrockService(
        region=settings.bedrock_region,
        timeout=settings.bedrock_timeout,
        max_retries=settings.bedrock_max_retries,
        connect_timeout=settings.bedrock_connect_timeout
    )


@lru_cache()
def get_s3_service() -> S3Service:
    """Get S3 service instance."""
    if not settings.s3_bucket_name:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="S3 bucket configuration is missing",
        )

    return S3Service(
        bucket_name=settings.s3_bucket_name, 
        region=settings.s3_region,
        use_website_endpoint=settings.s3_use_website_endpoint
    )


@lru_cache()
def get_dashboard_service() -> DashboardService:
    """Get dashboard service instance."""
    return DashboardService()


# Authentication dependency (optional - can be removed if not needed)
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Optional authentication dependency.
    Remove or modify based on your security requirements.
    """
    if not credentials:
        # Allow unauthenticated access for now
        return None

    # Here you would typically validate the JWT token
    # For now, we'll just return a placeholder
    return {"user_id": "anonymous", "permissions": ["read", "write"]}


# Validation dependencies
def validate_aws_configuration():
    """Validate that AWS services are properly configured."""
    missing_configs = []

    # Check for Amazon Q CLI availability
    import shlex
    import subprocess

    try:
        cli_path = getattr(settings, "amazon_q_cli_path", "q")
        # Validate CLI path to prevent injection attacks
        if not cli_path or not isinstance(cli_path, str) or len(cli_path) > 255:
            missing_configs.append("AMAZON_Q_CLI (invalid path configuration)")
        else:
            # Use shell=False and properly escaped arguments for security
            result = subprocess.run(
                [cli_path, "--help"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )  # Explicitly disable shell for security
            if result.returncode != 0:
                missing_configs.append("AMAZON_Q_CLI (command 'q' not working)")
    except FileNotFoundError:
        missing_configs.append("AMAZON_Q_CLI (command 'q' not found)")
    except Exception:
        missing_configs.append("AMAZON_Q_CLI (unable to verify)")

    # Check other required configurations
    if not settings.bedrock_agent_id:
        missing_configs.append("BEDROCK_AGENT_ID")
    if not settings.s3_bucket_name:
        missing_configs.append("S3_BUCKET_NAME")

    if missing_configs:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Missing required configuration: {', '.join(missing_configs)}",
        )

    return True


# Type aliases for dependencies
AmazonQServiceDep = Annotated[AmazonQService, Depends(get_amazon_q_service)]
BedrockServiceDep = Annotated[BedrockService, Depends(get_bedrock_service)]
S3ServiceDep = Annotated[S3Service, Depends(get_s3_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
CurrentUserDep = Annotated[dict, Depends(get_current_user)]
ConfigValidationDep = Annotated[bool, Depends(validate_aws_configuration)]
