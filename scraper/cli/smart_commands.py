"""
Smart CLI commands with auto-detection and intelligence.

These commands use ML-inspired heuristics to automatically
configure scraping jobs with minimal user input.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from scraper.config.models import ScrapeJob, FieldConfig, ExportConfig
from scraper.core.engine import ScraperEngine
from scraper.core.concurrent_engine import ConcurrentScraper
from scraper.core.fetcher_static import StaticFetcher
from scraper.strategies.intelligent_extraction import (
    IntelligentExtractor,
    SmartPaginationDetector,
)
from scraper.export.export_manager import ExportManager

console = Console()
logger = logging.getLogger(__name__)


@click.command()
@click.argument('url')
@click.option('--analyze-only', is_flag=True, help='Only analyze, don\'t scrape')
@click.option('--max-pages', default=10, help='Maximum pages to scrape')
@click.option('--export', default='csv,json', help='Export formats (comma-separated)')
@click.option('--concurrent', is_flag=True, help='Use high-performance concurrent scraping')
def smart(url: str, analyze_only: bool, max_pages: int, export: str, concurrent: bool):
    """
    🧠 SMART MODE - AI-powered auto-detection.

    Automatically detects:
    - Item containers
    - Field names and types
    - Pagination patterns
    - Best extraction strategy

    Example:
        scraper smart https://news.ycombinator.com --max-pages 5
    """
    console.print("\n[bold cyan]🧠 GrandmaScrape SMART Mode[/bold cyan]")
    console.print("Using AI-powered auto-detection...\n")

    asyncio.run(_run_smart_scrape(url, analyze_only, max_pages, export, concurrent))


async def _run_smart_scrape(
    url: str,
    analyze_only: bool,
    max_pages: int,
    export_formats: str,
    use_concurrent: bool
):
    """Execute smart scraping with auto-detection."""

    # Step 1: Fetch initial page
    console.print("[bold]Step 1:[/bold] Analyzing page structure...")

    # Create minimal job for initial fetch
    temp_job = ScrapeJob(
        name="temp_analysis",
        start_url=url,
    )

    async with StaticFetcher(temp_job) as fetcher:
        soup, html = await fetcher.fetch(url)

        if not soup:
            console.print("[bold red]✗ Failed to fetch page[/bold red]")
            return

    # Step 2: Auto-detect structure
    console.print("[bold]Step 2:[/bold] Auto-detecting structure...")

    intelligent_extractor = IntelligentExtractor()
    pagination_detector = SmartPaginationDetector()

    # Detect item container
    item_selector = await intelligent_extractor.auto_detect_item_container(soup)

    if not item_selector:
        console.print("[yellow]⚠ Could not detect item container[/yellow]")
        console.print("[dim]This might be a single-item page or unusual structure[/dim]")

        # Try to scrape anyway as single item
        item_selector = "body"

    # Detect fields
    detected_fields = await intelligent_extractor.auto_detect_fields(soup, item_selector)

    # Detect pagination
    pagination_config = await pagination_detector.detect_pagination(soup, url)

    # Step 3: Display analysis
    _display_analysis(url, item_selector, detected_fields, pagination_config)

    if analyze_only:
        console.print("\n[bold green]✓ Analysis complete[/bold green]")
        return

    # Step 4: Confirm and scrape
    if not click.confirm("\n[bold]Proceed with scraping?[/bold]", default=True):
        console.print("[yellow]Cancelled[/yellow]")
        return

    # Build job from detected configuration
    job = _build_job_from_detection(
        url,
        item_selector,
        detected_fields,
        pagination_config,
        max_pages,
        export_formats,
    )

    # Step 5: Execute scrape
    console.print("\n[bold]Step 5:[/bold] Scraping...")

    if use_concurrent:
        await _run_concurrent_scrape(job)
    else:
        await _run_standard_scrape(job)


def _display_analysis(
    url: str,
    item_selector: Optional[str],
    detected_fields: dict,
    pagination_config: dict
):
    """Display analysis results in a pretty format."""

    console.print()

    # Overview panel
    overview = Panel(
        f"[bold]URL:[/bold] {url}\n"
        f"[bold]Item Selector:[/bold] {item_selector or '[yellow]Not detected[/yellow]'}\n"
        f"[bold]Fields Detected:[/bold] {len(detected_fields)}\n"
        f"[bold]Pagination:[/bold] {pagination_config.get('mode', 'none')}",
        title="[bold cyan]Auto-Detection Results[/bold cyan]",
        border_style="cyan"
    )
    console.print(overview)

    # Fields table
    if detected_fields:
        console.print("\n[bold]Detected Fields:[/bold]")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Field Name", style="cyan")
        table.add_column("Selector", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Confidence", style="blue")

        for field_name, config in detected_fields.items():
            confidence = config.get('confidence', 0)
            confidence_str = f"{confidence:.0%}"

            table.add_row(
                field_name,
                config.get('selector', 'N/A'),
                config.get('type', 'string'),
                confidence_str
            )

        console.print(table)

    # Pagination info
    if pagination_config.get('mode') != 'none':
        console.print(f"\n[bold]Pagination:[/bold] {pagination_config['mode']}")

        if pagination_config['mode'] == 'next_button':
            console.print(f"  Next button: {pagination_config.get('next_button_selector')}")
        elif pagination_config['mode'] == 'url_pattern':
            console.print(f"  URL pattern: {pagination_config.get('url_pattern')}")

        console.print(f"  Confidence: {pagination_config.get('confidence', 0):.0%}")


def _build_job_from_detection(
    url: str,
    item_selector: Optional[str],
    detected_fields: dict,
    pagination_config: dict,
    max_pages: int,
    export_formats: str,
) -> ScrapeJob:
    """Build ScrapeJob from detection results."""

    # Convert detected fields to FieldConfig
    fields = {}
    for field_name, config in detected_fields.items():
        fields[field_name] = FieldConfig(
            selector=config.get('selector'),
            attr=config.get('attr', 'text'),
            type=config.get('type', 'string'),
            multiple=config.get('multiple', False),
        )

    # Build pagination config
    from scraper.config.models import PaginationConfig, PaginationMode

    if pagination_config.get('mode') == 'next_button':
        pagination = PaginationConfig(
            mode=PaginationMode.NEXT_BUTTON,
            next_button_selector=pagination_config.get('next_button_selector'),
            max_pages=max_pages,
        )
    elif pagination_config.get('mode') == 'url_pattern':
        pagination = PaginationConfig(
            mode=PaginationMode.URL_PATTERN,
            url_pattern=pagination_config.get('url_pattern'),
            max_pages=max_pages,
        )
    else:
        pagination = PaginationConfig(mode=PaginationMode.NONE)

    # Parse export formats
    formats = [f.strip() for f in export_formats.split(',')]

    # Create job
    job = ScrapeJob(
        name=f"smart_{url.split('//')[1].split('/')[0]}",
        start_url=url,
        item_selector=item_selector,
        fields=fields,
        pagination=pagination,
        export=ExportConfig(formats=formats),
    )

    return job


async def _run_standard_scrape(job: ScrapeJob):
    """Run standard scraping."""
    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scraping pages...", total=None)

        engine = ScraperEngine()
        result = await engine.run_job(job)

        progress.update(task, description="[green]✓ Scraping complete")

    # Export
    export_manager = ExportManager(job.export)
    exported_files = await export_manager.export_result(result)

    # Display results
    _display_results(result, exported_files)


async def _run_concurrent_scrape(job: ScrapeJob):
    """Run high-performance concurrent scraping."""
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn

    console.print("\n[bold cyan]⚡ High-Performance Concurrent Mode[/bold cyan]")

    # Create concurrent scraper
    concurrent_scraper = ConcurrentScraper(job, max_workers=10)

    # Generate URLs
    from scraper.core.engine import ScraperEngine
    engine = ScraperEngine()
    urls = await engine._generate_urls(job)

    # Add all URLs to queue
    for url in urls:
        await concurrent_scraper.add_urls([url])

    # Create scrape function
    async def scrape_single_url(url: str):
        """Scrape a single URL."""
        temp_job = ScrapeJob(
            name=job.name,
            start_url=url,
            item_selector=job.item_selector,
            fields=job.fields,
        )

        engine = ScraperEngine()
        result = await engine.run_job(temp_job)
        return result.data

    # Run with progress bar
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"Scraping {len(urls)} pages...",
            total=len(urls)
        )

        # Start scraping
        scrape_task = asyncio.create_task(concurrent_scraper.run(scrape_single_url))

        # Update progress
        while not scrape_task.done():
            stats = concurrent_scraper.get_progress()
            if stats:
                progress.update(task, completed=stats['completed'] + stats['failed'])
            await asyncio.sleep(0.5)

        result = await scrape_task

    # Export
    export_manager = ExportManager(job.export)
    exported_files = await export_manager.export_result(result)

    # Display results
    _display_results(result, exported_files)


def _display_results(result, exported_files):
    """Display scraping results."""

    # Results panel
    console.print()

    if result.status == 'success':
        status_color = "green"
        status_icon = "✓"
    elif result.status == 'partial':
        status_color = "yellow"
        status_icon = "⚠"
    else:
        status_color = "red"
        status_icon = "✗"

    results_panel = Panel(
        f"[bold]Status:[/bold] [{status_color}]{status_icon} {result.status.upper()}[/{status_color}]\n"
        f"[bold]Items Scraped:[/bold] {result.items_scraped}\n"
        f"[bold]Pages Visited:[/bold] {result.pages_visited}\n"
        f"[bold]Errors:[/bold] {len(result.errors)}\n"
        f"[bold]Duration:[/bold] {result.duration_seconds:.2f}s\n"
        f"[bold]Speed:[/bold] {result.items_scraped / max(result.duration_seconds, 0.001):.2f} items/sec",
        title="[bold green]Results[/bold green]",
        border_style="green"
    )
    console.print(results_panel)

    # Exported files
    if exported_files:
        console.print("\n[bold]Exported Files:[/bold]")
        for fmt, path in exported_files.items():
            console.print(f"  • {fmt.upper()}: [cyan]{path}[/cyan]")

    # Errors (if any)
    if result.errors:
        console.print(f"\n[bold yellow]Warnings/Errors:[/bold yellow]")
        for error in result.errors[:5]:  # Show first 5
            console.print(f"  • {error}")
        if len(result.errors) > 5:
            console.print(f"  ... and {len(result.errors) - 5} more")


@click.command()
@click.argument('url')
def analyze(url: str):
    """
    🔍 ANALYZE MODE - Deep site analysis.

    Analyzes website structure without scraping.

    Shows:
    - Detected patterns
    - Suggested selectors
    - Pagination detection
    - Estimated scraping time
    - Recommended settings
    """
    console.print("\n[bold cyan]🔍 GrandmaScrape ANALYZE Mode[/bold cyan]")
    console.print("Performing deep analysis...\n")

    asyncio.run(_analyze_site(url))


async def _analyze_site(url: str):
    """Perform deep site analysis."""

    # Fetch page
    temp_job = ScrapeJob(name="analysis", start_url=url)

    async with StaticFetcher(temp_job) as fetcher:
        soup, html = await fetcher.fetch(url)

        if not soup:
            console.print("[bold red]✗ Failed to fetch page[/bold red]")
            return

    # Analyze
    intelligent_extractor = IntelligentExtractor()
    pagination_detector = SmartPaginationDetector()

    item_selector = await intelligent_extractor.auto_detect_item_container(soup)
    detected_fields = await intelligent_extractor.auto_detect_fields(soup, item_selector or "body")
    pagination_config = await pagination_detector.detect_pagination(soup, url)

    # Display comprehensive analysis
    _display_comprehensive_analysis(
        url, soup, html, item_selector, detected_fields, pagination_config
    )


def _display_comprehensive_analysis(
    url, soup, html, item_selector, detected_fields, pagination_config
):
    """Display comprehensive analysis."""

    # Site overview
    console.print("[bold]Site Overview:[/bold]")
    console.print(f"  URL: {url}")
    console.print(f"  HTML Size: {len(html):,} bytes")
    console.print(f"  Title: {soup.title.string if soup.title else 'N/A'}")

    # Count elements
    links = len(soup.find_all('a'))
    images = len(soup.find_all('img'))
    forms = len(soup.find_all('form'))

    console.print(f"  Links: {links}")
    console.print(f"  Images: {images}")
    console.print(f"  Forms: {forms}")

    # Structure analysis
    console.print("\n[bold]Structure Analysis:[/bold]")
    console.print(f"  Item Container: {item_selector or '[yellow]Not detected[/yellow]'}")

    if item_selector:
        items = soup.select(item_selector)
        console.print(f"  Items Found: {len(items)}")

    # Fields
    console.print(f"\n[bold]Detected Fields:[/bold] {len(detected_fields)}")
    for field_name, config in detected_fields.items():
        console.print(f"  • {field_name}: {config.get('selector')} ({config.get('type')})")

    # Pagination
    console.print(f"\n[bold]Pagination:[/bold] {pagination_config.get('mode')}")

    # Recommendations
    console.print("\n[bold cyan]Recommendations:[/bold cyan]")

    tree = Tree("💡 Scraping Strategy")

    if not item_selector:
        tree.add("[yellow]⚠ No repeating pattern detected - might be single item page[/yellow]")
        tree.add("[cyan]→ Use single-page mode[/cyan]")
    else:
        tree.add(f"[green]✓ Detected {len(soup.select(item_selector))} items[/green]")
        tree.add(f"[cyan]→ Use selector: {item_selector}[/cyan]")

    if detected_fields:
        tree.add(f"[green]✓ Auto-detected {len(detected_fields)} fields[/green]")
    else:
        tree.add("[yellow]⚠ No fields auto-detected - may need manual configuration[/yellow]")

    if pagination_config.get('mode') != 'none':
        tree.add(f"[green]✓ Pagination detected: {pagination_config['mode']}[/green]")
    else:
        tree.add("[yellow]⚠ No pagination detected - single page only[/yellow]")

    # Performance estimate
    if item_selector:
        items_count = len(soup.select(item_selector))
        estimated_time = items_count * 2  # ~2 seconds per page
        tree.add(f"[blue]ℹ Estimated time: ~{estimated_time}s for 1 page[/blue]")

    console.print(tree)

    # Next steps
    console.print("\n[bold green]Next Steps:[/bold green]")
    console.print("  1. Review detected configuration above")
    console.print("  2. Run: [cyan]scraper smart " + url + "[/cyan]")
    console.print("  3. Or create custom config in YAML")
