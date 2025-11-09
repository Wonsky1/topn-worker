"""Scraper implementation for Otodom marketplace listings."""

from __future__ import annotations

import html
import json
import logging
from typing import List, Set, Tuple

import httpx
from bs4 import BeautifulSoup

from models import Item
from tools.processing.description import DescriptionSummarizer

from .base import BaseScraper

logger = logging.getLogger(__name__)


class OtodomScraper(BaseScraper):
    """Scraper for Otodom.pl listings (property marketplace)."""

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            headers=self.HEADERS, timeout=10, follow_redirects=True
        )

    async def fetch_new_items(
        self,
        url: str,
        existing_urls: Set[str],
        summarizer: DescriptionSummarizer,
    ) -> List[Item]:
        """Placeholder: Otodom listing discovery not implemented."""
        logger.warning("Otodom listing page scraping not yet implemented for: %s", url)
        return []

    async def fetch_item_details(
        self, item_url: str, summarizer: DescriptionSummarizer
    ) -> Tuple[str, str]:
        """Fetch description and image URL from a single Otodom listing."""
        try:
            response = await self.client.get(item_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            raw_desc, highres = self._extract_from_next_data(soup)

            # TODO: implement summarizer
            # description = summarizer.summarize(raw_desc) if raw_desc else "No description available"

            return raw_desc, highres

        except Exception as exc:
            logger.exception("Failed to load Otodom details for %s: %s", item_url, exc)
            return f"Failed to load description: {exc}", ""

    # ---- Extraction helpers ----

    @staticmethod
    def _extract_from_next_data(soup: BeautifulSoup) -> Tuple[str, str]:
        """Extract description and image from the __NEXT_DATA__ JSON."""
        script_tag = soup.find("script", id="__NEXT_DATA__")
        if not script_tag or not script_tag.string:
            return "", ""

        try:
            data = json.loads(script_tag.string)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in __NEXT_DATA__")
            return "", ""

        # Traverse to the ad object
        ad = data.get("props", {}).get("pageProps", {}).get("ad", {})

        # --- Description ---
        description_html = ad.get("description", "")
        description_html = html.unescape(description_html)
        description_text = BeautifulSoup(description_html, "html.parser").get_text(
            separator="\n", strip=True
        )

        # --- High-res Image ---
        highres = ""
        images = ad.get("images") or ad.get("photos") or []
        if isinstance(images, list) and images:
            # Try "large" first, fallback to first available
            for img in images:
                for key in ("large", "medium", "link", "url"):
                    if key in img and isinstance(img[key], str):
                        highres = img[key]
                        break
                if highres:
                    break

        return description_text, highres

    async def close(self):
        await self.client.aclose()
        await super().close()
