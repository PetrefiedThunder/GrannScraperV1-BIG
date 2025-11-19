# 🚀 Getting Started with GrandmaScrape

**Complete guide to getting up and running with GrandmaScrape in 5 minutes.**

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start (5 Minutes)](#quick-start-5-minutes)
3. [Choose Your Interface](#choose-your-interface)
4. [Common Use Cases](#common-use-cases)
5. [Next Steps](#next-steps)

---

## Installation

### Prerequisites

- Python 3.11 or higher
- 2GB+ RAM
- 1GB+ disk space

### Install with Poetry (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/yourorg/GrannScraperV1-BIG.git
cd GrannScraperV1-BIG

# 2. Install dependencies
poetry install

# 3. Install Playwright browsers (for JavaScript-heavy sites)
poetry run playwright install chromium

# 4. Verify installation
poetry run scraper --help
```

### Install with pip

```bash
# 1. Clone and navigate
git clone https://github.com/yourorg/GrannScraperV1-BIG.git
cd GrannScraperV1-BIG

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install
pip install -e .
playwright install chromium

# 4. Verify
scraper --help
```

---

## Quick Start (5 Minutes)

### Method 1: CLI (Grandma-Simple!)

**Just 3 questions, that's it!**

```bash
scraper easy https://example.com/products
```

You'll be asked:
1. What to name your scrape?
2. How many pages to scrape?
3. What format to export? (CSV, JSON, Excel)

Done! Results saved to `~/scraper_results/`

### Method 2: Web Dashboard

**Point-and-click interface - no coding required!**

```bash
# Start the server
scraper serve

# Open browser to:
http://localhost:8000
```

1. Enter URL in the form
2. Click "Start Auto-Scrape"
3. Watch real-time progress
4. Download results when complete

### Method 3: Python SDK

**For developers - clean, pythonic API**

```python
from scraper.sdk import GrandmaScrapeClient

# Auto-scrape with one method
with GrandmaScrapeClient() as client:
    job_id = client.auto_scrape(
        "https://example.com",
        max_pages=10,
        export_format="json",
        wait=True
    )

    results = client.get_all_results(job_id)
    print(f"Scraped {len(results)} items!")
```

### Method 4: Docker (Production)

**Containerized deployment**

```bash
# Quick start
docker-compose up -d

# Access dashboard
open http://localhost:8000
```

---

## Choose Your Interface

GrandmaScrape has **4 interfaces** for different users:

### 1. CLI - Command Line Interface

**Best for:** Quick scripts, automation, cron jobs

**Power Level:** ⚡⚡⚡⚡

**Commands:**
```bash
# Easy mode (3 questions)
scraper easy https://site.com

# Smart mode (AI auto-detection)
scraper smart https://site.com --concurrent

# Massive mode (max power)
scraper massive https://site.com --max-pages 1000

# Start API server
scraper serve
```

**Full Command List:**
```bash
scraper --help

Commands:
  serve     - Start API server + web dashboard
  easy      - 3 questions, that's it! (grandma-friendly)
  smart     - AI auto-detection (zero configuration)
  analyze   - Deep site analysis
  massive   - Max power mode
  wizard    - Interactive job builder
  run       - Execute saved job
  list      - Show all jobs
  validate  - Check config file
```

---

### 2. Web Dashboard - Browser Interface

**Best for:** Non-technical users, one-off scrapes, exploration

**Power Level:** ⚡⚡⚡

**Features:**
- Beautiful gradient UI
- Auto-scrape form
- Real-time job monitoring
- Results viewer
- No coding required

**Usage:**
```bash
scraper serve
# Visit http://localhost:8000
```

---

### 3. Python SDK - Programmatic API

**Best for:** Developers, integration, data pipelines

**Power Level:** ⚡⚡⚡⚡⚡

**Basic Usage:**
```python
from scraper.sdk import GrandmaScrapeClient

with GrandmaScrapeClient() as client:
    # Auto-scrape
    job_id = client.auto_scrape(url, concurrent=True, wait=True)

    # Get results
    results = client.get_all_results(job_id)

    # Check quality
    quality = client.check_data_quality(job_id)
```

**Advanced Usage:**
```python
# Async for performance
from scraper.sdk import AsyncGrandmaScrapeClient

async with AsyncGrandmaScrapeClient() as client:
    job_id = await client.auto_scrape(url)
    await client.wait_for_job(job_id)
    results = await client.get_all_results(job_id)
```

---

### 4. REST API - HTTP Interface

**Best for:** Remote access, microservices, integrations

**Power Level:** ⚡⚡⚡⚡⚡

**Start Server:**
```bash
scraper serve --port 8000
```

**Example Requests:**
```bash
# Auto-detect structure
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_pages": 1}'

# Create job
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d @job.json

# Run job
curl -X POST "http://localhost:8000/api/v1/jobs/JOB_ID/run?concurrent=true"

# Get results
curl http://localhost:8000/api/v1/jobs/JOB_ID/results
```

**API Documentation:** http://localhost:8000/docs

---

## Common Use Cases

### Use Case 1: E-Commerce Price Monitoring

**Goal:** Track competitor prices daily

**Solution:** CLI + Cron Job

```bash
# Create cron job (runs daily at 2 AM)
crontab -e

# Add line:
0 2 * * * cd /path/to/scraper && scraper smart https://competitor.com/products --export csv
```

---

### Use Case 2: Data Science Project

**Goal:** Collect training data for ML model

**Solution:** Python SDK + Pandas

```python
from scraper.sdk import GrandmaScrapeClient
import pandas as pd

with GrandmaScrapeClient() as client:
    # Scrape data
    job_id = client.auto_scrape(
        "https://dataset-source.com",
        max_pages=100,
        concurrent=True,
        wait=True
    )

    # Load into Pandas
    data = client.get_all_results(job_id)
    df = pd.DataFrame(data)

    # Train model
    from sklearn.model_selection import train_test_split
    # ... your ML code
```

---

### Use Case 3: News Aggregation

**Goal:** Daily digest from multiple sources

**Solution:** Workflow DAG + Email

See `examples/workflows/news_aggregation.yaml`

```bash
# Run workflow
python -m scraper.scheduler.workflow_dag execute examples/workflows/news_aggregation.yaml
```

---

### Use Case 4: Production Data Pipeline

**Goal:** Scheduled scraping with quality checks

**Solution:** Airflow + Docker

See `examples/integrations/airflow_dag.py`

```bash
# Deploy with Docker
docker-compose -f docker-compose.prod.yml up -d

# Add to Airflow
cp examples/integrations/airflow_dag.py ~/airflow/dags/
```

---

## Next Steps

### 1. Try the Examples

```bash
# Basic examples
python examples/01_quick_start.py
python examples/02_pandas_integration.py
python examples/03_async_concurrent.py

# See all examples
ls examples/
```

### 2. Learn Advanced Features

**Power Features:**
- AI Auto-Detection (zero-config scraping)
- 10x Concurrent Scraping
- ML Data Quality Analysis
- Smart Caching (99% bandwidth savings)
- Workflow DAGs
- Advanced Scheduling

**Read:** `ULTRA_POWER.md` for all advanced features

### 3. Deploy to Production

**Deployment options:**
- Docker (docker-compose)
- AWS (ECS, EC2)
- GCP (Cloud Run)
- Azure (Container Instances)

**Read:** `DEPLOYMENT.md` for complete deployment guide

### 4. Explore the SDK

**SDK Features:**
- Auto-scrape with zero config
- Async/await support
- Quality analysis
- Anomaly detection
- Workflow management

**Read:** `LAYER_C.md` for SDK documentation

---

## Helpful Commands

### Server Management

```bash
# Start server
scraper serve

# Start on custom port
scraper serve --port 3000

# Development mode (auto-reload)
scraper serve --reload
```

### Job Management

```bash
# List saved jobs
scraper list

# Run saved job
scraper run my_job

# Validate config
scraper validate config/job.yaml
```

### Docker Operations

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild
docker-compose build
```

---

## Troubleshooting

### Server Won't Start

**Problem:** Port already in use

**Solution:**
```bash
# Use different port
scraper serve --port 3000

# Or kill process on port 8000
lsof -ti:8000 | xargs kill
```

---

### Slow Scraping

**Problem:** Takes too long

**Solution:**
```bash
# Enable concurrent scraping (10x faster)
scraper smart URL --concurrent

# Or in SDK:
client.auto_scrape(url, concurrent=True)
```

---

### Import Errors

**Problem:** Module not found

**Solution:**
```bash
# Reinstall dependencies
poetry install

# Or with pip:
pip install -e .
```

---

### Quality Issues

**Problem:** Scraped data has errors

**Solution:**
```python
# Check quality report
quality = client.check_data_quality(job_id)
print(quality['quality_report']['issues'])

# Detect anomalies
anomalies = client.detect_anomalies(job_id)
print(anomalies)
```

---

## Learning Resources

### Documentation

- **README.md** - Project overview
- **GETTING_STARTED.md** - This document
- **ULTRA_POWER.md** - Advanced features
- **LAYER_C.md** - SDK documentation
- **DEPLOYMENT.md** - Production deployment
- **examples/README.md** - Example code

### API Documentation

```bash
# Start server
scraper serve

# Visit interactive docs
http://localhost:8000/docs
```

### Example Code

- **examples/** - 5+ complete examples
- **examples/integrations/** - Airflow, Pandas integrations
- **examples/workflows/** - YAML workflow configs

---

## Getting Help

1. **Check the docs** - See above
2. **Try examples** - Run example code
3. **Read API docs** - http://localhost:8000/docs
4. **Check issues** - GitHub issues page

---

## Tips for Success

### 1. Start Simple

```bash
# Begin with easy mode
scraper easy https://simple-site.com

# Then graduate to smart mode
scraper smart https://simple-site.com
```

### 2. Use Concurrent Scraping

```python
# 10x faster!
client.auto_scrape(url, concurrent=True)
```

### 3. Check Data Quality

```python
# Always verify quality
quality = client.check_data_quality(job_id)
if quality['quality_report']['quality_score'] < 0.8:
    print("Warning: Low quality data")
```

### 4. Enable Incremental Scraping

```python
# Only scrape what changed (99% bandwidth savings)
client.run_job(job_id, incremental=True)
```

### 5. Use Workflows for Complex Tasks

```bash
# Define once, run many times
python -m scraper.scheduler.workflow_dag execute workflow.yaml
```

---

## What's Next?

You're ready to start scraping! Here's a suggested learning path:

1. **✅ Install GrandmaScrape** (You did this!)
2. **⬜ Try `scraper easy`** - Get your first scrape
3. **⬜ Run `01_quick_start.py`** - See SDK in action
4. **⬜ Start web dashboard** - Try the UI
5. **⬜ Read `ULTRA_POWER.md`** - Learn advanced features
6. **⬜ Build your first project** - Apply to real use case
7. **⬜ Deploy to production** - See `DEPLOYMENT.md`

---

**Happy Scraping! 🧓✨**

*Made with ❤️ and ethical scraping practices*
