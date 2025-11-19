# GrandmaScrape Examples

Practical examples showing how to use GrandmaScrape in real-world scenarios.

## Prerequisites

```bash
# 1. Install GrandmaScrape
cd ..
poetry install

# 2. Start the API server (required for SDK examples)
poetry run scraper serve

# Or in Python:
python -m scraper.api.rest_server
```

---

## Basic Examples

### 01_quick_start.py

**The simplest way to use GrandmaScrape - 5 lines of code!**

```bash
python examples/01_quick_start.py
```

**What it does:**
- Auto-scrapes a website with zero configuration
- Uses AI to detect structure
- Exports to JSON
- Checks data quality

**Use when:**
- You want to quickly scrape a site
- You're new to GrandmaScrape
- You need a simple proof-of-concept

---

### 02_pandas_integration.py

**Integrate with Pandas for data analysis**

```bash
pip install pandas openpyxl
python examples/02_pandas_integration.py
```

**What it does:**
- Scrapes product data
- Converts to Pandas DataFrame
- Performs data analysis
- Exports to CSV, Excel, JSON

**Use when:**
- You need to analyze scraped data
- You're a data scientist/analyst
- You want statistical analysis

**Outputs:**
- `scraped_data.csv`
- `scraped_data.xlsx`
- `scraped_data.json`

---

### 03_async_concurrent.py

**Scrape multiple websites simultaneously**

```bash
python examples/03_async_concurrent.py
```

**What it does:**
- Scrapes 3 sites concurrently
- Uses async/await for performance
- Compares timing vs sequential

**Use when:**
- You need to scrape multiple sites
- Performance is critical
- You're familiar with async Python

**Performance:**
- Sequential: ~180s for 3 sites
- Concurrent: ~60s for 3 sites (3x faster!)

---

### 04_workflow_dag.py

**Complex multi-step scraping pipelines**

```bash
python examples/04_workflow_dag.py
```

**What it does:**
- Creates a DAG workflow
- Scrapes products, reviews, prices
- Runs steps in parallel where possible
- Generates competitive analysis report

**Use when:**
- You have complex, multi-step processes
- Steps have dependencies
- You need parallel execution

**Workflow:**
```
scrape_products
    ├── scrape_reviews (parallel)
    └── scrape_prices (parallel)
            └── analyze_data
                    └── export_report
```

---

### 05_data_quality_monitoring.py

**Monitor and ensure data quality**

```bash
python examples/05_data_quality_monitoring.py
```

**What it does:**
- Scrapes data
- Analyzes quality (completeness, validity, uniqueness)
- Detects anomalies
- Provides recommendations

**Use when:**
- Data quality is critical
- You need production monitoring
- You want anomaly detection

**Metrics:**
- Quality score (0-100%)
- Completeness, consistency, validity
- Anomaly detection with severity levels

---

## Integration Examples

### integrations/airflow_dag.py

**Apache Airflow integration for scheduled scraping**

```bash
# 1. Install Airflow
pip install apache-airflow

# 2. Copy to Airflow DAGs folder
cp examples/integrations/airflow_dag.py ~/airflow/dags/

# 3. Start Airflow
airflow standalone

# 4. Visit http://localhost:8080
```

**What it does:**
- Daily scheduled scraping (2 AM)
- Quality checks
- Anomaly detection
- Database export
- Email alerts on failure

**Use when:**
- You need scheduled scraping
- You use Airflow for orchestration
- You want production-grade pipelines

**DAG:**
```
scrape_website
    ├── check_data_quality
    └── detect_anomalies
            └── export_to_database
                    └── send_summary_report
```

---

## Running the Examples

### Option 1: Direct Execution

```bash
# Basic examples
python examples/01_quick_start.py
python examples/02_pandas_integration.py
python examples/03_async_concurrent.py
python examples/04_workflow_dag.py
python examples/05_data_quality_monitoring.py

# Airflow DAG
cp examples/integrations/airflow_dag.py ~/airflow/dags/
```

### Option 2: Using Poetry

```bash
# From project root
poetry run python examples/01_quick_start.py
```

### Option 3: Interactive (IPython/Jupyter)

```bash
ipython

# Then in IPython:
%run examples/01_quick_start.py
```

---

## Modifying Examples

All examples are designed to be easily modified for your use case.

### Change Target URL

```python
# In any example, change:
url="https://example.com"

# To your target:
url="https://your-site.com"
```

### Adjust Scraping Parameters

```python
job_id = client.auto_scrape(
    url="https://example.com",
    max_pages=50,        # Increase for more data
    export_format="csv", # json, excel, sqlite
    concurrent=True,     # Faster scraping
    wait=True           # Wait for completion
)
```

### Add Custom Analysis

```python
# After getting results
results = client.get_all_results(job_id)

# Your custom analysis
import pandas as pd
df = pd.DataFrame(results)

# Example: Price analysis
avg_price = df['price'].mean()
max_price = df['price'].max()
print(f"Average: ${avg_price:.2f}")
print(f"Maximum: ${max_price:.2f}")
```

---

## Common Patterns

### Pattern 1: Auto-Scrape + Export

```python
from scraper.sdk import GrandmaScrapeClient

with GrandmaScrapeClient() as client:
    job_id = client.auto_scrape(url, export_format="csv", wait=True)
    # Results auto-exported to CSV
```

### Pattern 2: Scrape + Quality Check

```python
with GrandmaScrapeClient() as client:
    job_id = client.auto_scrape(url, wait=True)

    quality = client.check_data_quality(job_id)
    if quality['quality_report']['quality_score'] < 0.8:
        print("WARNING: Low quality data!")
```

### Pattern 3: Incremental Scraping

```python
with GrandmaScrapeClient() as client:
    # Only scrapes changed pages (99% bandwidth savings!)
    job_id = client.run_job(job_id, incremental=True)
```

### Pattern 4: Async Batch Scraping

```python
from scraper.sdk import AsyncGrandmaScrapeClient

async def scrape_all(urls):
    async with AsyncGrandmaScrapeClient() as client:
        tasks = [client.auto_scrape(url) for url in urls]
        return await asyncio.gather(*tasks)
```

---

## Troubleshooting

### API Server Not Running

**Error:** `Connection refused`

**Solution:**
```bash
# Start the server
python -m scraper.api.rest_server

# Or using CLI
scraper serve
```

### Import Errors

**Error:** `ModuleNotFoundError`

**Solution:**
```bash
# Install dependencies
poetry install

# Or with pip
pip install -r requirements.txt
```

### Slow Scraping

**Solution:**
```python
# Enable concurrent scraping
client.auto_scrape(url, concurrent=True)

# Or use incremental mode
client.run_job(job_id, incremental=True)
```

### Quality Issues

**Solution:**
```python
# Check quality report
quality = client.check_data_quality(job_id)
print(quality['quality_report']['issues'])

# Re-scrape with different settings
```

---

## Next Steps

1. **Try the examples** - Start with `01_quick_start.py`
2. **Modify for your use case** - Change URLs and parameters
3. **Read the docs** - See `../README.md` and `../ULTRA_POWER.md`
4. **Deploy to production** - See `../DEPLOYMENT.md`

---

## Additional Resources

- **Main README**: `../README.md`
- **API Documentation**: http://localhost:8000/docs
- **Web Dashboard**: http://localhost:8000
- **Power Features**: `../ULTRA_POWER.md`
- **Deployment Guide**: `../DEPLOYMENT.md`
- **Layer C Guide**: `../LAYER_C.md`

---

## Contributing

Have a cool example to share? Create a pull request!

**Example template:**
```python
#!/usr/bin/env python3
"""
Example N: Your Example Title

Description of what it does and when to use it.
"""

from scraper.sdk import GrandmaScrapeClient

def main():
    # Your example code
    pass

if __name__ == "__main__":
    main()
```

---

Made with ❤️ and ethical scraping practices.
