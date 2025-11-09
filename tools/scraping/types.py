"""Scraper types and routing utilities."""

from __future__ import annotations

from enum import StrEnum
from urllib.parse import urlparse


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
