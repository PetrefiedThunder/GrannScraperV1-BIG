# 🧓 GrandmaScrape Intelligence Platform

**Enterprise-grade web scraping made grandma-simple.**

A next-generation, intelligent web scraping and data intelligence platform that rivals commercial products like Apify, ScrapingBee, and Octoparse — with an AI-first intelligence layer and a user experience so simple, your grandma could use it.

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

## 🎯 Features

### Layer A - Enterprise Single-Node (Current)

- ✅ **Static & JavaScript Scraping** - Handle both simple HTML and complex SPAs
- ✅ **Smart Pagination** - Next button, URL patterns, infinite scroll
- ✅ **Proxy & User-Agent Rotation** - Built-in anti-blocking
- ✅ **Multiple Export Formats** - CSV, JSON, Excel, SQLite, and more
- ✅ **AI-Powered Extraction** - Claude-powered semantic field detection
- ✅ **Grandma-Friendly CLI** - Three difficulty modes (easy/massive/wizard)
- ✅ **Rate Limiting & Politeness** - Respect robots.txt and site resources
- ✅ **Data Transformation** - Cleaning, type inference, deduplication

### Layer B - Distributed Intelligence (Roadmap)

- 🔄 Distributed workers & orchestration
- 🔄 Browser cluster management
- 🔄 Advanced ML extraction
- 🔄 Workflow DAGs & scheduling
- 🔄 Multi-tenancy & RBAC
- 🔄 Real-time monitoring & alerts

### Layer C - UX & SDK Surface (Complete!)

- ✅ **Python SDK** - Clean, pythonic API client
- ✅ **Web Dashboard** - Modern HTML/JS interface
- ✅ **Docker Deployment** - Production-ready containers
- ✅ **Comprehensive Tests** - pytest suite for all components
- ✅ **Production Guide** - Complete deployment documentation

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

- [User Guide](docs/USER_GUIDE.md) - Complete usage documentation
- [Developer Guide](docs/DEV_GUIDE.md) - Contributing & architecture
- [API Reference](docs/API_REFERENCE.md) - REST & GraphQL APIs
- [How to Add New Sites](docs/HOW_TO_ADD_NEW_SITES.md) - Custom strategies

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

Contributions welcome! Please read our [Developer Guide](docs/DEV_GUIDE.md) first.

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
