# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

GrandmaScrape is an enterprise-grade web scraping and data intelligence platform built with Python. It provides multiple interfaces (CLI, Web Dashboard, REST API, Python SDK) for scraping static and JavaScript-heavy websites with intelligent extraction, pagination, rate limiting, and extensive export capabilities.

**Technology Stack:**
- Python 3.11+ with Poetry for dependency management
- Async/await patterns throughout (asyncio)
- FastAPI for REST API
- Playwright for browser automation
- BeautifulSoup4 for HTML parsing
- Pydantic v2 for data models and validation
- Click + Rich for CLI

## Essential Commands

### Development Setup
```bash
# Install dependencies
poetry install

# Install Playwright browsers (required for JavaScript sites)
poetry run playwright install chromium

# Verify installation
poetry run scraper --help
```

### Testing
```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=scraper --cov-report=html

# Run specific test file
poetry run pytest tests/test_scraper.py

# Run specific test
poetry run pytest tests/test_models.py::test_job_validation -v
```

### Code Quality
```bash
# Run ruff linter (checks code style)
poetry run ruff check .

# Run mypy type checker
poetry run mypy scraper

# Auto-fix linting issues
poetry run ruff check --fix .
```

### Running the Application

**CLI Commands:**
```bash
# Easy mode (3 questions, grandma-friendly)
poetry run scraper easy https://example.com

# Massive mode (max power with smart defaults)
poetry run scraper massive https://example.com --max-pages 100 --export csv,json

# Interactive wizard
poetry run scraper wizard

# Run saved job
poetry run scraper run my_job

# List all saved jobs
poetry run scraper list
```

**API Server:**
```bash
# Start API server with web dashboard
poetry run scraper serve

# Development mode with auto-reload
poetry run scraper serve --reload

# Custom port
poetry run scraper serve --port 3000

# Direct Python invocation
python -m scraper.api.rest_server
```

**Docker:**
```bash
# Build and start services
docker-compose build
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Production deployment
docker-compose -f docker-compose.prod.yml up -d
```

## Architecture & Key Concepts

### Core Data Flow
1. **Job Configuration** (`ScrapeJob`) → defines what/how to scrape
2. **Engine** (`ScraperEngine`) → orchestrates the scraping process
3. **Fetchers** → retrieve HTML (static via httpx or browser via Playwright)
4. **Extractors** → parse and extract data from HTML
5. **Transforms** → clean, deduplicate, and type-cast data
6. **Export Manager** → save results in various formats

### Module Organization

**Core Modules:**
- `scraper/core/` - Scraping engine, fetchers (static/browser), rate limiting
- `scraper/config/` - Pydantic models for jobs, fields, pagination, etc.
- `scraper/extractors/` - Data extraction (CSS selectors, tables, media, LLM)
- `scraper/transforms/` - Data transformation (cleaning, deduplication, type inference)
- `scraper/export/` - Export formats (CSV, JSON, Excel, Parquet, etc.) and database connectors

**Interfaces:**
- `scraper/cli/` - Command-line interface with Click
- `scraper/api/` - FastAPI REST API server
- `scraper/sdk/` - Python SDK client for API
- `scraper/web/` - Web dashboard (HTML/JS/CSS)

**Advanced Features:**
- `scraper/scheduler/` - Job scheduling, cron, workflow DAGs
- `scraper/ml/` - Data intelligence, anomaly detection, quality analysis
- `scraper/monitor/` - Alerting (Slack, Discord, Email, SMS, PagerDuty)
- `scraper/security/` - Authentication, RBAC, compliance
- `scraper/storage/` - Smart caching, incremental scraping, metadata store

### Key Design Patterns

**Async Throughout:**
All I/O operations use async/await. The engines, fetchers, extractors, and export managers are async.

**Fetcher Strategy Pattern:**
Jobs determine fetcher type:
- `StaticFetcher` - fast, uses httpx for static HTML
- `BrowserFetcher` - uses Playwright for JavaScript-heavy sites
- Engine selects fetcher based on `job.browser.enabled` or auto-detection

**Pagination Modes:**
- `none` - single page
- `next_button` - clicks next button (CSS selector)
- `url_pattern` - generates URLs with {page} placeholder
- `infinite_scroll` - scrolls down to load content

**Field Extraction:**
- CSS selectors for structured extraction
- LLM-powered semantic extraction (Claude)
- Table extraction for tabular data
- Media extraction for images/videos

**Export Pipeline:**
Results → `ExportManager` → format-specific exporters → disk/database/cloud

### Important Conventions

**Async Context Managers:**
Fetchers use async context managers (`async with fetcher:`). Always ensure proper cleanup.

**Rate Limiting:**
`RateLimiter` enforces delays between requests. Always use `await rate_limiter.acquire(domain)` and `release(domain)`.

**Session Management:**
`SessionManager` tracks visited URLs, failed URLs, and prevents duplicate scraping.

**Job IDs:**
Jobs use UUID-based IDs by default. In API endpoints, job_id must be validated against regex `^[a-zA-Z0-9_-]+$` to prevent injection.

**Error Handling:**
Engines collect errors in `result.errors` list but continue scraping. Final status is `success`, `partial`, or `failed`.

## Working with This Codebase

### Adding a New Export Format
1. Create exporter in `scraper/export/` (e.g. `my_format_exporter.py`)
2. Implement async `export(data: List[Dict], output_path: Path)` method
3. Register in `ExportManager.get_exporter()` switch statement
4. Add format to `ExportFormat` enum if needed
5. Update documentation and tests

### Adding a New CLI Command
1. Add command function in `scraper/cli/main.py` or `scraper/cli/smart_commands.py`
2. Use `@cli.command()` decorator
3. Follow existing patterns (use `console.print()` for output, async with `asyncio.run()`)
4. Register command with `cli.add_command()` if in separate file

### Adding a New API Endpoint
1. Add endpoint function in `scraper/api/rest_server.py`
2. Use appropriate HTTP method decorator (`@app.get()`, `@app.post()`, etc.)
3. Define request/response models with Pydantic
4. Add input validation (especially for IDs to prevent injection)
5. Handle errors with `HTTPException`

### Modifying Data Models
1. Models are in `scraper/config/models.py`
2. Use Pydantic v2 syntax (`BaseModel`, `Field`, validators)
3. Add field validators with `@field_validator` decorator
4. Add model validators with `@model_validator` decorator
5. Update tests to cover new validation logic

### Testing Strategy
- Unit tests in `tests/` mirror `scraper/` structure
- Use `pytest-asyncio` for async tests (`async def test_...`)
- Use `pytest-mock` for mocking external dependencies
- Fixtures in `tests/conftest.py` provide reusable test data
- Aim for >80% coverage on new code

## Configuration Files

**Job Configs:**
Saved in `~/.grandma-scraper/jobs/` as YAML files with schema:
```yaml
name: "My Scraper"
start_url: "https://example.com"
browser:
  enabled: true
pagination:
  mode: "url_pattern"
  max_pages: 10
fields:
  title:
    selector: "h1"
    type: "string"
export:
  formats: ["csv", "json"]
```

**Environment Variables:**
See `DEPLOYMENT.md` for production configuration. Key variables:
- `API_HOST`, `API_PORT` - server binding
- `DATABASE_URL`, `REDIS_URL` - storage backends
- `SCRAPER_MAX_CONCURRENT` - concurrency limit
- `LOG_LEVEL` - logging verbosity

## Common Issues

**Playwright Not Installed:**
If browser tests fail, run `poetry run playwright install chromium`

**Rate Limiting Errors:**
Jobs respect rate limits by default. Adjust `rate_limit.min_delay` and `max_delay` in job config.

**Type Checking Failures:**
This codebase uses strict type checking. All functions need type hints (`-> ReturnType`). Use `Optional[T]` for nullable values.

**Import Errors:**
Use absolute imports: `from scraper.core.engine import ScraperEngine`, not relative imports.

## Documentation References

- `README.md` - project overview and quick start
- `GETTING_STARTED.md` - detailed installation and usage guide
- `CONTRIBUTING.md` - contribution guidelines and code standards
- `DEPLOYMENT.md` - production deployment (Docker, AWS, GCP, Azure)
- `LAYER_C.md` - SDK, API, and UX layer documentation
- `ULTRA_POWER.md` - advanced Layer B features (ML, workflows, monitoring)
- `COMPETITIVE_ANALYSIS.md` - comparison with commercial services
