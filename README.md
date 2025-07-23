# Amazon Q CLI Wrapper

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
