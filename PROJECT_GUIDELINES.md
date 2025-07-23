# Amazon Q CLI Wrapper Project Guidelines

## Project Overview
This project creates a web-based interface that wraps Amazon Q CLI to:
1. Query Amazon Q for cost optimization and under-utilization insights
2. Process JSON data through Bedrock agents for comprehensive analysis
3. Generate dashboard UIs with findings
4. Deploy dashboards to S3 static hosting
5. Provide embeddable widgets for integration

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Frontend  │───▶│  Python Backend  │───▶│   Amazon Q CLI  │
│   (React/Vue)   │    │   (FastAPI)      │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   S3 Static     │◀───│  Bedrock Agent   │───▶│  Dashboard Gen  │
│   Hosting       │    │   Processing     │    │   (Plotly/D3)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 1. Project Structure & Organization

### Recommended Directory Structure
```
amazon-q-wrapper/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── amazon_q.py
│   │   │   │   ├── bedrock.py
│   │   │   │   └── dashboard.py
│   │   │   └── dependencies.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── logging.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── amazon_q_service.py
│   │   │   ├── bedrock_service.py
│   │   │   ├── s3_service.py
│   │   │   └── dashboard_service.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── requests.py
│   │   │   └── responses.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── validators.py
│   │       └── helpers.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── Dockerfile
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── utils/
│   ├── public/
│   ├── package.json
│   └── Dockerfile
├── infrastructure/
│   ├── terraform/
│   │   ├── modules/
│   │   ├── environments/
│   │   └── main.tf
│   └── cloudformation/
├── scripts/
│   ├── deploy.sh
│   └── setup.py
├── docs/
│   ├── api/
│   └── deployment/
├── .github/
│   └── workflows/
├── docker-compose.yml
├── .env.template
├── .gitignore
└── README.md
```

## 2. Python Best Practices

### 2.1 Code Quality & Standards

#### Use Type Hints
```python
from typing import List, Dict, Optional, Union
from pydantic import BaseModel

class CostOptimizationQuery(BaseModel):
    query: str
    time_range: Optional[str] = "30d"
    resource_types: List[str] = []
    
async def query_amazon_q(
    query: CostOptimizationQuery,
    session: AsyncSession
) -> Dict[str, Union[str, List[Dict]]]:
    """Query Amazon Q for cost optimization insights."""
    pass
```

#### Use Pydantic for Data Validation
```python
from pydantic import BaseModel, validator, Field

class BedrockProcessingRequest(BaseModel):
    data_objects: List[Dict] = Field(..., min_items=1)
    processing_type: str = Field(..., regex="^(summary|analysis|report)$")
    
    @validator('data_objects')
    def validate_data_objects(cls, v):
        for obj in v:
            if not isinstance(obj, dict) or not obj:
                raise ValueError("Each data object must be a non-empty dictionary")
        return v
```

#### Error Handling & Logging
```python
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)

def handle_aws_errors(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"AWS Error in {func.__name__}: {error_code} - {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"AWS service error: {error_code}"
            )
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    return wrapper
```

### 2.2 Dependency Management

#### requirements.txt (Production)
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
boto3==1.34.0
botocore==1.34.0
aiofiles==23.2.1
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-dotenv==1.0.0
structlog==23.2.0
tenacity==8.2.3
plotly==5.17.0
jinja2==3.1.2
```

#### requirements-dev.txt (Development)
```
-r requirements.txt
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
black==23.11.0
isort==5.12.0
flake8==6.1.0
mypy==1.7.1
pre-commit==3.6.0
httpx==0.25.2
factory-boy==3.3.0
```

### 2.3 Configuration Management

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Configuration
    api_title: str = "Amazon Q Wrapper API"
    api_version: str = "1.0.0"
    debug: bool = False
    
    # AWS Configuration
    aws_region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    
    # Amazon Q Configuration
    amazon_q_application_id: str
    amazon_q_user_id: str
    
    # Bedrock Configuration
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    bedrock_agent_id: str
    bedrock_agent_alias_id: str = "TSTALIASID"
    
    # S3 Configuration
    s3_bucket_name: str
    s3_region: str = "us-east-1"
    
    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

## 3. AWS Best Practices

### 3.1 IAM Policies & Security

#### Principle of Least Privilege
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "q:Chat",
                "q:ListConversations",
                "q:GetConversation"
            ],
            "Resource": "arn:aws:q:*:*:application/${amazon_q_application_id}"
        },
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeAgent",
                "bedrock:Retrieve"
            ],
            "Resource": [
                "arn:aws:bedrock:*:*:agent/${bedrock_agent_id}",
                "arn:aws:bedrock:*:*:knowledge-base/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:PutObjectAcl",
                "s3:GetObject"
            ],
            "Resource": "arn:aws:s3:::${bucket_name}/*"
        }
    ]
}
```

### 3.2 AWS Service Integration

#### Amazon Q Service Wrapper
```python
import boto3
from botocore.exceptions import ClientError
from typing import Dict, List, Optional

class AmazonQService:
    def __init__(self, application_id: str, user_id: str, region: str = "us-east-1"):
        self.client = boto3.client('qbusiness', region_name=region)
        self.application_id = application_id
        self.user_id = user_id
    
    @handle_aws_errors
    async def chat(
        self, 
        message: str, 
        conversation_id: Optional[str] = None
    ) -> Dict:
        """Send a chat message to Amazon Q."""
        try:
            response = self.client.chat(
                applicationId=self.application_id,
                userId=self.user_id,
                userMessage=message,
                conversationId=conversation_id
            )
            return {
                "response": response.get('systemMessage', ''),
                "conversation_id": response.get('conversationId'),
                "source_attributions": response.get('sourceAttributions', [])
            }
        except ClientError as e:
            logger.error(f"Amazon Q chat error: {e}")
            raise
    
    @handle_aws_errors
    async def query_cost_optimization(self, query: str) -> Dict:
        """Query Amazon Q for cost optimization insights."""
        cost_query = f"""
        Please analyze cost optimization opportunities for: {query}
        
        Focus on:
        1. Under-utilized resources
        2. Right-sizing recommendations
        3. Reserved instance opportunities
        4. Storage optimization
        5. Network cost reduction
        
        Provide specific, actionable recommendations with estimated savings.
        """
        
        return await self.chat(cost_query)
```

#### Bedrock Agent Service
```python
import boto3
import json
from typing import Dict, List

class BedrockService:
    def __init__(self, region: str = "us-east-1"):
        self.client = boto3.client('bedrock-agent-runtime', region_name=region)
    
    @handle_aws_errors
    async def invoke_agent(
        self, 
        agent_id: str,
        agent_alias_id: str,
        session_id: str,
        input_text: str
    ) -> Dict:
        """Invoke Bedrock agent for processing."""
        try:
            response = self.client.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                sessionId=session_id,
                inputText=input_text
            )
            
            # Process streaming response
            result = ""
            for event in response['completion']:
                if 'chunk' in event:
                    chunk = event['chunk']
                    if 'bytes' in chunk:
                        result += chunk['bytes'].decode('utf-8')
            
            return {"response": result}
        except ClientError as e:
            logger.error(f"Bedrock agent error: {e}")
            raise
    
    async def process_data_objects(
        self, 
        data_objects: List[Dict],
        agent_id: str,
        agent_alias_id: str
    ) -> Dict:
        """Process multiple data objects through Bedrock agent."""
        session_id = f"session-{int(time.time())}"
        
        # Prepare input for agent
        input_data = {
            "task": "analyze_and_summarize",
            "data_objects": data_objects,
            "output_format": "comprehensive_report"
        }
        
        input_text = f"""
        Please analyze the following data objects and create a comprehensive report:
        
        {json.dumps(input_data, indent=2)}
        
        Consolidate all findings into a single, well-structured document with:
        1. Executive summary
        2. Key findings by category
        3. Recommendations
        4. Supporting data and metrics
        """
        
        return await self.invoke_agent(
            agent_id=agent_id,
            agent_alias_id=agent_alias_id,
            session_id=session_id,
            input_text=input_text
        )
```

#### S3 Service for Static Hosting
```python
import boto3
import json
from typing import Dict, Optional

class S3Service:
    def __init__(self, bucket_name: str, region: str = "us-east-1"):
        self.s3_client = boto3.client('s3', region_name=region)
        self.bucket_name = bucket_name
        self.region = region
    
    @handle_aws_errors
    async def upload_static_site(
        self, 
        html_content: str, 
        site_id: str,
        additional_files: Optional[Dict[str, str]] = None
    ) -> str:
        """Upload static site to S3 and return public URL."""
        try:
            # Upload main HTML file
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=f"{site_id}/index.html",
                Body=html_content,
                ContentType='text/html',
                ACL='public-read'
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
                        ACL='public-read'
                    )
            
            # Configure website hosting if not already done
            await self._configure_website_hosting()
            
            # Return public URL
            return f"https://{self.bucket_name}.s3-website-{self.region}.amazonaws.com/{site_id}"
            
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
            raise
    
    async def _configure_website_hosting(self):
        """Configure S3 bucket for static website hosting."""
        try:
            website_config = {
                'IndexDocument': {'Suffix': 'index.html'},
                'ErrorDocument': {'Key': 'error.html'}
            }
            
            self.s3_client.put_bucket_website(
                Bucket=self.bucket_name,
                WebsiteConfiguration=website_config
            )
        except ClientError as e:
            if e.response['Error']['Code'] != 'NoSuchWebsiteConfiguration':
                logger.error(f"Website configuration error: {e}")
                raise
    
    def _get_content_type(self, file_path: str) -> str:
        """Get content type based on file extension."""
        extensions = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml'
        }
        
        for ext, content_type in extensions.items():
            if file_path.endswith(ext):
                return content_type
        
        return 'application/octet-stream'
```

### 3.3 Cost Optimization

#### Resource Tagging Strategy
```python
def get_resource_tags() -> Dict[str, str]:
    """Standard tags for all AWS resources."""
    return {
        "Project": "amazon-q-wrapper",
        "Environment": settings.environment,
        "Owner": "data-engineering-team",
        "CostCenter": "analytics",
        "AutoShutdown": "enabled"
    }
```

#### S3 Lifecycle Policies
```json
{
    "Rules": [
        {
            "ID": "dashboard-cleanup",
            "Status": "Enabled",
            "Filter": {
                "Prefix": "dashboards/"
            },
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "Days": 90,
                    "StorageClass": "GLACIER"
                }
            ],
            "Expiration": {
                "Days": 365
            }
        }
    ]
}
```

## 4. API Design & FastAPI Implementation

### 4.1 Main Application Setup
```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager

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
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "*.yourdomain.com"]
)
```

### 4.2 API Routes
```python
from fastapi import APIRouter, Depends, BackgroundTasks
from typing import Dict, List

router = APIRouter(prefix="/api/v1", tags=["amazon-q"])

@router.post("/query/cost-optimization")
async def query_cost_optimization(
    request: CostOptimizationQuery,
    amazon_q: AmazonQService = Depends(get_amazon_q_service)
) -> Dict:
    """Query Amazon Q for cost optimization insights."""
    result = await amazon_q.query_cost_optimization(request.query)
    return {
        "query": request.query,
        "response": result["response"],
        "conversation_id": result["conversation_id"],
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/process/bedrock")
async def process_with_bedrock(
    request: BedrockProcessingRequest,
    bedrock: BedrockService = Depends(get_bedrock_service)
) -> Dict:
    """Process data objects through Bedrock agent."""
    result = await bedrock.process_data_objects(
        data_objects=request.data_objects,
        agent_id=settings.bedrock_agent_id,
        agent_alias_id=settings.bedrock_agent_alias_id
    )
    return {
        "processed_data": result["response"],
        "processing_type": request.processing_type,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/dashboard/generate")
async def generate_dashboard(
    request: DashboardGenerationRequest,
    background_tasks: BackgroundTasks,
    dashboard_service: DashboardService = Depends(get_dashboard_service),
    s3_service: S3Service = Depends(get_s3_service)
) -> Dict:
    """Generate dashboard from summary data and deploy to S3."""
    
    # Generate dashboard HTML
    dashboard_html = await dashboard_service.create_dashboard(
        summary_data=request.summary_data,
        dashboard_type=request.dashboard_type
    )
    
    # Generate unique site ID
    site_id = f"dashboard-{uuid.uuid4().hex[:8]}"
    
    # Upload to S3
    public_url = await s3_service.upload_static_site(
        html_content=dashboard_html,
        site_id=site_id,
        additional_files=dashboard_service.get_static_assets()
    )
    
    return {
        "dashboard_url": public_url,
        "site_id": site_id,
        "embed_code": f'<iframe src="{public_url}" width="100%" height="600px"></iframe>',
        "timestamp": datetime.utcnow().isoformat()
    }
```

## 5. Dashboard Generation Service

### 5.1 Dashboard Service Implementation
```python
import plotly.graph_objects as go
import plotly.express as px
from plotly.offline import plot
from jinja2 import Template
from typing import Dict, List

class DashboardService:
    def __init__(self):
        self.template_loader = Template(self._get_html_template())
    
    async def create_dashboard(
        self, 
        summary_data: Dict, 
        dashboard_type: str = "cost_optimization"
    ) -> str:
        """Create interactive dashboard from summary data."""
        
        # Parse data and create visualizations
        charts = await self._create_charts(summary_data, dashboard_type)
        
        # Generate HTML with embedded charts
        dashboard_html = self.template_loader.render(
            title=f"Cost Optimization Dashboard - {datetime.now().strftime('%Y-%m-%d')}",
            charts=charts,
            summary=summary_data.get("executive_summary", ""),
            recommendations=summary_data.get("recommendations", [])
        )
        
        return dashboard_html
    
    async def _create_charts(self, data: Dict, dashboard_type: str) -> List[str]:
        """Create Plotly charts based on data and dashboard type."""
        charts = []
        
        if dashboard_type == "cost_optimization":
            # Cost savings chart
            if "cost_savings" in data:
                fig = px.bar(
                    x=list(data["cost_savings"].keys()),
                    y=list(data["cost_savings"].values()),
                    title="Potential Cost Savings by Category",
                    labels={"x": "Category", "y": "Savings ($)"}
                )
                charts.append(plot(fig, output_type='div', include_plotlyjs=False))
            
            # Resource utilization chart
            if "utilization" in data:
                fig = go.Figure(data=go.Scatter(
                    x=data["utilization"]["timestamps"],
                    y=data["utilization"]["cpu_usage"],
                    mode='lines+markers',
                    name='CPU Utilization'
                ))
                fig.update_layout(title="Resource Utilization Over Time")
                charts.append(plot(fig, output_type='div', include_plotlyjs=False))
        
        return charts
    
    def _get_html_template(self) -> str:
        """HTML template for dashboard."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ title }}</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { text-align: center; color: #333; }
                .summary { background: #f5f5f5; padding: 20px; border-radius: 5px; margin: 20px 0; }
                .chart-container { margin: 30px 0; }
                .recommendations { background: #e8f4fd; padding: 20px; border-radius: 5px; }
                .recommendation-item { margin: 10px 0; padding: 10px; background: white; border-radius: 3px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{{ title }}</h1>
            </div>
            
            <div class="summary">
                <h2>Executive Summary</h2>
                <p>{{ summary }}</p>
            </div>
            
            {% for chart in charts %}
            <div class="chart-container">
                {{ chart|safe }}
            </div>
            {% endfor %}
            
            <div class="recommendations">
                <h2>Recommendations</h2>
                {% for rec in recommendations %}
                <div class="recommendation-item">
                    <strong>{{ rec.category }}:</strong> {{ rec.description }}
                    {% if rec.estimated_savings %}
                    <br><em>Estimated Savings: ${{ rec.estimated_savings }}</em>
                    {% endif %}
                </div>
                {% endfor %}
            </div>
        </body>
        </html>
        """
    
    def get_static_assets(self) -> Dict[str, str]:
        """Return additional CSS/JS files if needed."""
        return {
            "styles.css": """
                /* Additional custom styles */
                .highlight { background-color: #fff3cd; padding: 2px 4px; }
                .metric { font-size: 1.2em; font-weight: bold; color: #007bff; }
            """
        }
```

## 6. Testing Strategy

### 6.1 Unit Tests
```python
import pytest
from unittest.mock import Mock, patch
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_cost_optimization_query():
    """Test Amazon Q cost optimization query."""
    mock_response = {
        "response": "Here are cost optimization recommendations...",
        "conversation_id": "conv-123",
        "source_attributions": []
    }
    
    with patch('services.amazon_q_service.AmazonQService.chat') as mock_chat:
        mock_chat.return_value = mock_response
        
        service = AmazonQService("app-id", "user-id")
        result = await service.query_cost_optimization("EC2 optimization")
        
        assert result["response"] == mock_response["response"]
        assert result["conversation_id"] == mock_response["conversation_id"]

@pytest.mark.asyncio
async def test_dashboard_generation():
    """Test dashboard generation from summary data."""
    sample_data = {
        "executive_summary": "Cost savings identified",
        "cost_savings": {"EC2": 1000, "S3": 500},
        "recommendations": [
            {"category": "EC2", "description": "Right-size instances", "estimated_savings": 1000}
        ]
    }
    
    service = DashboardService()
    dashboard_html = await service.create_dashboard(sample_data)
    
    assert "Cost Optimization Dashboard" in dashboard_html
    assert "Cost savings identified" in dashboard_html
    assert "plotly" in dashboard_html.lower()
```

### 6.2 Integration Tests
```python
@pytest.mark.asyncio
async def test_full_workflow_integration():
    """Test complete workflow from Q query to dashboard deployment."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Step 1: Query Amazon Q
        q_response = await client.post("/api/v1/query/cost-optimization", json={
            "query": "Analyze EC2 costs",
            "time_range": "30d"
        })
        assert q_response.status_code == 200
        
        # Step 2: Process with Bedrock
        bedrock_response = await client.post("/api/v1/process/bedrock", json={
            "data_objects": [q_response.json()],
            "processing_type": "summary"
        })
        assert bedrock_response.status_code == 200
        
        # Step 3: Generate dashboard
        dashboard_response = await client.post("/api/v1/dashboard/generate", json={
            "summary_data": bedrock_response.json()["processed_data"],
            "dashboard_type": "cost_optimization"
        })
        assert dashboard_response.status_code == 200
        assert "dashboard_url" in dashboard_response.json()
```

## 7. Security Best Practices

### 7.1 Authentication & Authorization
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import secrets

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate JWT token and return current user."""
    try:
        payload = jwt.decode(
            credentials.credentials, 
            settings.secret_key, 
            algorithms=[settings.algorithm]
        )
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        return username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
```

### 7.2 Input Validation & Sanitization
```python
from pydantic import validator, Field
import re

class SecureRequest(BaseModel):
    query: str = Field(..., max_length=1000)
    
    @validator('query')
    def validate_query(cls, v):
        # Remove potentially dangerous characters
        if re.search(r'[<>"\']', v):
            raise ValueError("Query contains invalid characters")
        return v.strip()
```

## 8. Deployment & DevOps

### 8.1 Docker Configuration
```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 8.2 Infrastructure as Code (Terraform)
```hcl
# infrastructure/terraform/main.tf
provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "dashboard_hosting" {
  bucket = "${var.project_name}-dashboards-${random_id.bucket_suffix.hex}"
  
  tags = {
    Name        = "Dashboard Hosting"
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_s3_bucket_website_configuration" "dashboard_hosting" {
  bucket = aws_s3_bucket.dashboard_hosting.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "error.html"
  }
}

resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}
```

### 8.3 CI/CD Pipeline (.github/workflows/deploy.yml)
```yaml
name: Deploy Amazon Q Wrapper

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements-dev.txt
          
      - name: Run tests
        run: |
          cd backend
          pytest tests/ -v --cov=src --cov-report=xml
          
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
          
      - name: Deploy infrastructure
        run: |
          cd infrastructure/terraform
          terraform init
          terraform plan
          terraform apply -auto-approve
          
      - name: Build and deploy application
        run: |
          docker build -t amazon-q-wrapper .
          # Deploy to ECS/EKS/Lambda as needed
```

## 9. Monitoring & Observability

### 9.1 Structured Logging
```python
import structlog

logger = structlog.get_logger()

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start_time = time.time()
    
    logger.info(
        "request_started",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host
    )
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(
        "request_completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        process_time=process_time
    )
    
    return response
```

### 9.2 Health Checks
```python
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check AWS service connectivity
        s3_client = boto3.client('s3')
        s3_client.head_bucket(Bucket=settings.s3_bucket_name)
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "s3": "available",
                "bedrock": "available",
                "amazon_q": "available"
            }
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unhealthy")
```

## 10. Performance Optimization

### 10.1 Caching Strategy
```python
from functools import lru_cache
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

@lru_cache(maxsize=100)
def get_cached_query_result(query_hash: str) -> Optional[Dict]:
    """Get cached query result."""
    try:
        cached = redis_client.get(f"query:{query_hash}")
        return json.loads(cached) if cached else None
    except Exception:
        return None

async def cache_query_result(query_hash: str, result: Dict, ttl: int = 3600):
    """Cache query result with TTL."""
    try:
        redis_client.setex(
            f"query:{query_hash}", 
            ttl, 
            json.dumps(result)
        )
    except Exception as e:
        logger.warning("Failed to cache result", error=str(e))
```

### 10.2 Async Processing
```python
from celery import Celery

celery_app = Celery('amazon_q_wrapper')

@celery_app.task
def process_large_dataset_async(data_objects: List[Dict]) -> str:
    """Process large datasets asynchronously."""
    # Heavy processing logic here
    return "processing_complete"

@router.post("/process/async")
async def process_async(request: BedrockProcessingRequest):
    """Submit async processing job."""
    task = process_large_dataset_async.delay(request.data_objects)
    return {"task_id": task.id, "status": "submitted"}
```

This comprehensive guide provides a solid foundation for building your Amazon Q CLI wrapper with web UI. Remember to:

1. Start with a minimal viable product (MVP)
2. Implement security from day one
3. Use infrastructure as code for reproducible deployments
4. Monitor everything from the beginning
5. Follow AWS Well-Architected Framework principles
6. Implement proper error handling and logging
7. Use async patterns for better performance
8. Cache frequently accessed data
9. Implement proper testing at all levels
10. Document your APIs and deployment processes

The architecture is designed to be scalable, maintainable, and cost-effective while following both Python and AWS best practices. 