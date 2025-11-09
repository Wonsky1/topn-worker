"""High-level orchestrator that periodically scrapes items and persists them.

This is a refactor of the original `tools.utils.find_new_items` function.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

import pytz

from models import Item
from tools.processing.description import DescriptionSummarizer
from tools.scraping.base import BaseScraper
from tools.scraping.types import get_proper_scraper

if TYPE_CHECKING:
    from clients.topn_db_client import TopnDbClient

logger = logging.getLogger(__name__)


class ItemMonitor:
    """Periodically checks all `MonitoringTask` URLs using the provided scraper."""

    def __init__(
        self,
        db_client: "TopnDbClient",
        scraper_cls: type[BaseScraper],
        cycle_sleep_seconds: int = 3,
    ) -> None:
        self.db_client = db_client
        self.scraper: BaseScraper = scraper_cls()
        self.summarizer = DescriptionSummarizer()
        self.cycle_sleep_seconds = cycle_sleep_seconds

    async def run_once(self):
        """Scrape each task URL once and persist new items."""
        try:
            # Get all tasks from the API
            tasks_response = await self.db_client.get_all_tasks()
            tasks = tasks_response.get("tasks", [])

            # Extract distinct URLs
            distinct_urls = list({task["url"] for task in tasks})
            logger.info(
                "ItemMonitor starting scraping loop for %s URLs", len(distinct_urls)
            )

            for url in distinct_urls:
                try:
                    # Get existing items for this source URL
                    items_response = await self.db_client.get_items_by_source_url(
                        url, limit=10000
                    )
                    existing_items = items_response.get("items", [])
                    existing_urls = {item["item_url"] for item in existing_items}

                    new_items = await self.scraper.fetch_new_items(
                        url=url,
                        existing_urls=existing_urls,
                        summarizer=self.summarizer,
                    )
                except Exception as exc:
                    logger.error(
                        "Failed fetching items for %s: %s", url, exc, exc_info=True
                    )
                    continue

                await self._persist_items(new_items, source_url=url)
                logger.info("URL %s processed; added %s new items", url, len(new_items))

                await asyncio.sleep(self.cycle_sleep_seconds)

            logger.info("ItemMonitor finished all URLs")
        except Exception as exc:
            logger.error("Error in run_once: %s", exc, exc_info=True)
            raise

    async def _persist_items(self, items: list[Item], source_url: str):
        poland_tz = pytz.timezone("Europe/Warsaw")
        for item in items:
            # Use enum-based scraper detection for source
            scraper_type = get_proper_scraper(item.item_url)
            source = (
                scraper_type.value.upper()
            )  # Convert "olx" -> "OLX", "otodom" -> "OTODOM"

            item_data = {
                "item_url": item.item_url,
                "title": item.title,
                "price": item.price,
                "location": item.location,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "created_at_pretty": item.created_at_pretty,
                "image_url": item.image_url,
                "description": item.description,
                "source_url": source_url,
                "source": source,
                "first_seen": datetime.now(poland_tz).replace(tzinfo=None).isoformat(),
            }
            try:
                await self.db_client.create_item(item_data)
                logger.info("New item persisted: %s | %s", item.title, item.item_url)
            except Exception as exc:
                logger.error(
                    "Failed to persist item %s: %s", item.item_url, exc, exc_info=True
                )

    async def close(self):
        await self.scraper.close()
