"""Scraping module with marketplace-specific scrapers."""

from .base import BaseScraper
from .types import ScraperType, get_proper_scraper, get_scraper_registry


# For backward compatibility, provide SCRAPER_REGISTRY as a function call
# This avoids circular import issues
def _get_registry():
    """Lazy-load the scraper registry."""
    return get_scraper_registry()


# Note: SCRAPER_REGISTRY is now a function call to avoid circular imports
# Use get_scraper_registry() instead, or call SCRAPER_REGISTRY() if you need the dict
SCRAPER_REGISTRY = _get_registry
