# Mercator Reporting

Intelligent reporting tool for Mercator CMDB. A modern recreation of the Cognos Impromptu / Isiparc approach for IT asset management reporting.

## Overview

Mercator Reporting is a full-stack application providing:
- **Backend**: Python FastAPI service connecting to Mercator CMDB
- **Frontend**: React SPA with Tailwind CSS for report exploration and visualization
- **Export Capabilities**: Excel, Word, PDF, and HTML report generation
- **Docker Support**: Containerized deployment with docker-compose

## Architecture

```
mercator-reporting/
├── src/                          # Python Backend (FastAPI)
│   ├── main.py                   # FastAPI application entry point
│   ├── config.py                 # Environment configuration (Pydantic Settings)
│   ├── api/
│   │   └── routes/
│   │       ├── mercator.py       # Mercator CMDB health & endpoint routes
│   │       └── reports.py        # Report generation API routes
│   ├── core/
│   │   ├── mercator_client.py    # HTTP client for Mercator CMDB API
│   │   └── dependencies.py       # FastAPI dependency injection
│   ├── models/
│   │   └── report.py             # Pydantic models for reports
│   ├── reporting/
│   │   ├── engine.py             # Report generation engine
│   │   └── filters.py            # Query filtering logic
│   └── services/
│       └── export.py             # Export services (Excel, PDF, etc.)
├── frontend/                     # React Frontend
│   ├── src/
│   │   ├── App.jsx               # Main React application
│   │   ├── main.jsx              # React entry point
│   │   ├── components/
│   │   │   ├── Navbar.jsx        # Navigation component
│   │   │   ├── ReportTable.jsx   # Report data table
│   │   │   └── TemplateCard.jsx  # Report template cards
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx     # Main dashboard
│   │   │   └── ReportView.jsx    # Report detail view
│   │   └── api/
│   │       └── reports.js        # API client for reports
│   ├── Dockerfile.frontend       # Multi-stage Docker build
│   ├── nginx.conf                # Nginx config with API proxy
│   ├── package.json              # Node.js dependencies
│   ├── vite.config.js            # Vite build configuration
│   └── tailwind.config.js        # Tailwind CSS configuration
├── tests/                        # Python test suite
├── docs/                         # Documentation
├── Dockerfile                    # Python backend Dockerfile
├── docker-compose.yml            # Multi-service orchestration
├── pyproject.toml               # Python dependencies & tool config
└── bootstrap.sh                 # Environment setup script
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (optional)

### Local Development

1. **Install Python dependencies** (using [uv](https://github.com/astral-sh/uv)):
   ```bash
   uv pip install -e ".[dev,lint]"
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your Mercator CMDB credentials
   ```

3. **Run backend**:
   ```bash
   uvicorn src.main:app --reload
   ```

4. **Run frontend** (in separate terminal):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Docker Deployment

Run the entire stack with docker-compose:

```bash
docker-compose up --build
```

Services:
- **Backend**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

## Configuration

Environment variables (see `src/config.py`):

| Variable | Description | Default |
|----------|-------------|---------|
| `MERCATOR_BASE_URL` | Mercator CMDB API URL | `http://localhost:8080` |
| `MERCATOR_LOGIN` | Mercator username | `admin@admin.com` |
| `MERCATOR_PASSWORD` | Mercator password | `password` |
| `SECRET_KEY` | Application secret key | `change-me` |
| `MAX_EXPORT_ROWS` | Maximum rows per export | `10000` |
| `DEBUG` | Debug mode | `false` |

## Features

- **Mercator CMDB Integration**: Connect to existing Mercator CMDB instances
- **Dynamic Reporting**: Query and filter CMDB data with custom reports
- **Export Formats**: Excel (.xlsx), Word (.docx), PDF, HTML
- **Modern UI**: React SPA with responsive Tailwind CSS design
- **API Documentation**: Auto-generated OpenAPI/Swagger docs
- **Hot Reload**: Development mode with automatic code reloading
- **Health Checks**: Docker health monitoring for all services

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Service health check |
| `GET /api/mercator/health` | Mercator CMDB connectivity check |
| `GET /api/mercator/endpoints` | Available Mercator API endpoints |
| `GET /api/reports/templates` | List report templates |
| `POST /api/reports/generate` | Generate custom report |
| `POST /api/reports/export` | Export report to file |

## Tech Stack

**Backend:**
- FastAPI + Uvicorn
- Pydantic + Pydantic Settings
- HTTPX (async HTTP client)
- Pandas / NumPy (data processing)
- ReportLab / OpenPyXL / python-docx (exports)

**Frontend:**
- React 18
- Vite (build tool)
- React Router
- Tailwind CSS
- Nginx (production server)

**DevOps:**
- Docker + Docker Compose
- uv (Python package manager)
- pytest (testing)
- Ruff + Black (linting)

## Development

### Running Tests

```bash
pytest
```

### Code Quality

```bash
ruff check src/
black src/
mypy src/
```

### Project Structure Notes

- Backend follows FastAPI best practices with dependency injection
- Frontend uses Vite for fast development and optimized builds
- Nginx proxies `/api/*` requests to the backend service
- Docker volumes enable hot-reload during development

## License

Proprietary - Équipe Mercator Reporting
