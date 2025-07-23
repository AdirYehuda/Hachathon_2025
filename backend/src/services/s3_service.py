import json
import logging
from functools import wraps
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def handle_aws_errors(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(f"AWS Error in {func.__name__}: {error_code} - {e}")
            raise HTTPException(
                status_code=500, detail=f"AWS service error: {error_code}"
            )
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    return wrapper


class S3Service:
    def __init__(self, bucket_name: str, region: str = "us-east-1", use_website_endpoint: bool = True):
        self.s3_client = boto3.client("s3", region_name=region)
        self.bucket_name = bucket_name
        self.region = region
        self.use_website_endpoint = use_website_endpoint

    @handle_aws_errors
    async def upload_static_site(
        self,
        html_content: str,
        site_id: str,
        additional_files: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload static site to S3 and return public URL."""
        try:
            # Upload main HTML file
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=f"{site_id}/index.html",
                Body=html_content,
                ContentType="text/html",
            )

            # Upload additional files (CSS, JS, etc.)
            if additional_files:
                for file_path, content in additional_files.items():
                    content_type = self._get_content_type(file_path)
                    self.s3_client.put_object(
                        Bucket=self.bucket_name,
                        Key=f"{site_id}/{file_path}",
                        Body=content,
                        ContentType=content_type,
                    )

            # Configure website hosting if not already done
            await self._configure_website_hosting()
            
            # Configure bucket policy for public read access
            await self._configure_public_read_policy()

            # Return public URL pointing directly to index.html for reliability
            if self.use_website_endpoint:
                return f"https://{self.bucket_name}.s3-website-{self.region}.amazonaws.com/{site_id}/index.html"
            else:
                return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{site_id}/index.html"

        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise

    @handle_aws_errors
    async def _configure_website_hosting(self):
        """Configure S3 bucket for static website hosting."""
        try:
            website_config = {
                "IndexDocument": {"Suffix": "index.html"},
                "ErrorDocument": {"Key": "error.html"},
            }

            self.s3_client.put_bucket_website(
                Bucket=self.bucket_name, WebsiteConfiguration=website_config
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchWebsiteConfiguration":
                logger.error(f"Website configuration error: {e}")
                raise

    @handle_aws_errors
    async def _configure_public_read_policy(self):
        """Configure S3 bucket policy for public read access."""
        try:
            # Define bucket policy for public read access
            bucket_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PublicReadGetObject",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{self.bucket_name}/*"
                    }
                ]
            }

            # Convert policy to JSON string
            policy_json = json.dumps(bucket_policy)

            # Apply bucket policy
            self.s3_client.put_bucket_policy(
                Bucket=self.bucket_name,
                Policy=policy_json
            )
            
            logger.info(f"Bucket policy configured for public read access on {self.bucket_name}")
            
        except ClientError as e:
            # If policy already exists or we don't have permission, log but don't fail
            error_code = e.response["Error"]["Code"]
            if error_code in ["NoSuchBucketPolicy", "AccessDenied"]:
                logger.warning(f"Could not set bucket policy: {error_code}. Ensure bucket has public read access configured.")
            else:
                logger.error(f"Bucket policy configuration error: {e}")
                raise

    def _get_content_type(self, file_path: str) -> str:
        """Get content type based on file extension."""
        extensions = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
        }

        for ext, content_type in extensions.items():
            if file_path.endswith(ext):
                return content_type

        return "application/octet-stream"

    @handle_aws_errors
    async def create_embed_code(
        self, dashboard_url: str, width: str = "100%", height: str = "600px"
    ) -> str:
        """Create embeddable iframe code for the dashboard."""
        embed_code = f'<iframe src="{dashboard_url}" width="{width}" height="{height}" frameborder="0" allowfullscreen></iframe>'
        return embed_code

    @handle_aws_errors
    async def list_dashboards(self) -> List[Dict]:
        """List all deployed dashboards."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Delimiter="/"
            )

            dashboards = []
            for prefix in response.get("CommonPrefixes", []):
                site_id = prefix["Prefix"].rstrip("/")
                if self.use_website_endpoint:
                    url = f"https://{self.bucket_name}.s3-website-{self.region}.amazonaws.com/{site_id}/index.html"
                else:
                    url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{site_id}/index.html"
                dashboards.append(
                    {
                        "site_id": site_id,
                        "url": url,
                        "created": "N/A",  # Could be enhanced to get actual creation time
                    }
                )

            return dashboards
        except ClientError as e:
            logger.error(f"Error listing dashboards: {e}")
            raise
