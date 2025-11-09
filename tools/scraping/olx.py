"""Scraper implementation for OLX marketplace listings."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Dict, List, Set

import httpx
import pytz
from bs4 import BeautifulSoup

from models import Item
from tools.processing.description import DescriptionSummarizer
from tools.utils.time_helpers import TimeUtils

from .base import BaseScraper
from .types import ScraperType, get_proper_scraper, get_scraper_registry

logger = logging.getLogger(__name__)


class OLXScraper(BaseScraper):
    """OLX marketplace scraper.

    Designed to reproduce the original behaviour previously located in
    `tools.utils.get_new_items` and `tools.utils.get_item_description`.
    """

    HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "pl-PL,pl;q=0.9,en-GB;q=0.8,en;q=0.7",
        "Cache-Control": "max-age=0",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "X-Forwarded-For": "83.0.0.0",  # Polish IP range to get Polish timezone
        "CF-IPCountry": "PL",
    }

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            headers=self.HEADERS, timeout=10, follow_redirects=True
        )
        self._detail_fetchers: Dict[ScraperType, BaseScraper] = {}

    async def fetch_new_items(
        self,
        url: str,
        existing_urls: Set[str],
        summarizer: DescriptionSummarizer,
    ) -> List[Item]:
        logger.info("Fetching OLX items from %s", url)

        response = await self.client.get(url)
        logger.debug("OLX response status code: %s", response.status_code)
        soup = BeautifulSoup(response.text, "html.parser")
        divs = soup.find_all("div", attrs={"data-testid": "l-card"})

        new_items: List[Item] = []
        skipped_count = 0
        for div in divs:
            location_date = div.find(
                "p", attrs={"data-testid": "location-date"}
            ).get_text(strip=True)
            if "Dzisiaj" not in location_date:
                logger.debug("Skipping non-today item: %s", location_date)
                continue

            location, time_str = location_date.split("Dzisiaj o ")
            location = location.strip().rstrip("-").strip()

            if not TimeUtils.within_last_minutes(time_str):
                logger.debug("Skipping old item at %s", time_str)
                continue

            title_div = div.find("div", attrs={"data-cy": "ad-card-title"})
            a_tag = title_div.find("a")
            item_url = a_tag["href"]
            if not item_url.startswith("http"):
                item_url = "https://www.olx.pl" + item_url

            if item_url in existing_urls:
                skipped_count += 1
                continue

            title = a_tag.get_text(strip=True)

            price_div = div.find("p", attrs={"data-testid": "ad-price"})
            price = price_div.get_text(strip=True) if price_div else "Brak ceny"

            image_div = div.find("div", attrs={"data-testid": "image-container"})
            image_url = image_div.find("img")["src"] if image_div else ""

            description, highres = await self._fetch_item_details(item_url, summarizer)
            if highres:
                image_url = highres

            created_at, created_at_pretty = self._parse_times(time_str)

            new_items.append(
                Item(
                    title=title,
                    price=price,
                    location=location,
                    created_at=created_at,
                    created_at_pretty=created_at_pretty,
                    image_url=image_url,
                    item_url=item_url,
                    description=description,
                )
            )

        logger.info(
            "OLX scraper found %s new items, skipped %s existing",
            len(new_items),
            skipped_count,
        )
        return new_items

    def _get_detail_fetcher(self, scraper_type: ScraperType) -> BaseScraper:
        """Lazy-load detail fetchers on demand.

        Args:
            scraper_type: Type of scraper to get.

        Returns:
            Instance of the requested scraper.
        """
        if scraper_type not in self._detail_fetchers:
            # Get registry and instantiate the appropriate scraper
            registry = get_scraper_registry()
            scraper_cls = registry[scraper_type]
            self._detail_fetchers[scraper_type] = scraper_cls()
        return self._detail_fetchers[scraper_type]

    async def _fetch_item_details(
        self, item_url: str, summarizer: DescriptionSummarizer
    ):
        """Internal method to fetch item details with delegation support."""
        scraper_type = get_proper_scraper(item_url)

        if scraper_type != ScraperType.OLX:
            # Delegate to appropriate scraper
            fetcher = self._get_detail_fetcher(scraper_type)
            return await fetcher.fetch_item_details(item_url, summarizer)

        # Use OLX-specific implementation
        return await self.fetch_item_details(item_url, summarizer)

    async def fetch_item_details(
        self, item_url: str, summarizer: DescriptionSummarizer
    ) -> tuple[str, str]:
        """Fetch description and image for a single OLX item.

        This implements the BaseScraper abstract method for OLX-specific logic.

        Args:
            item_url: URL of the OLX listing.
            summarizer: Description summarizer (currently unused, TODO).

        Returns:
            tuple[description, highres_image_url]
        """
        try:
            response = await self.client.get(item_url)
            soup = BeautifulSoup(response.text, "html.parser")

            raw_desc = self._extract_description(soup)
            # TODO: implement description summarization later
            # summary = await summarizer.summarize(raw_desc)
            # description = summary or raw_desc[:500]
            description = raw_desc[:500]

            highres = self._extract_highres_image(soup)
            return description, highres
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to load details for %s: %s", item_url, exc)
            return f"Failed to load description: {exc}", ""

    @staticmethod
    def _extract_highres_image(soup: BeautifulSoup) -> str:
        """Return highest-quality image URL from item detail page if present."""
        try:
            img_tag = soup.find(
                "img", attrs={"data-testid": re.compile(r"^swiper-image")}
            )
            if not img_tag:
                return ""
            if img_tag.get("src"):
                return img_tag["src"]
            srcset = img_tag.get("srcset", "")
            if srcset:
                variants = [v.strip() for v in srcset.split(",")]
                best_url = ""
                best_w = 0
                for variant in variants:
                    try:
                        url_part, size_part = variant.split(" ")
                        width = int(size_part.rstrip("w"))
                        if width > best_w:
                            best_w = width
                            best_url = url_part
                    except ValueError:
                        continue
                return best_url
            return ""
        except Exception:
            return ""

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str:
        description_tag = soup.find("div", attrs={"data-cy": "ad_description"})
        return description_tag.get_text(strip=True) if description_tag else ""

    @staticmethod
    def _parse_times(time_str: str):
        parsed_time = datetime.strptime(time_str, "%H:%M").time()
        utc_tz = pytz.UTC
        now_utc = datetime.now(utc_tz)
        datetime_provided_utc = utc_tz.localize(
            datetime.combine(now_utc.date(), parsed_time)
        )
        poland_tz = pytz.timezone("Europe/Warsaw")
        datetime_provided_pl = datetime_provided_utc.astimezone(poland_tz)
        datetime_naive_pl = datetime_provided_pl.replace(tzinfo=None)
        created_at_pretty = datetime_provided_pl.strftime("%d.%m.%Y - *%H:%M*")
        return datetime_naive_pl, created_at_pretty

    async def close(self):
        await self.client.aclose()
        # Close all delegated scrapers
        for fetcher in self._detail_fetchers.values():
            await fetcher.close()
        await super().close()
