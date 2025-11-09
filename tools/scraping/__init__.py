"""Scraping module with marketplace-specific scrapers."""

from typing import Dict, Type

from .base import BaseScraper
from .olx import OLXScraper
from .otodom import OtodomScraper
from .types import ScraperType, get_proper_scraper

# Registry mapping scraper types to their implementation classes
SCRAPER_REGISTRY: Dict[ScraperType, Type[BaseScraper]] = {
    ScraperType.OLX: OLXScraper,
    ScraperType.OTODOM: OtodomScraper,
}
