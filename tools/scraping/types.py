"""Scraper types and routing utilities."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Dict, Type
from urllib.parse import urlparse

if TYPE_CHECKING:
    from .base import BaseScraper


class ScraperType(StrEnum):
    """Enumeration of available scraper types."""

    OLX = "olx"
    OTODOM = "otodom"


def get_proper_scraper(url: str) -> ScraperType:
    """Determine which scraper to use based on URL domain.

    Args:
        url: The URL to analyze (can be item URL or search URL).

    Returns:
        ScraperType enum value indicating which scraper should handle this URL.
    """
    domain = urlparse(url).netloc.lower()

    if "otodom" in domain:
        return ScraperType.OTODOM
    elif "olx" in domain:
        return ScraperType.OLX
    else:
        # Default fallback to OLX
        return ScraperType.OLX


def get_scraper_registry() -> Dict[ScraperType, Type["BaseScraper"]]:
    """Get the scraper registry with lazy imports to avoid circular dependencies.

    Returns:
        Dictionary mapping ScraperType to scraper implementation classes.
    """
    # Import here to avoid circular imports
    from .olx import OLXScraper
    from .otodom import OtodomScraper

    return {
        ScraperType.OLX: OLXScraper,
        ScraperType.OTODOM: OtodomScraper,
    }
