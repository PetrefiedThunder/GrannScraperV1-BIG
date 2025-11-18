"""
Real-time monitoring and live dashboard.

Displays live statistics, progress, and performance metrics
during scraping operations.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.table import Table
from rich.layout import Layout


class LiveDashboard:
    """
    Real-time dashboard for monitoring scraping operations.

    Displays:
    - Current progress
    - Speed metrics
    - Error rates
    - Domain statistics
    - Memory usage
    - ETA
    """

    def __init__(self):
        self.console = Console()
        self.start_time = datetime.utcnow()

        self.stats = {
            'pages_scraped': 0,
            'items_scraped': 0,
            'errors': 0,
            'bytes_downloaded': 0,
            'active_workers': 0,
            'domains': {},  # domain -> count
            'recent_speeds': [],  # Last N speeds for averaging
            'recent_urls': [],  # Last N URLs scraped
        }

    def update(self, **kwargs):
        """Update dashboard statistics."""
        for key, value in kwargs.items():
            if key in self.stats:
                if isinstance(self.stats[key], dict):
                    self.stats[key].update(value)
                elif isinstance(self.stats[key], list):
                    self.stats[key].append(value)
                    # Keep last 100
                    self.stats[key] = self.stats[key][-100:]
                else:
                    self.stats[key] = value

    def get_layout(self) -> Layout:
        """Generate dashboard layout."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=7),
        )

        layout["main"].split_row(
            Layout(name="stats"),
            Layout(name="domains"),
        )

        # Header
        layout["header"].update(
            Panel(
                "[bold cyan]🧓 GrandmaScrape Live Dashboard[/bold cyan]",
                style="bold white on blue"
            )
        )

        # Stats
        layout["stats"].update(self._create_stats_panel())

        # Domain breakdown
        layout["domains"].update(self._create_domains_panel())

        # Footer with recent activity
        layout["footer"].update(self._create_activity_panel())

        return layout

    def _create_stats_panel(self) -> Panel:
        """Create statistics panel."""
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()

        # Calculate metrics
        pages_per_sec = self.stats['pages_scraped'] / elapsed if elapsed > 0 else 0
        items_per_sec = self.stats['items_scraped'] / elapsed if elapsed > 0 else 0
        mb_downloaded = self.stats['bytes_downloaded'] / (1024 * 1024)

        # Average recent speed
        avg_speed = 0
        if self.stats['recent_speeds']:
            avg_speed = sum(self.stats['recent_speeds']) / len(self.stats['recent_speeds'])

        # Error rate
        total_attempts = self.stats['pages_scraped'] + self.stats['errors']
        error_rate = (self.stats['errors'] / total_attempts * 100) if total_attempts > 0 else 0

        stats_table = Table(show_header=False, box=None, padding=(0, 2))
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green bold")

        stats_table.add_row("Pages Scraped", f"{self.stats['pages_scraped']:,}")
        stats_table.add_row("Items Extracted", f"{self.stats['items_scraped']:,}")
        stats_table.add_row("Active Workers", f"{self.stats['active_workers']}")
        stats_table.add_row("Errors", f"[red]{self.stats['errors']}[/red]")
        stats_table.add_row("Error Rate", f"[red]{error_rate:.1f}%[/red]" if error_rate > 5 else f"{error_rate:.1f}%")
        stats_table.add_row("", "")
        stats_table.add_row("Speed", f"{pages_per_sec:.2f} pages/sec")
        stats_table.add_row("Throughput", f"{items_per_sec:.2f} items/sec")
        stats_table.add_row("Data Downloaded", f"{mb_downloaded:.2f} MB")
        stats_table.add_row("Elapsed Time", f"{elapsed:.0f}s")

        return Panel(stats_table, title="[bold]Statistics[/bold]", border_style="cyan")

    def _create_domains_panel(self) -> Panel:
        """Create domain breakdown panel."""
        if not self.stats['domains']:
            return Panel("No domains yet...", title="[bold]Domains[/bold]")

        # Sort domains by count
        sorted_domains = sorted(
            self.stats['domains'].items(),
            key=lambda x: x[1],
            reverse=True
        )

        domains_table = Table(show_header=True, box=None)
        domains_table.add_column("Domain", style="cyan")
        domains_table.add_column("Pages", style="green", justify="right")

        for domain, count in sorted_domains[:10]:  # Top 10
            domains_table.add_row(domain, f"{count:,}")

        if len(sorted_domains) > 10:
            domains_table.add_row(
                f"... and {len(sorted_domains) - 10} more",
                ""
            )

        return Panel(
            domains_table,
            title="[bold]Domain Breakdown[/bold]",
            border_style="green"
        )

    def _create_activity_panel(self) -> Panel:
        """Create recent activity panel."""
        if not self.stats['recent_urls']:
            return Panel("Waiting for activity...", title="[bold]Recent Activity[/bold]")

        # Show last 5 URLs
        recent = self.stats['recent_urls'][-5:]

        activity_text = "\n".join([
            f"[dim]{i+1}.[/dim] {url}"
            for i, url in enumerate(reversed(recent))
        ])

        return Panel(
            activity_text,
            title="[bold]Recent URLs[/bold]",
            border_style="yellow"
        )

    async def run_with_dashboard(self, scrape_coroutine):
        """
        Run scraping with live dashboard.

        Usage:
            dashboard = LiveDashboard()
            result = await dashboard.run_with_dashboard(engine.run_job(job))
        """
        with Live(self.get_layout(), refresh_per_second=4, console=self.console) as live:
            # Run scraping
            result = await scrape_coroutine

            # Final update
            live.update(self.get_layout())

        return result


class PerformanceAnalyzer:
    """
    Analyze scraping performance and provide insights.
    """

    def __init__(self):
        self.metrics: List[Dict] = []

    def record_metric(
        self,
        url: str,
        response_time: float,
        bytes_downloaded: int,
        items_extracted: int,
        success: bool
    ):
        """Record a scraping metric."""
        self.metrics.append({
            'timestamp': datetime.utcnow(),
            'url': url,
            'response_time': response_time,
            'bytes': bytes_downloaded,
            'items': items_extracted,
            'success': success,
        })

    def generate_report(self) -> Dict:
        """Generate performance report."""
        if not self.metrics:
            return {}

        total_metrics = len(self.metrics)
        successful = sum(1 for m in self.metrics if m['success'])
        failed = total_metrics - successful

        avg_response_time = sum(m['response_time'] for m in self.metrics) / total_metrics
        total_bytes = sum(m['bytes'] for m in self.metrics)
        total_items = sum(m['items'] for m in self.metrics)

        # Find slowest and fastest
        slowest = max(self.metrics, key=lambda m: m['response_time'])
        fastest = min(self.metrics, key=lambda m: m['response_time'])

        # Time series analysis
        duration = (self.metrics[-1]['timestamp'] - self.metrics[0]['timestamp']).total_seconds()

        return {
            'summary': {
                'total_requests': total_metrics,
                'successful': successful,
                'failed': failed,
                'success_rate': successful / total_metrics * 100,
                'total_duration': duration,
            },
            'performance': {
                'avg_response_time': avg_response_time,
                'fastest_response': fastest['response_time'],
                'slowest_response': slowest['response_time'],
                'fastest_url': fastest['url'],
                'slowest_url': slowest['url'],
            },
            'throughput': {
                'total_bytes': total_bytes,
                'total_items': total_items,
                'avg_bytes_per_request': total_bytes / total_metrics,
                'avg_items_per_request': total_items / total_metrics,
                'requests_per_second': total_metrics / duration if duration > 0 else 0,
                'items_per_second': total_items / duration if duration > 0 else 0,
            },
            'recommendations': self._generate_recommendations(
                avg_response_time,
                successful,
                total_metrics
            ),
        }

    def _generate_recommendations(
        self,
        avg_response_time: float,
        successful: int,
        total: int
    ) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []

        success_rate = successful / total * 100

        if avg_response_time > 5.0:
            recommendations.append(
                "⚠ Average response time is high (>5s). Consider:\n"
                "  • Reducing max_concurrent_requests\n"
                "  • Increasing delays\n"
                "  • Using browser mode only when needed"
            )

        if success_rate < 90:
            recommendations.append(
                f"⚠ Success rate is low ({success_rate:.1f}%). Consider:\n"
                "  • Increasing retry attempts\n"
                "  • Adding delays between requests\n"
                "  • Checking selectors are correct"
            )

        if avg_response_time < 1.0 and success_rate > 95:
            recommendations.append(
                "✓ Performance is excellent! You might increase concurrency for faster scraping."
            )

        return recommendations

    def display_report(self, console: Console):
        """Display formatted performance report."""
        report = self.generate_report()

        if not report:
            console.print("[yellow]No metrics recorded yet[/yellow]")
            return

        # Summary panel
        summary = report['summary']
        summary_panel = Panel(
            f"Total Requests: {summary['total_requests']}\n"
            f"Successful: [green]{summary['successful']}[/green]\n"
            f"Failed: [red]{summary['failed']}[/red]\n"
            f"Success Rate: {summary['success_rate']:.1f}%\n"
            f"Duration: {summary['total_duration']:.2f}s",
            title="[bold]Summary[/bold]",
            border_style="cyan"
        )

        # Performance panel
        perf = report['performance']
        perf_panel = Panel(
            f"Avg Response Time: {perf['avg_response_time']:.2f}s\n"
            f"Fastest: {perf['fastest_response']:.2f}s ({perf['fastest_url']})\n"
            f"Slowest: {perf['slowest_response']:.2f}s ({perf['slowest_url']})",
            title="[bold]Performance[/bold]",
            border_style="green"
        )

        # Throughput panel
        throughput = report['throughput']
        throughput_panel = Panel(
            f"Total Items: {throughput['total_items']:,}\n"
            f"Total Data: {throughput['total_bytes'] / (1024*1024):.2f} MB\n"
            f"Requests/sec: {throughput['requests_per_second']:.2f}\n"
            f"Items/sec: {throughput['items_per_second']:.2f}",
            title="[bold]Throughput[/bold]",
            border_style="yellow"
        )

        # Display
        console.print("\n")
        console.print(summary_panel)
        console.print(perf_panel)
        console.print(throughput_panel)

        # Recommendations
        if report['recommendations']:
            console.print("\n[bold cyan]Recommendations:[/bold cyan]")
            for rec in report['recommendations']:
                console.print(f"  {rec}\n")
