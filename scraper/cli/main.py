"""
CLI entry point for GrandmaScrape.

Provides easy, massive, wizard, and advanced modes.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from scraper.config.models import ScrapeJob, FieldConfig, ExportConfig
from scraper.core.engine import ScraperEngine
from scraper.export.export_manager import ExportManager

# Import smart commands
from scraper.cli.smart_commands import smart, analyze

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def cli(debug: bool) -> None:
    """
    GrandmaScrape - Enterprise web scraping made grandma-simple.

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

    Use 'scraper COMMAND --help' for more information on a command.
    """
    # Configure logging
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s" if not debug else "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@cli.command()
@click.argument("url")
def easy(url: str) -> None:
    """
    EASY MODE - Grandma-friendly scraping.

    Just paste a URL and answer 3 simple questions!

    Example:
        scraper easy https://example.com
    """
    console.print("\n[bold green]🧓 GrandmaScrape Easy Mode[/bold green]")
    console.print("I'll help you scrape this website in just 3 questions!\n")

    # Question 1: What to get
    console.print("[bold]Question 1:[/bold] What are you trying to get from this page?")
    console.print("  (Examples: titles, prices, names, articles, products)")
    what_to_get = click.prompt("  Your answer", default="items")

    # Question 2: How many pages
    console.print("\n[bold]Question 2:[/bold] About how many pages should I look through?")
    console.print("  (Just give me a number, or say 'just one')")
    pages_input = click.prompt("  Your answer", default="just one")

    if "one" in pages_input.lower():
        max_pages = 1
    else:
        try:
            max_pages = int(pages_input.split()[0])
        except:
            max_pages = 1

    # Question 3: Filename
    console.print("\n[bold]Question 3:[/bold] What should I name your file?")
    console.print("  (I'll add .csv automatically)")
    filename = click.prompt("  Your answer", default="my_scrape")

    # Clean and validate filename
    import re
    filename = filename.replace(".csv", "")
    # Only allow alphanumeric, dash, underscore
    filename = re.sub(r'[^a-zA-Z0-9_-]', '_', filename)[:100]

    console.print("\n[bold cyan]Great! I'm ready to scrape![/bold cyan]")
    console.print(f"  • Getting: {what_to_get}")
    console.print(f"  • Pages: {max_pages}")
    console.print(f"  • Saving as: {filename}.csv")
    console.print()

    if not click.confirm("Should I start?", default=True):
        console.print("[yellow]Okay, maybe next time![/yellow]")
        return

    # Build a simple job
    job = ScrapeJob(
        name=f"easy_{filename}",
        start_url=url,
        description=f"Easy mode scrape for {what_to_get}",
        pagination={"mode": "none" if max_pages == 1 else "url_pattern", "max_pages": max_pages},
        fields={},  # Will use auto-detection
        export=ExportConfig(
            formats=["csv"],
            filename_template=filename,
        ),
    )

    # Run the scrape
    asyncio.run(_run_easy_job(job, what_to_get))


async def _run_easy_job(job: ScrapeJob, what_to_get: str) -> None:
    """Run easy mode job with friendly progress."""
    console.print("\n[bold]I'm starting to work...[/bold]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Opening the website...", total=None)

        engine = ScraperEngine()

        # Update progress messages
        progress.update(task, description=f"Looking for {what_to_get}...")

        result = await engine.run_job(job)

        progress.update(task, description="Almost done, saving your file...")

        # Export results
        export_manager = ExportManager(job.export)
        exported_files = await export_manager.export_result(result)

    # Report results
    console.print()
    if result.status == "success":
        console.print(f"[bold green]✓ Success![/bold green] I found {result.items_scraped} {what_to_get}.")

        if exported_files:
            file_path = list(exported_files.values())[0]
            console.print(f"[bold]Your file is ready:[/bold] {file_path}")
            console.print(f"\n[dim]Open it with Excel, Google Sheets, or any spreadsheet program![/dim]")
    else:
        console.print(f"[bold yellow]⚠ Hmm, I had some trouble.[/bold yellow]")
        console.print(f"I found {result.items_scraped} items, but there were {len(result.errors)} errors.")

        if result.errors:
            console.print("\n[bold]What went wrong:[/bold]")
            for error in result.errors[:3]:  # Show first 3 errors
                console.print(f"  • {error}")


@cli.command()
@click.argument("url")
@click.option("--max-pages", default=10, help="Maximum pages to scrape")
@click.option("--use-browser", is_flag=True, help="Use browser for JavaScript sites")
@click.option("--export", default="csv", help="Export formats (comma-separated: csv,json,excel)")
@click.option("--output-dir", type=click.Path(), help="Output directory")
def massive(
    url: str,
    max_pages: int,
    use_browser: bool,
    export: str,
    output_dir: Optional[str],
) -> None:
    """
    MASSIVE MODE - Maximum power with smart defaults.

    Intelligently scrapes sites with auto-detection.

    Example:
        scraper massive https://example.com --max-pages 100 --export csv,json
    """
    console.print("\n[bold magenta]⚡ GrandmaScrape MASSIVE Mode[/bold magenta]")
    console.print("Engaging maximum power with intelligent detection...\n")

    # Parse export formats
    export_formats = [fmt.strip() for fmt in export.split(",")]

    # Build output path
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = Path.home() / "scraper_results"

    # Create job with smart defaults
    job = ScrapeJob(
        name=f"massive_{url.split('//')[1].split('/')[0]}",
        start_url=url,
        description="Massive mode scrape with auto-detection",
        browser={"enabled": use_browser},
        pagination={"mode": "url_pattern", "max_pages": max_pages},
        fields={},  # Auto-detect
        export=ExportConfig(
            formats=export_formats,
            base_path=output_path,
        ),
    )

    console.print(f"[bold]Configuration:[/bold]")
    console.print(f"  • URL: {url}")
    console.print(f"  • Max pages: {max_pages}")
    console.print(f"  • Browser mode: {'ON' if use_browser else 'OFF'}")
    console.print(f"  • Export formats: {', '.join(export_formats)}")
    console.print()

    asyncio.run(_run_massive_job(job))


async def _run_massive_job(job: ScrapeJob) -> None:
    """Run massive mode job."""
    with Progress(console=console) as progress:
        task = progress.add_task(
            "[cyan]Scraping in progress...", total=job.pagination.max_pages
        )

        engine = ScraperEngine()
        result = await engine.run_job(job)

        progress.update(task, completed=result.pages_visited)

    # Export
    export_manager = ExportManager(job.export)
    exported_files = await export_manager.export_result(result)

    # Results table
    table = Table(title="Scrape Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Status", result.status.upper())
    table.add_row("Items Scraped", str(result.items_scraped))
    table.add_row("Pages Visited", str(result.pages_visited))
    table.add_row("Errors", str(len(result.errors)))
    table.add_row("Duration", f"{result.duration_seconds:.2f}s")

    console.print()
    console.print(table)

    if exported_files:
        console.print("\n[bold]Exported Files:[/bold]")
        for fmt, path in exported_files.items():
            console.print(f"  • {fmt.upper()}: {path}")


@cli.command()
def wizard() -> None:
    """
    WIZARD MODE - Interactive job creation.

    Step-by-step guidance to create a custom scraping job.
    """
    console.print("\n[bold blue]🧙 GrandmaScrape Wizard[/bold blue]")
    console.print("I'll guide you through creating a custom scraping job.\n")

    # Step 1: URL
    url = click.prompt("[bold]Step 1: URL[/bold]\n  What website do you want to scrape?")

    # Step 2: Name
    name = click.prompt("\n[bold]Step 2: Job Name[/bold]\n  Give this scrape a name", default="my_scrape")

    # Step 3: Browser
    console.print("\n[bold]Step 3: Browser Mode[/bold]")
    console.print("  Does this site need JavaScript to load content?")
    console.print("  (Examples: SPAs, sites with infinite scroll)")
    use_browser = click.confirm("  Use browser mode?", default=False)

    # Step 4: Pagination
    console.print("\n[bold]Step 4: Pagination[/bold]")
    console.print("  How are pages organized?")
    console.print("  1. Single page only")
    console.print("  2. Next button (like 'Next >'))")
    console.print("  3. Page numbers in URL (like /page/1, /page/2)")
    console.print("  4. Infinite scroll")

    pagination_choice = click.prompt("  Your choice", type=int, default=1)

    pagination_config = {"mode": "none"}

    if pagination_choice == 2:
        pagination_config["mode"] = "next_button"
        next_selector = click.prompt("  CSS selector for next button", default=".next, .pagination-next")
        pagination_config["next_button_selector"] = next_selector
    elif pagination_choice == 3:
        pagination_config["mode"] = "url_pattern"
        url_pattern = click.prompt("  URL pattern (use {page} for page number)", default=f"{url}?page={{page}}")
        pagination_config["url_pattern"] = url_pattern
    elif pagination_choice == 4:
        pagination_config["mode"] = "infinite_scroll"

    if pagination_choice > 1:
        max_pages = click.prompt("  Maximum pages to scrape", type=int, default=10)
        pagination_config["max_pages"] = max_pages

    # Step 5: Export
    console.print("\n[bold]Step 5: Export Format[/bold]")
    console.print("  How do you want your data?")
    console.print("  1. CSV (spreadsheet)")
    console.print("  2. JSON (for developers)")
    console.print("  3. Excel (.xlsx)")
    console.print("  4. All of the above")

    export_choice = click.prompt("  Your choice", type=int, default=1)

    export_formats = {
        1: ["csv"],
        2: ["json"],
        3: ["excel"],
        4: ["csv", "json", "excel"],
    }.get(export_choice, ["csv"])

    # Build job
    job_data = {
        "name": name,
        "start_url": url,
        "browser": {"enabled": use_browser},
        "pagination": pagination_config,
        "export": {
            "formats": export_formats,
        },
        "fields": {},
    }

    # Save config
    import re
    # Sanitize job name for filesystem
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)[:100]

    config_dir = Path.home() / ".grandma-scraper" / "jobs"
    config_dir.mkdir(parents=True, exist_ok=True)

    import yaml
    config_file = config_dir / f"{safe_name}.yaml"

    with open(config_file, "w") as f:
        yaml.dump(job_data, f, default_flow_style=False)

    console.print(f"\n[bold green]✓ Configuration saved![/bold green]")
    console.print(f"  Location: {config_file}")
    console.print(f"\n[bold]To run this job:[/bold]")
    console.print(f"  scraper run {safe_name}")

    if click.confirm("\nRun it now?", default=True):
        ctx = click.get_current_context()
        ctx.invoke(run, job_name=name)


@cli.command()
@click.argument("job_name")
def run(job_name: str) -> None:
    """
    Run a saved scraping job.

    Example:
        scraper run my_job
    """
    import re
    # Sanitize job_name to prevent path traversal
    safe_job_name = re.sub(r'[^a-zA-Z0-9_-]', '_', job_name)[:100]

    # Load job config
    config_dir = Path.home() / ".grandma-scraper" / "jobs"
    config_file = config_dir / f"{safe_job_name}.yaml"

    if not config_file.exists():
        console.print(f"[bold red]✗ Job '{safe_job_name}' not found![/bold red]")
        console.print(f"  Looking for: {config_file}")
        return

    import yaml
    with open(config_file) as f:
        job_data = yaml.safe_load(f)

    # Create job
    job = ScrapeJob(**job_data)

    console.print(f"\n[bold]Running job: {job.name}[/bold]")

    asyncio.run(_run_job(job))


async def _run_job(job: ScrapeJob) -> None:
    """Run a job and export results."""
    engine = ScraperEngine()

    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Scraping...", total=None)

        result = await engine.run_job(job)

        progress.update(task, description="[cyan]Exporting results...")

        export_manager = ExportManager(job.export)
        exported_files = await export_manager.export_result(result)

    console.print(f"\n[bold green]✓ Complete![/bold green]")
    console.print(f"  Items: {result.items_scraped}")
    console.print(f"  Pages: {result.pages_visited}")

    if exported_files:
        console.print("\n[bold]Files:[/bold]")
        for fmt, path in exported_files.items():
            console.print(f"  • {path}")


@cli.command()
def list() -> None:
    """List all saved scraping jobs."""
    config_dir = Path.home() / ".grandma-scraper" / "jobs"

    if not config_dir.exists():
        console.print("[yellow]No saved jobs yet![/yellow]")
        console.print("Create one with: scraper wizard")
        return

    job_files = list(config_dir.glob("*.yaml"))

    if not job_files:
        console.print("[yellow]No saved jobs yet![/yellow]")
        return

    table = Table(title="Saved Jobs")
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="blue")
    table.add_column("Browser", style="green")

    import yaml
    for job_file in job_files:
        with open(job_file) as f:
            job_data = yaml.safe_load(f)

        name = job_data.get("name", job_file.stem)
        url = job_data.get("start_url", "")
        browser = "Yes" if job_data.get("browser", {}).get("enabled") else "No"

        table.add_row(name, url, browser)

    console.print(table)


@cli.command()
@click.argument("config_path", type=click.Path(exists=True))
def validate(config_path: str) -> None:
    """
    Validate a job configuration file.

    Example:
        scraper validate config/my_job.yaml
    """
    import yaml

    try:
        with open(config_path) as f:
            job_data = yaml.safe_load(f)

        # Try to create job (validates schema)
        job = ScrapeJob(**job_data)

        console.print(f"[bold green]✓ Configuration is valid![/bold green]")
        console.print(f"\n[bold]Job Details:[/bold]")
        console.print(f"  Name: {job.name}")
        console.print(f"  URL: {job.start_url}")
        console.print(f"  Fields: {len(job.fields)}")
        console.print(f"  Export formats: {', '.join(job.export.formats)}")

    except Exception as e:
        console.print(f"[bold red]✗ Configuration is invalid![/bold red]")
        console.print(f"\n[bold]Error:[/bold] {e}")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload (development)")
def serve(host: str, port: int, reload: bool) -> None:
    """
    Start the API server with web dashboard.

    This starts the FastAPI server that provides:
    - REST API for programmatic access
    - Web dashboard at http://localhost:8000
    - API documentation at http://localhost:8000/docs

    Examples:
        scraper serve                  # Start on default port 8000
        scraper serve --port 3000      # Start on custom port
        scraper serve --reload         # Development mode with auto-reload
    """
    try:
        import uvicorn
        from scraper.api.rest_server import app
    except ImportError:
        console.print("[bold red]Error:[/bold red] uvicorn not installed")
        console.print("Install with: poetry install")
        return

    console.print("[bold cyan]🧓 GrandmaScrape API Server[/bold cyan]\n")
    console.print(f"[bold]Starting server on {host}:{port}[/bold]")
    console.print(f"\n[green]✓[/green] Dashboard:      http://localhost:{port}")
    console.print(f"[green]✓[/green] API Docs:       http://localhost:{port}/docs")
    console.print(f"[green]✓[/green] Health Check:   http://localhost:{port}/api/v1/health")
    console.print("\n[dim]Press Ctrl+C to stop[/dim]\n")

    uvicorn.run(
        "scraper.api.rest_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


# Register smart commands
cli.add_command(smart)
cli.add_command(analyze)


if __name__ == "__main__":
    cli()
