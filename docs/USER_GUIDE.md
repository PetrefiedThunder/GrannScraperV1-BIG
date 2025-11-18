# GrandmaScrape User Guide

Complete guide to using the GrandmaScrape Intelligence Platform.

---

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Usage Modes](#usage-modes)
4. [Configuration](#configuration)
5. [Advanced Features](#advanced-features)
6. [Troubleshooting](#troubleshooting)

---

## Installation

### Prerequisites

- Python 3.11 or higher
- pip or poetry package manager

### Step 1: Install Dependencies

Using Poetry (recommended):

```bash
cd GrannScraperV1-BIG
poetry install
```

Using pip:

```bash
pip install -r requirements.txt  # (generate from pyproject.toml)
```

### Step 2: Install Playwright Browsers

```bash
poetry run playwright install chromium
# Or: playwright install chromium
```

### Step 3: Verify Installation

```bash
poetry run scraper --help
```

You should see the help menu!

---

## Quick Start

### Easiest Way: Easy Mode

```bash
scraper easy https://example.com
```

Answer 3 simple questions:
1. What are you trying to get?
2. How many pages?
3. What filename?

**Done!** Your CSV file will be in `~/scraper_results/`

### Example

```bash
$ scraper easy https://news.ycombinator.com

Question 1: What are you trying to get from this page?
  (Examples: titles, prices, names, articles, products)
  Your answer: news articles

Question 2: About how many pages should I look through?
  (Just give me a number, or say 'just one')
  Your answer: 5

Question 3: What should I name your file?
  (I'll add .csv automatically)
  Your answer: hackernews

Great! I'm ready to scrape!
  • Getting: news articles
  • Pages: 5
  • Saving as: hackernews.csv

Should I start? [Y/n]: y
```

---

## Usage Modes

### 1. Easy Mode (Grandma-Friendly)

**Best for:** Non-technical users, one-time scrapes

```bash
scraper easy <URL>
```

Features:
- ✅ Only 3 questions
- ✅ Auto-detection
- ✅ CSV output
- ✅ Plain English feedback

### 2. Massive Mode (Max Power)

**Best for:** Power users who want quick results

```bash
scraper massive <URL> [OPTIONS]
```

Options:
- `--max-pages N` - Scrape up to N pages (default: 10)
- `--use-browser` - Use browser for JavaScript sites
- `--export FORMAT` - Export formats: csv,json,excel (comma-separated)
- `--output-dir PATH` - Custom output directory

Example:

```bash
scraper massive https://example.com/products \
  --max-pages 50 \
  --use-browser \
  --export csv,json,excel
```

### 3. Wizard Mode (Interactive)

**Best for:** Creating reusable configurations

```bash
scraper wizard
```

Creates a saved job configuration you can run again:

```bash
scraper run my_job_name
```

### 4. Configuration File Mode

**Best for:** Complex, repeatable scraping tasks

Create a YAML config file:

```yaml
# my_scrape.yaml
name: "product_scraper"
start_url: "https://example.com"

item_selector: ".product"

fields:
  title:
    selector: ".title"
    type: "string"

  price:
    selector: ".price"
    type: "currency"

pagination:
  mode: "url_pattern"
  url_pattern: "https://example.com?page={page}"
  max_pages: 20

export:
  formats:
    - csv
    - json
```

Run it:

```bash
scraper run my_scrape.yaml
```

---

## Configuration

### Job Structure

A complete job configuration has these sections:

#### 1. Metadata

```yaml
name: "my_job"
description: "Description of what this scrapes"
enabled: true
tags: ["ecommerce", "products"]
```

#### 2. Target

```yaml
start_url: "https://example.com"
allowed_domains:
  - example.com
  - cdn.example.com
```

#### 3. Extraction

```yaml
# Container for each item (optional)
item_selector: ".product-card"

# Fields to extract
fields:
  title:
    selector: "h2.product-title"
    attr: "text"  # text, href, src, data-*, etc.
    type: "string"  # string, int, float, currency, date, etc.
    required: true

  price:
    selector: ".price"
    type: "currency"
    regex: "\\$([0-9.]+)"  # Optional regex extraction

  images:
    selector: "img.product-image"
    attr: "src"
    type: "url"
    multiple: true  # Returns list
```

#### 4. Pagination

**None (single page):**

```yaml
pagination:
  mode: "none"
```

**Next Button:**

```yaml
pagination:
  mode: "next_button"
  next_button_selector: ".pagination-next"
  max_pages: 10
```

**URL Pattern:**

```yaml
pagination:
  mode: "url_pattern"
  url_pattern: "https://example.com/page/{page}"
  start_page: 1
  max_pages: 20
```

**Infinite Scroll:**

```yaml
pagination:
  mode: "infinite_scroll"
  scroll_times: 10
  scroll_pause: 2.0  # seconds between scrolls
```

#### 5. Browser Settings

```yaml
browser:
  enabled: true
  headless: true
  wait_for_selector: ".content-loaded"
  wait_timeout: 30000  # milliseconds
  page_load_timeout: 60000
  viewport_width: 1920
  viewport_height: 1080
  block_images: false  # Speed up by blocking images
  capture_screenshot: false
```

#### 6. Rate Limiting

```yaml
rate_limit:
  enabled: true
  min_delay: 1.0  # seconds
  max_delay: 3.0
  max_concurrent_requests: 5
  respect_robots_txt: true
  requests_per_second: 2.0  # Optional hard limit
```

#### 7. Retries

```yaml
retry:
  max_retries: 3
  backoff_factor: 2.0
  retry_on_status:
    - 429  # Too Many Requests
    - 500
    - 502
    - 503
  timeout: 30  # seconds
```

#### 8. Proxies & Headers

```yaml
proxy:
  enabled: true
  proxy_list:
    - "http://proxy1.example.com:8080"
    - "http://proxy2.example.com:8080"
  rotation_strategy: "round_robin"  # round_robin, random, least_used

user_agent_strategy: "random"  # random, fixed, rotating_list

custom_headers:
  Accept-Language: "en-US,en;q=0.9"
  Custom-Header: "value"

cookies:
  session_id: "abc123"
```

#### 9. Export

```yaml
export:
  formats:
    - csv
    - json
    - excel
    - sqlite
  base_path: "~/scraper_results"
  filename_template: "{job_name}_{timestamp}"
  include_metadata: true
  compression: null  # gzip, zip, bz2
```

#### 10. Limits

```yaml
max_items: 500  # Stop after N items
```

---

## Advanced Features

### AI-Powered Extraction

Use Claude to extract complex data:

```yaml
fields:
  summary:
    use_llm: true
    llm_description: "Summarize the main points of this article in 2-3 sentences"
    type: "string"

  sentiment:
    use_llm: true
    llm_description: "Is the sentiment positive, negative, or neutral?"
    type: "string"

  entities:
    use_llm: true
    llm_description: "Extract all people, organizations, and locations mentioned"
    multiple: true
```

**Requirements:**
- Set `ANTHROPIC_API_KEY` environment variable
- Install: `pip install anthropic`

### Data Transformations

Apply transformations programmatically:

```python
from scraper.transforms.cleaning import DataCleaner
from scraper.transforms.type_inference import TypeInferrer
from scraper.transforms.deduplication import Deduplicator

# Clean data
cleaned_items = [DataCleaner.clean_item(item) for item in items]

# Infer types
schema = TypeInferrer.infer_schema(items)

# Deduplicate
unique_items = Deduplicator.deduplicate_by_key(items, "id")
```

### Programmatic Usage

```python
from scraper import ScrapeJob, ScraperEngine, FieldConfig
from scraper.export.export_manager import ExportManager
import asyncio

async def main():
    # Create job
    job = ScrapeJob(
        name="my_scrape",
        start_url="https://example.com",
        fields={
            "title": FieldConfig(selector=".title", type="string"),
            "price": FieldConfig(selector=".price", type="currency"),
        },
    )

    # Run scrape
    engine = ScraperEngine()
    result = await engine.run_job(job)

    print(f"Scraped {result.items_scraped} items")

    # Export
    export_mgr = ExportManager(job.export)
    files = await export_mgr.export_result(result)

    print(f"Exported to: {files}")

asyncio.run(main())
```

### Managing Jobs

**List saved jobs:**

```bash
scraper list
```

**Validate configuration:**

```bash
scraper validate config/my_job.yaml
```

**Run saved job:**

```bash
scraper run job_name
```

---

## Troubleshooting

### Common Issues

#### 1. "No items found"

**Cause:** Incorrect selector

**Solution:**
- Inspect the page HTML
- Use browser DevTools to test selectors
- Try different selector strategies (CSS vs XPath)
- Use `--use-browser` flag if content loads with JavaScript

#### 2. "Rate limited / 429 errors"

**Cause:** Scraping too fast

**Solution:**
```yaml
rate_limit:
  min_delay: 3.0  # Increase delays
  max_delay: 5.0
  max_concurrent_requests: 1  # Reduce concurrency
```

#### 3. "Browser timeout"

**Cause:** Page taking too long to load

**Solution:**
```yaml
browser:
  page_load_timeout: 120000  # Increase timeout
  wait_for_selector: ".specific-element"  # Wait for specific element
```

#### 4. "Blocked by website"

**Cause:** Bot detection

**Solution:**
- Respect robots.txt
- Add delays between requests
- Use realistic user agents
- Consider if scraping is allowed by ToS
- Use proxies (if legal/ethical)

#### 5. "Import errors"

**Cause:** Missing dependencies

**Solution:**
```bash
poetry install --no-root
playwright install chromium
```

### Debug Mode

Enable detailed logging:

```bash
scraper --debug easy https://example.com
```

### Getting Help

- Check example configs in `scraper/config/examples/`
- Read error messages carefully
- Enable debug mode
- Check website's robots.txt
- Review Terms of Service

---

## Best Practices

### 1. Be Polite

- ✅ Respect robots.txt
- ✅ Use reasonable delays (1-3 seconds)
- ✅ Limit concurrent requests
- ✅ Scrape during off-peak hours
- ❌ Don't overwhelm servers

### 2. Legal & Ethical

- ✅ Read and follow Terms of Service
- ✅ Only scrape public data
- ✅ Respect copyright and privacy
- ❌ Don't bypass authentication
- ❌ Don't circumvent paywalls

### 3. Data Quality

- ✅ Validate extracted data
- ✅ Handle missing values
- ✅ Use appropriate data types
- ✅ Deduplicate results
- ✅ Clean and normalize text

### 4. Performance

- ✅ Use static fetcher when possible (faster)
- ✅ Block unnecessary resources (images, CSS)
- ✅ Limit max pages/items
- ✅ Use efficient selectors
- ❌ Don't use browser mode unnecessarily

---

## Examples

See `scraper/config/examples/` for complete examples:

- `example_news.yaml` - News site scraper
- `example_ecommerce.yaml` - Product listing scraper
- `example_social_media.yaml` - Infinite scroll feed
- `example_ai_powered.yaml` - LLM-based extraction

---

## Export Formats

### CSV

Plain text, comma-separated values. Opens in Excel, Google Sheets, etc.

**Use for:** Simple data, spreadsheet analysis

### JSON

Structured JSON format with metadata.

**Use for:** APIs, web apps, developers

### Excel (.xlsx)

Excel workbook with data and metadata sheets.

**Use for:** Business users, advanced spreadsheet features

### SQLite

SQLite database file.

**Use for:** SQL queries, data analysis, integrations

---

## Next Steps

- [Developer Guide](DEV_GUIDE.md) - Contributing and architecture
- [API Reference](API_REFERENCE.md) - REST and GraphQL APIs
- [GitHub Issues](https://github.com/yourusername/GrannScraperV1-BIG/issues) - Report bugs or request features

---

**Happy Scraping! 🧓**
