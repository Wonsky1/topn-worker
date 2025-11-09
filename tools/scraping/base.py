"""Abstract base class for all scrapers.

Allows us to plug additional marketplaces in the future simply by
subclassing `BaseScraper` and implementing the abstract methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Set

from models import Item
from tools.processing.description import (  # noqa: F401 pylint: disable=cyclic-import
    DescriptionSummarizer,
)


class BaseScraper(ABC):
    """Interface that every marketplace‐specific scraper must implement."""

    HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "X-Forwarded-For": "83.0.0.0",
        "CF-IPCountry": "PL",
    }

    @abstractmethod
    async def fetch_new_items(
        self,
        url: str,
        existing_urls: Set[str],
        summarizer: "DescriptionSummarizer",
    ) -> List[Item]:
        """Return a list of *new* `Item` objects collected from *url*.

        Args:
            url: Marketplace search / listing URL.
            existing_urls: A set of already processed item URLs (deduplication).
            summarizer: Helper used to summarise raw item descriptions.
        """

    @abstractmethod
    async def fetch_item_details(
        self, item_url: str, summarizer: "DescriptionSummarizer"
    ) -> tuple[str, str]:
        """Fetch description and high-resolution image for a single item.

        Args:
            item_url: URL of the specific item listing.
            summarizer: Helper used to summarise raw item descriptions.

        Returns:
            tuple[description, highres_image_url]
        """

    async def close(self):  # pragma: no cover
        """Override if the scraper keeps any open connections / sessions."""
        return None
