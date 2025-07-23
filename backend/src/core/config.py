import secrets
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Configuration
    api_title: str = "Amazon Q Wrapper API"
    api_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    # AWS Configuration
    aws_region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_profile: Optional[str] = None

    # Amazon Q Developer CLI Configuration
    amazon_q_cli_path: Optional[str] = None  # Path to Amazon Q CLI executable
    amazon_q_default_region: str = "us-east-1"
    amazon_q_cli_timeout: int = 300  # CLI command timeout in seconds
    amazon_q_cli_max_retries: int = 3  # Maximum retry attempts
    amazon_q_cli_output_format: str = "json"  # Output format preference
    amazon_q_cli_working_dir: Optional[str] = None  # Working directory for CLI commands

    # Amazon Q Configuration (legacy support)
    amazon_q_application_id: str = ""
    amazon_q_user_id: str = ""

    # Bedrock Configuration
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    bedrock_agent_id: str = ""
    bedrock_agent_alias_id: str = "TSTALIASID"
    bedrock_region: str = "us-east-1"
    bedrock_timeout: int = 600  # Increased to 10 minutes for complex agent processing
    bedrock_max_retries: int = 3
    bedrock_connect_timeout: int = 60

    # S3 Configuration
    s3_bucket_name: str = ""
    s3_region: str = "us-east-1"
    s3_force_path_style: bool = False
    s3_endpoint_url: Optional[str] = None
    s3_use_website_endpoint: bool = False  # Set to False to remove "website" from URLs

    # Security Configuration
    secret_key: str = secrets.token_urlsafe(32)  # Auto-generate secure key if not provided
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    allowed_origins: str = "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000"

    # Database Configuration
    database_url: str = "sqlite:///./app.db"

    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    cache_ttl_short: int = 300  # 5 minutes
    cache_ttl_medium: int = 3600  # 1 hour
    cache_ttl_long: int = 86400  # 24 hours

    # Logging Configuration
    log_level: str = "INFO"
    log_file_path: Optional[str] = None
    log_format: str = "json"

    # Dashboard Configuration
    dashboard_default_width: str = "100%"
    dashboard_default_height: str = "600px"
    dashboard_theme: str = "light"
    chart_default_color_scheme: str = "viridis"
    chart_animation_enabled: bool = True

    # Performance & Monitoring
    max_request_size: str = "10MB"
    request_timeout: int = 300
    health_check_timeout: int = 10
    health_check_retry_count: int = 3

    # Feature Flags
    feature_email_notifications: bool = False
    feature_advanced_analytics: bool = True
    feature_async_processing: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables (like REACT_APP_*)


settings = Settings()
