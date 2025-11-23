# 🧓 GrandmaScrape Intelligence Platform

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Checked](https://img.shields.io/badge/type%20checked-mypy-blue.svg)](http://mypy-lang.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Status](https://img.shields.io/badge/status-active%20development-orange.svg)]()

**An open-source scraping toolkit with a friendly CLI, FastAPI service, and Python SDK.**

The project currently ships a single-node scraping engine (static + Playwright), a set of beginner-friendly CLI modes, an HTTP API with an optional dashboard, and a Python SDK for programmatic access. Distributed orchestration and other Layer B features live on the roadmap while the core experience is hardened.

---

## ⚡ Quick Start

### Installation

```bash
# Install dependencies
poetry install

# Install Playwright browsers
poetry run playwright install chromium
```

### Grandma Mode (Easiest)

```bash
# Just paste a URL and answer 3 simple questions
scraper easy https://example.com
```

### Massive Mode (Max Power, Single Command)

```bash
# Intelligent auto-detection with smart defaults
scraper massive https://example.com --max-pages 100 --export csv,json
```

### Wizard Mode (Interactive Setup)

```bash
# Step-by-step guidance to create a custom job
scraper wizard
```

---

## 🎯 Current Capabilities

### Core scraping engine (Layer A)

- ✅ **Static + JavaScript rendering** via `requests`/BeautifulSoup and optional Playwright
- ✅ **Smart pagination** with none/url-pattern/next-button/infinite-scroll modes
- ✅ **Session controls** including robots.txt checks, rate limiting, and basic proxy/UA rotation
- ✅ **Extraction options** for CSS selectors, tables, media, and optional LLM-backed semantic fields
- ✅ **Exports** to CSV, JSON/NDJSON, Excel, SQLite, Parquet, Feather, and more
- ✅ **Data post-processing** (type inference, cleaning, deduplication)

### Interfaces & developer surface

- ✅ **CLI** modes: `easy`, `massive`, `wizard`, `smart`, `analyze`, `run`, `list`, `validate`, `serve`
- ✅ **FastAPI service** with job management, smart cache/incremental scraping, and OpenAPI docs at `/docs`
- ✅ **Python SDK** (`GrandmaScrapeClient`) for interacting with the API
- ✅ **Examples & configs** to bootstrap common workflows

### Roadmap highlights (Layer B and beyond)

- 🔄 Distributed execution, browser pooling, and workflow orchestration
- 🔄 RBAC/multi-tenant hardening
- 🔄 Expanded monitoring/alerting surface
- 🔄 More pluggable ML extraction models

[See detailed comparison →](COMPETITIVE_ANALYSIS.md)

---

## 📖 Usage Examples

### Example 1: Quick CSV Export

```bash
scraper easy https://news.ycombinator.com
# Answers prompts, exports to ~/scraper_results/hackernews_2025-11-18.csv
```

### Example 2: Custom Job Config

```yaml
# config/my_job.yaml
name: "Product Scraper"
start_url: "https://example.com/products"
use_browser: true
pagination_mode: "next_button"
next_button_selector: ".next-page"
max_pages: 50

fields:
  title:
    selector: "h1.product-title"
    type: "string"
  price:
    selector: ".price"
    type: "currency"
  rating:
    selector: ".rating"
    type: "float"

export_formats: ["csv", "json", "excel"]
```

```bash
scraper run config/my_job.yaml
```

### Example 3: Programmatic Usage

```python
from scraper.core.engine import ScraperEngine
from scraper.config.models import ScrapeJob

job = ScrapeJob(
    name="my_scrape",
    start_url="https://example.com",
    item_selector=".product",
    fields={
        "title": {"selector": "h2", "type": "string"},
        "price": {"selector": ".price", "type": "currency"}
    },
    export_formats=["csv"]
)

engine = ScraperEngine()
results = await engine.run_job(job)
```

### Example 4: Python SDK (Layer C)

```python
from scraper.sdk import GrandmaScrapeClient

# Initialize client
with GrandmaScrapeClient("http://localhost:8000") as client:
    # Auto-scrape with zero config
    job_id = client.auto_scrape(
        "https://example.com",
        max_pages=10,
        export_format="csv",
        concurrent=True,
        wait=True  # Wait for completion
    )

    # Get results
    results = client.get_all_results(job_id)
    print(f"Scraped {len(results)} items!")

    # Check data quality
    quality = client.check_data_quality(job_id)
    print(f"Quality score: {quality['quality_report']['quality_score']:.2f}")
```

### Example 5: Web Dashboard (Layer C)

```bash
# Start API server with dashboard
python -m scraper.api.rest_server

# Open browser to http://localhost:8000
# 1. Enter URL in auto-scrape form
# 2. Click "Start Auto-Scrape"
# 3. View real-time progress
# 4. Download results when complete
```

### Example 6: Docker Deployment (Layer C)

```bash
# Quick start
docker-compose up -d

# Production deployment
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Access dashboard at http://localhost:8000
```

---

## 🏗️ Architecture

```
scraper/
├── core/          # Engine, fetchers, rate limiting
├── strategies/    # Site-specific scraping strategies
├── extractors/    # Data extraction (selectors, AI, media)
├── transforms/    # ETL, cleaning, type inference
├── export/        # 20+ export formats
├── storage/       # Cache, metadata, job store
├── scheduler/     # Cron, workflows, DAGs
├── monitor/       # Metrics, logging, alerts
├── security/      # Auth, RBAC, compliance
├── ml/            # AI models, anomaly detection
├── api/           # REST & GraphQL APIs
├── cli/           # Command-line interface
└── config/        # Job models & examples
```

---

## ⚖️ Legal & Ethical Use

**⚠️ IMPORTANT DISCLAIMER**

This platform is a powerful tool. **You are responsible** for using it in compliance with:

- Each website's Terms of Service
- robots.txt directives (respected by default)
- All applicable laws (CFAA, GDPR, etc.)

**Default behavior:**
- ✅ Respects robots.txt
- ✅ Enforces rate limiting
- ✅ Uses polite scraping patterns

**This tool should NOT be used to:**
- ❌ Bypass authentication or paywalls
- ❌ Circumvent technical access controls
- ❌ Scrape sites that explicitly prohibit it
- ❌ Violate privacy or data protection laws

---

## 📚 Documentation

**Getting Started:**
- [Getting Started Guide](GETTING_STARTED.md) - 5-minute quick start for beginners
- [Platform Summary](PLATFORM_SUMMARY.md) - Complete feature overview
- [Success Summary](SUCCESS_SUMMARY.md) - Achievement statistics & ROI

**Advanced Features:**
- [Ultra Power Features](ULTRA_POWER.md) - Layer B intelligence features
- [Layer C Documentation](LAYER_C.md) - SDK, API, and UX guide
- [Deployment Guide](DEPLOYMENT.md) - Production deployment (400+ lines)

**Competitive Analysis:**
- [Competitive Analysis](COMPETITIVE_ANALYSIS.md) - vs. commercial services (Apify, Bright Data, etc.)

**Contributing:**
- [Contributing Guide](CONTRIBUTING.md) - How to contribute
- [Security Policy](SECURITY.md) - Security and responsible disclosure
- [Changelog](CHANGELOG.md) - Version history and updates

**API Documentation:**
- Auto-generated OpenAPI docs at `/docs` when running `scraper serve`

---

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=scraper --cov-report=html

# Run specific test suite
poetry run pytest tests/core/
```

---

## 🤝 Contributing

Contributions are welcome and appreciated!

Please read our [Contributing Guide](CONTRIBUTING.md) to get started.

**Ways to contribute:**
- 🐛 Report bugs
- 💡 Suggest features
- 📚 Improve documentation
- 🧪 Add tests
- ✨ Submit pull requests

**Good first issues:** Look for issues labeled `good first issue` in the GitHub repository.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

Built with modern Python async patterns, powered by:
- Playwright for browser automation
- FastAPI for lightning-fast APIs
- Claude AI for intelligent extraction
- Beautiful Soup for HTML parsing

**Made with ❤️ for grandmas and engineers alike.**
