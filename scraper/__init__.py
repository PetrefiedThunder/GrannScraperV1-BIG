"""
GrandmaScrape Intelligence Platform

Enterprise-grade web scraping made grandma-simple.
"""

__version__ = "0.1.0"
__author__ = "GrannScraper Team"

from scraper.config.models import ScrapeJob, FieldConfig, Workflow
from scraper.core.engine import ScraperEngine

__all__ = ["ScrapeJob", "FieldConfig", "Workflow", "ScraperEngine", "__version__"]
