"""
Pytest configuration and fixtures.
"""

import pytest


@pytest.fixture
def sample_html():
    """Sample HTML for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <div class="container">
            <article class="item">
                <h2 class="title">Item 1</h2>
                <p class="description">Description 1</p>
                <span class="price">$19.99</span>
                <a class="link" href="/item1">Link 1</a>
            </article>
            <article class="item">
                <h2 class="title">Item 2</h2>
                <p class="description">Description 2</p>
                <span class="price">$29.99</span>
                <a class="link" href="/item2">Link 2</a>
            </article>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_job_data():
    """Sample job configuration data."""
    return {
        "name": "test_job",
        "start_url": "https://example.com",
        "item_selector": ".item",
        "fields": {
            "title": {
                "selector": ".title",
                "type": "string",
            },
            "price": {
                "selector": ".price",
                "type": "currency",
            },
        },
        "pagination": {
            "mode": "none",
        },
        "export": {
            "formats": ["json"],
        },
    }

README config:
88: 
89: ### Example 2: Custom Job Config
90: 
91: ```yaml
92: # config/my_job.yaml
93: name: "Product Scraper"
94: start_url: "https://example.com/products"
95: use_browser: true
96: pagination_mode: "next_button"
97: next_button_selector: ".next-page"
98: max_pages: 50
99: 
100: fields:
101:   title:
102:     selector: "h1.product-title"
103:     type: "string"
104:   price:
105:     selector: ".price"
106:     type: "currency"
107:   rating:
108:     selector: ".rating"
109:     type: "float"
110: 
111: export_formats: ["csv", "json", "excel"]
112: ```
113: 
114: ```bash
115: scraper run config/my_job.yaml
116: ```
117: 
118: ### Example 3: Programmatic Usage
119: 
120: ```python
121: from scraper.core.engine import ScraperEngine
122: from scraper.config.models import ScrapeJob
123: 
124: job = ScrapeJob(
125:     name="my_scrape",
126:     start_url="https://example.com",
127:     item_selector=".product",
128:     fields={
129:         "title": {"selector": "h2", "type": "string"},
130:         "price": {"selector": ".price", "type": "currency"}
131:     },
132:     export_formats=["csv"]
133: )
134: 
135: engine = ScraperEngine()
136: results = await engine.run_job(job)
137: ```
SDK init:
44: class GrandmaScrapeClient:
45:     """
46:     Python SDK for GrandmaScrape API.
47: 
48:     Provides high-level methods for:
49:     - Auto-detection and scraping
50:     - Job management
51:     - Result retrieval
52:     - Workflow creation
53:     - Data quality analysis
54:     """
55: 
56:     def __init__(
57:         self,
58:         base_url: str = "http://localhost:8000",
59:         api_key: Optional[str] = None,
60:         timeout: float = 30.0
61:     ):
62:         """
63:         Initialize SDK client.
64: 
65:         Args:
66:             base_url: API server base URL
67:             api_key: Optional API key for authentication
68:             timeout: Request timeout in seconds
69:         """
70:         self.base_url = base_url.rstrip('/')
71:         self.api_key = api_key
72:         self.timeout = timeout
73: 
74:         headers = {}
75:         if api_key:
76:             headers['Authorization'] = f'Bearer {api_key}'
77: 
78:         self.client = httpx.Client(
79:             base_url=self.base_url,
80:             headers=headers,
81:             timeout=timeout
82:         )
83: 
84:         self.async_client = httpx.AsyncClient(
85:             base_url=self.base_url,
86:             headers=headers,
87:             timeout=timeout
88:         )
89: 
90:     def __enter__(self):
91:         return self
92: 
93:     def __exit__(self, exc_type, exc_val, exc_tb):
94:         self.close()
95: 
96:     def close(self):
97:         """Close HTTP clients."""
98:         self.client.close()
99: 
100:     async def aclose(self):
101:         """Close async HTTP client."""
102:         await self.async_client.aclose()
103: 
104:     # ============================================================================
105:     # HIGH-LEVEL METHODS (Grandma-simple!)
106:     # ============================================================================
107: 
108:     def auto_scrape(
109:         self,
110:         url: str,
