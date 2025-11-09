from unittest import IsolatedAsyncioTestCase

from tools.scraping.base import BaseScraper


class DummyScraper(BaseScraper):
    async def fetch_new_items(self, url, existing_urls, summarizer):  # pragma: no cover
        return []

    async def fetch_item_details(self, item_url, summarizer):  # pragma: no cover
        return "", ""


class TestBaseScraper(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.scraper = DummyScraper()

    async def asyncTearDown(self):
        pass

    async def test_close_returns_none(self):
        res = await self.scraper.close()
        self.assertIsNone(res)
