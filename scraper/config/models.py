"""
Core data models for GrandmaScrape Platform.

Defines all configuration and runtime models using Pydantic v2.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class PaginationMode(str, Enum):
    """Pagination strategy modes."""

    NONE = "none"
    NEXT_BUTTON = "next_button"
    URL_PATTERN = "url_pattern"
    INFINITE_SCROLL = "infinite_scroll"


class UserAgentStrategy(str, Enum):
    """User agent rotation strategies."""

    RANDOM = "random"
    FIXED = "fixed"
    ROTATING_LIST = "rotating_list"


class FieldType(str, Enum):
    """Data types for extracted fields."""

    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    DATE = "date"
    DATETIME = "datetime"
    CURRENCY = "currency"
    URL = "url"
    EMAIL = "email"
    PHONE = "phone"


class FieldConfig(BaseModel):
    """Configuration for a single field to extract."""

    selector: Optional[str] = Field(
        None, description="CSS or XPath selector for the field"
    )
    attr: Optional[str] = Field(
        "text", description="HTML attribute to extract (text, href, src, etc.)"
    )
    type: FieldType = Field(
        FieldType.STRING, description="Data type of the field"
    )
    use_llm: bool = Field(
        False, description="Use LLM for intelligent extraction"
    )
    llm_description: Optional[str] = Field(
        None, description="Natural language description for LLM extraction"
    )
    required: bool = Field(
        False, description="Whether this field is required"
    )
    default: Optional[Any] = Field(
        None, description="Default value if extraction fails"
    )
    regex: Optional[str] = Field(
        None, description="Regex pattern to apply after extraction"
    )
    multiple: bool = Field(
        False, description="Extract multiple values (returns list)"
    )

    @field_validator("selector")
    @classmethod
    def validate_selector(cls, v: Optional[str]) -> Optional[str]:
        """Ensure selector is provided if not using LLM."""
        if v and v.strip():
            return v.strip()
        return None


class PaginationConfig(BaseModel):
    """Pagination configuration."""

    mode: PaginationMode = Field(
        PaginationMode.NONE, description="Pagination strategy"
    )
    next_button_selector: Optional[str] = Field(
        None, description="CSS selector for next button (next_button mode)"
    )
    url_pattern: Optional[str] = Field(
        None, description="URL pattern with {page} placeholder (url_pattern mode)"
    )
    start_page: int = Field(1, description="Starting page number", ge=1)
    max_pages: int = Field(10, description="Maximum pages to scrape", ge=1)
    scroll_times: int = Field(
        5, description="Number of scrolls (infinite_scroll mode)", ge=1
    )
    scroll_pause: float = Field(
        1.0, description="Pause between scrolls in seconds", ge=0.1
    )

    @model_validator(mode="after")
    def validate_pagination_config(self) -> "PaginationConfig":
        """Ensure required fields are set based on mode."""
        if self.mode == PaginationMode.NEXT_BUTTON and not self.next_button_selector:
            raise ValueError("next_button_selector required for next_button mode")
        if self.mode == PaginationMode.URL_PATTERN and not self.url_pattern:
            raise ValueError("url_pattern required for url_pattern mode")
        return self


class BrowserConfig(BaseModel):
    """Browser automation configuration."""

    enabled: bool = Field(False, description="Use browser automation")
    headless: bool = Field(True, description="Run browser in headless mode")
    wait_for_selector: Optional[str] = Field(
        None, description="Wait for this selector before extraction"
    )
    wait_timeout: int = Field(
        30000, description="Wait timeout in milliseconds", ge=1000
    )
    page_load_timeout: int = Field(
        60000, description="Page load timeout in milliseconds", ge=1000
    )
    user_agent: Optional[str] = Field(
        None, description="Custom user agent for browser"
    )
    viewport_width: int = Field(1920, description="Viewport width", ge=800)
    viewport_height: int = Field(1080, description="Viewport height", ge=600)
    javascript_enabled: bool = Field(True, description="Enable JavaScript")
    block_images: bool = Field(False, description="Block images for faster loading")
    block_css: bool = Field(False, description="Block CSS for faster loading")
    capture_screenshot: bool = Field(
        False, description="Capture screenshot of each page"
    )
    screenshot_path: Optional[Path] = Field(
        None, description="Directory to save screenshots"
    )


class ProxyConfig(BaseModel):
    """Proxy configuration."""

    enabled: bool = Field(False, description="Enable proxy rotation")
    proxy_list: list[str] = Field(
        default_factory=list, description="List of proxy URLs"
    )
    rotation_strategy: Literal["round_robin", "random", "least_used"] = Field(
        "round_robin", description="Proxy rotation strategy"
    )
    test_on_start: bool = Field(
        True, description="Test proxies before using"
    )

    @field_validator("proxy_list")
    @classmethod
    def validate_proxy_list(cls, v: list[str]) -> list[str]:
        """Ensure proxy URLs are valid."""
        if not v:
            return v
        # Basic validation - could be more sophisticated
        valid_proxies = []
        for proxy in v:
            if proxy.startswith(("http://", "https://", "socks5://")):
                valid_proxies.append(proxy)
        return valid_proxies


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    enabled: bool = Field(True, description="Enable rate limiting")
    min_delay: float = Field(
        1.0, description="Minimum delay between requests in seconds", ge=0.0
    )
    max_delay: float = Field(
        3.0, description="Maximum delay between requests in seconds", ge=0.0
    )
    max_concurrent_requests: int = Field(
        5, description="Maximum concurrent requests", ge=1, le=100
    )
    respect_robots_txt: bool = Field(
        True, description="Respect robots.txt directives"
    )
    requests_per_second: Optional[float] = Field(
        None, description="Hard limit on requests per second", ge=0.1
    )

    @model_validator(mode="after")
    def validate_delays(self) -> "RateLimitConfig":
        """Ensure min_delay <= max_delay."""
        if self.min_delay > self.max_delay:
            raise ValueError("min_delay must be <= max_delay")
        return self


class RetryConfig(BaseModel):
    """Retry configuration."""

    max_retries: int = Field(3, description="Maximum retry attempts", ge=0, le=10)
    backoff_factor: float = Field(
        2.0, description="Exponential backoff factor", ge=1.0
    )
    retry_on_status: list[int] = Field(
        default_factory=lambda: [429, 500, 502, 503, 504],
        description="HTTP status codes to retry on",
    )
    timeout: int = Field(
        30, description="Request timeout in seconds", ge=1, le=300
    )


class ExportConfig(BaseModel):
    """Export configuration."""

    formats: list[str] = Field(
        default_factory=lambda: ["csv"], description="Export formats"
    )
    base_path: Path = Field(
        Path.home() / "scraper_results", description="Base directory for exports"
    )
    filename_template: str = Field(
        "{job_name}_{timestamp}", description="Filename template"
    )
    include_metadata: bool = Field(
        True, description="Include metadata in exports"
    )
    compression: Optional[Literal["gzip", "zip", "bz2"]] = Field(
        None, description="Compression format"
    )


class ScrapeJob(BaseModel):
    """
    Complete scraping job configuration.

    This is the core model that defines everything about a scrape.
    """

    # Metadata
    id: str = Field(
        default_factory=lambda: f"job_{datetime.utcnow().timestamp()}",
        description="Unique job identifier",
    )
    name: str = Field(..., description="Human-readable job name")
    description: Optional[str] = Field(None, description="Job description")
    enabled: bool = Field(True, description="Whether job is enabled")
    tags: list[str] = Field(default_factory=list, description="Job tags")

    # Target
    start_url: str = Field(..., description="Starting URL")
    allowed_domains: list[str] = Field(
        default_factory=list, description="Allowed domains for crawling"
    )

    # Extraction
    item_selector: Optional[str] = Field(
        None, description="CSS/XPath selector for item containers"
    )
    fields: dict[str, FieldConfig] = Field(
        default_factory=dict, description="Field extraction configs"
    )

    # Pagination
    pagination: PaginationConfig = Field(
        default_factory=PaginationConfig, description="Pagination config"
    )

    # Browser
    browser: BrowserConfig = Field(
        default_factory=BrowserConfig, description="Browser config"
    )

    # Proxy & UA
    proxy: ProxyConfig = Field(
        default_factory=ProxyConfig, description="Proxy config"
    )
    user_agent_strategy: UserAgentStrategy = Field(
        UserAgentStrategy.RANDOM, description="User agent strategy"
    )
    user_agent_list: list[str] = Field(
        default_factory=list, description="Custom user agent list"
    )

    # Rate limiting & retries
    rate_limit: RateLimitConfig = Field(
        default_factory=RateLimitConfig, description="Rate limit config"
    )
    retry: RetryConfig = Field(
        default_factory=RetryConfig, description="Retry config"
    )

    # Limits
    max_items: Optional[int] = Field(
        None, description="Maximum items to scrape"
    )

    # Export
    export: ExportConfig = Field(
        default_factory=ExportConfig, description="Export config"
    )

    # Advanced
    custom_headers: dict[str, str] = Field(
        default_factory=dict, description="Custom HTTP headers"
    )
    cookies: dict[str, str] = Field(
        default_factory=dict, description="Custom cookies"
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )

    @field_validator("start_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Basic URL validation."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("start_url must begin with http:// or https://")
        return v

    @model_validator(mode="after")
    def set_allowed_domains(self) -> "ScrapeJob":
        """Auto-populate allowed_domains from start_url if empty."""
        if not self.allowed_domains and self.start_url:
            from urllib.parse import urlparse
            domain = urlparse(self.start_url).netloc
            if domain:
                self.allowed_domains = [domain]
        return self


class WorkflowStep(BaseModel):
    """A single step in a workflow."""

    id: str = Field(..., description="Step identifier")
    type: Literal["scrape", "transform", "export", "condition"] = Field(
        ..., description="Step type"
    )
    job_id: Optional[str] = Field(None, description="ScrapeJob ID for scrape steps")
    depends_on: list[str] = Field(
        default_factory=list, description="IDs of steps this depends on"
    )
    condition: Optional[str] = Field(
        None, description="Python expression for conditional execution"
    )
    config: dict[str, Any] = Field(
        default_factory=dict, description="Step-specific configuration"
    )


class Workflow(BaseModel):
    """
    Multi-step workflow / DAG configuration.

    Allows chaining jobs, transforms, and exports with dependencies.
    """

    id: str = Field(
        default_factory=lambda: f"workflow_{datetime.utcnow().timestamp()}",
        description="Unique workflow identifier",
    )
    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    enabled: bool = Field(True, description="Whether workflow is enabled")

    steps: list[WorkflowStep] = Field(
        ..., description="Workflow steps"
    )

    schedule: Optional[str] = Field(
        None, description="Cron expression for scheduling"
    )

    retry_policy: RetryConfig = Field(
        default_factory=RetryConfig, description="Workflow-level retry policy"
    )

    notifications: dict[str, Any] = Field(
        default_factory=dict, description="Notification settings"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )

    @model_validator(mode="after")
    def validate_dag(self) -> "Workflow":
        """Ensure steps form a valid DAG (no cycles)."""
        # Build dependency graph
        step_ids = {step.id for step in self.steps}

        # Check all dependencies exist
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    raise ValueError(f"Step {step.id} depends on non-existent step {dep}")

        # Simple cycle detection (could be more sophisticated)
        visited = set()
        rec_stack = set()

        def has_cycle(step_id: str) -> bool:
            visited.add(step_id)
            rec_stack.add(step_id)

            # Find step
            step = next((s for s in self.steps if s.id == step_id), None)
            if not step:
                return False

            for dep in step.depends_on:
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(step_id)
            return False

        for step in self.steps:
            if step.id not in visited:
                if has_cycle(step.id):
                    raise ValueError(f"Workflow contains cycle involving step {step.id}")

        return self


class ScrapeResult(BaseModel):
    """Result of a scrape operation."""

    job_id: str = Field(..., description="Job ID")
    status: Literal["success", "partial", "failed"] = Field(
        ..., description="Overall status"
    )
    items_scraped: int = Field(0, description="Number of items scraped")
    pages_visited: int = Field(0, description="Number of pages visited")
    errors: list[str] = Field(default_factory=list, description="Error messages")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    start_time: datetime = Field(
        default_factory=datetime.utcnow, description="Start timestamp"
    )
    end_time: Optional[datetime] = Field(None, description="End timestamp")
    duration_seconds: Optional[float] = Field(None, description="Duration in seconds")
    data: list[dict[str, Any]] = Field(
        default_factory=list, description="Scraped data"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    @model_validator(mode="after")
    def calculate_duration(self) -> "ScrapeResult":
        """Calculate duration if end_time is set."""
        if self.end_time and not self.duration_seconds:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
        return self
