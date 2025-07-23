#!/usr/bin/env python3
"""
Project Setup Script for Amazon Q CLI Wrapper

This script sets up the initial project structure following the guidelines.
Run: python setup_project.py
"""

import os
import sys
from pathlib import Path


def create_directory_structure():
    """Create the recommended directory structure."""
    
    directories = [
        # Backend structure
        "backend/src/api/routes",
        "backend/src/core",
        "backend/src/services",
        "backend/src/models",
        "backend/src/utils",
        "backend/tests/unit",
        "backend/tests/integration",
        
        # Frontend structure
        "frontend/src/components",
        "frontend/src/pages",
        "frontend/src/services",
        "frontend/src/utils",
        "frontend/public",
        
        # Infrastructure
        "infrastructure/terraform/modules",
        "infrastructure/terraform/environments",
        "infrastructure/cloudformation",
        
        # Scripts
        "scripts",
        
        # Documentation
        "docs/api",
        "docs/deployment",
        
        # CI/CD
        ".github/workflows",
    ]
    
    print("🏗️  Creating directory structure...")
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"   ✓ Created: {directory}")


def create_init_files():
    """Create __init__.py files for Python packages."""
    
    init_files = [
        "backend/src/__init__.py",
        "backend/src/api/__init__.py",
        "backend/src/api/routes/__init__.py",
        "backend/src/core/__init__.py",
        "backend/src/services/__init__.py",
        "backend/src/models/__init__.py",
        "backend/src/utils/__init__.py",
        "backend/tests/__init__.py",
    ]
    
    print("\n📝 Creating Python package files...")
    for init_file in init_files:
        Path(init_file).touch()
        print(f"   ✓ Created: {init_file}")


def create_requirements_files():
    """Create requirements files."""
    
    # Production requirements
    requirements_txt = """fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pydantic-settings==2.1.0
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
redis==5.0.1
celery==5.3.4
"""

    # Development requirements
    requirements_dev_txt = """-r requirements.txt
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
pytest-mock==3.12.0
black==23.11.0
isort==5.12.0
flake8==6.1.0
mypy==1.7.1
pre-commit==3.6.0
httpx==0.25.2
factory-boy==3.3.0
"""

    print("\n📦 Creating requirements files...")
    
    with open("backend/requirements.txt", "w") as f:
        f.write(requirements_txt)
    print("   ✓ Created: backend/requirements.txt")
    
    with open("backend/requirements-dev.txt", "w") as f:
        f.write(requirements_dev_txt)
    print("   ✓ Created: backend/requirements-dev.txt")


def create_docker_files():
    """Create Docker configuration files."""
    
    # Backend Dockerfile
    dockerfile_backend = """FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY main.py .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
USER app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

    # Frontend Dockerfile
    dockerfile_frontend = """FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Use nginx to serve the built app
FROM nginx:alpine
COPY --from=0 /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""

    # Docker Compose
    docker_compose = """version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./app.db
      - REDIS_HOST=redis
    depends_on:
      - redis
    volumes:
      - ./backend:/app
      - /app/__pycache__
    
  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
    
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
"""

    print("\n🐳 Creating Docker files...")
    
    with open("backend/Dockerfile", "w") as f:
        f.write(dockerfile_backend)
    print("   ✓ Created: backend/Dockerfile")
    
    with open("frontend/Dockerfile", "w") as f:
        f.write(dockerfile_frontend)
    print("   ✓ Created: frontend/Dockerfile")
    
    with open("docker-compose.yml", "w") as f:
        f.write(docker_compose)
    print("   ✓ Created: docker-compose.yml")


def create_gitignore():
    """Create .gitignore file."""
    
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# Environment variables
.env
.env.local
.env.production

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Database
*.db
*.sqlite3

# Terraform
*.tfstate
*.tfstate.*
.terraform/
.terraform.lock.hcl

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Build outputs
dist/
build/

# Coverage
.coverage
htmlcov/
.pytest_cache/

# AWS
.aws/

# Temporary files
*.tmp
*.temp
"""

    print("\n🙈 Creating .gitignore...")
    with open(".gitignore", "w") as f:
        f.write(gitignore_content)
    print("   ✓ Created: .gitignore")


def create_readme():
    """Create README file."""
    
    readme_content = """# Amazon Q CLI Wrapper

A web-based interface that wraps Amazon Q CLI to provide cost optimization insights, Bedrock agent processing, and dashboard generation with S3 static hosting.

## Features

- 🤖 Amazon Q integration for cost optimization queries
- 🧠 Bedrock agent processing for data analysis
- 📊 Interactive dashboard generation with Plotly
- ☁️ S3 static hosting for dashboard deployment
- 🔗 Embeddable widgets for integration

## Quick Start

1. **Clone and setup**:
   ```bash
   git clone <your-repo>
   cd amazon-q-wrapper
   python setup_project.py  # If not already run
   ```

2. **Configure environment**:
   ```bash
   cp env.template .env
   # Edit .env with your AWS credentials and configurations
   ```

3. **Run with Docker**:
   ```bash
   docker-compose up
   ```

4. **Or run locally**:
   ```bash
   # Backend
   cd backend
   pip install -r requirements-dev.txt
   uvicorn main:app --reload

   # Frontend (in another terminal)
   cd frontend
   npm install
   npm run dev
   ```

## Project Structure

```
amazon-q-wrapper/
├── backend/          # FastAPI backend
├── frontend/         # React/Vue frontend
├── infrastructure/   # Terraform/CloudFormation
├── scripts/         # Deployment scripts
└── docs/           # Documentation
```

## API Endpoints

- `POST /api/v1/query/cost-optimization` - Query Amazon Q
- `POST /api/v1/process/bedrock` - Process data with Bedrock
- `POST /api/v1/dashboard/generate` - Generate and deploy dashboard

## Configuration

See `env.template` for all available configuration options.

## Deployment

See `docs/deployment/` for detailed deployment instructions.

## Contributing

1. Follow the guidelines in `PROJECT_GUIDELINES.md`
2. Run tests: `pytest`
3. Format code: `black . && isort .`
4. Type check: `mypy src/`

## License

MIT License
"""

    print("\n📖 Creating README...")
    with open("README.md", "w") as f:
        f.write(readme_content)
    print("   ✓ Created: README.md")


def create_basic_backend_files():
    """Create basic backend application files."""
    
    # Main FastAPI app
    main_py = """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from src.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting Amazon Q Wrapper API")
    yield
    # Shutdown
    print("Shutting down Amazon Q Wrapper API")


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


@app.get("/")
async def root():
    return {"message": "Amazon Q Wrapper API", "version": settings.api_version}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

    # Configuration
    config_py = """from pydantic_settings import BaseSettings
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
    amazon_q_application_id: str = ""
    amazon_q_user_id: str = ""
    
    # Bedrock Configuration
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    bedrock_agent_id: str = ""
    bedrock_agent_alias_id: str = "TSTALIASID"
    
    # S3 Configuration
    s3_bucket_name: str = ""
    s3_region: str = "us-east-1"
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
"""

    print("\n🐍 Creating basic backend files...")
    
    with open("backend/main.py", "w") as f:
        f.write(main_py)
    print("   ✓ Created: backend/main.py")
    
    with open("backend/src/core/config.py", "w") as f:
        f.write(config_py)
    print("   ✓ Created: backend/src/core/config.py")


def create_basic_frontend_files():
    """Create basic frontend files."""
    
    # package.json
    package_json = """{
  "name": "amazon-q-wrapper-frontend",
  "version": "1.0.0",
  "description": "Frontend for Amazon Q CLI Wrapper",
  "main": "index.js",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint src --ext .js,.jsx,.ts,.tsx",
    "format": "prettier --write src/"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0",
    "react-router-dom": "^6.8.0",
    "@mui/material": "^5.15.0",
    "@emotion/react": "^11.11.0",
    "@emotion/styled": "^11.11.0",
    "plotly.js": "^2.27.0",
    "react-plotly.js": "^2.6.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0",
    "eslint": "^8.56.0",
    "prettier": "^3.1.0",
    "typescript": "^5.3.0"
  }
}
"""

    # index.html
    index_html = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Amazon Q Wrapper</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""

    print("\n⚛️  Creating basic frontend files...")
    
    with open("frontend/package.json", "w") as f:
        f.write(package_json)
    print("   ✓ Created: frontend/package.json")
    
    with open("frontend/public/index.html", "w") as f:
        f.write(index_html)
    print("   ✓ Created: frontend/public/index.html")


def main():
    """Main setup function."""
    print("🚀 Setting up Amazon Q CLI Wrapper project...")
    print("=" * 50)
    
    try:
        create_directory_structure()
        create_init_files()
        create_requirements_files()
        create_docker_files()
        create_gitignore()
        create_readme()
        create_basic_backend_files()
        create_basic_frontend_files()
        
        print("\n" + "=" * 50)
        print("✅ Project setup complete!")
        print("\n📋 Next steps:")
        print("1. Copy env.template to .env and configure your AWS credentials")
        print("2. Review PROJECT_GUIDELINES.md for detailed implementation guidance")
        print("3. Install dependencies: cd backend && pip install -r requirements-dev.txt")
        print("4. Start development: docker-compose up")
        print("\n🎉 Happy coding!")
        
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 