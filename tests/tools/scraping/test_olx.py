import os
import types
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from bs4 import BeautifulSoup

from tools.scraping.types import ScraperType

OLX_LISTING_HTML = """
<html><body>
  <div data-testid="l-card">
    <p data-testid="location-date">Warszawa - Dzisiaj o 12:34</p>
    <div data-cy="ad-card-title"><a href="/oferta/1">Nice flat</a></div>
    <p data-testid="ad-price">1 500 zł</p>
    <div data-testid="image-container"><img src="http://img/1.jpg"/></div>
  </div>
  <div data-testid="l-card">
    <p data-testid="location-date">Warszawa - Dzisiaj o 01:00</p>
    <div data-cy="ad-card-title"><a href="/oferta/2">Old flat</a></div>
  </div>
</body></html>
"""

DETAIL_HTML = """
<html><body>
  <div data-cy="ad_description">Some long description</div>
  <img data-testid="swiper-image-1" srcset="http://a.jpg 200w, http://b.jpg 800w"/>
</body></html>
"""


class TestOLXScraper(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        os.environ.setdefault("TOPN_DB_BASE_URL", "http://api")
        os.environ.setdefault("GROQ_MODEL_NAME", "dummy")
        import sys

        sys.modules.setdefault(
            "langchain_groq",
            types.SimpleNamespace(
                ChatGroq=type("ChatGroq", (), {"__init__": lambda *a, **k: None})
            ),
        )

        from tools.scraping.olx import OLXScraper

        self.OLXScraper = OLXScraper

    async def asyncTearDown(self):
        pass

    async def test_fetch_new_items_filters_and_builds_items(self):
        # Mock httpx responses for list and details
        list_resp = MagicMock(status_code=200, text=OLX_LISTING_HTML)
        detail_resp = MagicMock(status_code=200, text=DETAIL_HTML)

        with patch(
            "httpx.AsyncClient.get", new=AsyncMock(side_effect=[list_resp, detail_resp])
        ):
            # Only the first card should be considered "recent"
            with patch(
                "tools.utils.time_helpers.TimeUtils.within_last_minutes",
                side_effect=[True, False],
            ):
                scr = self.OLXScraper()
                summarizer = types.SimpleNamespace(
                    summarize=AsyncMock(return_value="sum")
                )
                items = await scr.fetch_new_items(
                    "http://olx", existing_urls=set(), summarizer=summarizer
                )

        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it.title, "Nice flat")
        # Note: Summarizer is not yet implemented in OLXScraper (see TODO in fetch_item_details)
        # So we expect the raw description from the HTML
        self.assertIn("Some long description", it.description)
        self.assertTrue(it.item_url.startswith("https://www.olx.pl"))

    async def test_fetch_item_details_otodom_shortcut(self):
        # Mock the Otodom scraper's fetch_item_details method
        with patch(
            "tools.scraping.otodom.OtodomScraper.fetch_item_details"
        ) as mock_fetch:
            mock_fetch.return_value = (
                "Otodom property description",
                "http://otodom.img",
            )

            scr = self.OLXScraper()
            desc, img = await scr._fetch_item_details(
                "http://otodom.pl/123",
                summarizer=types.SimpleNamespace(summarize=AsyncMock()),
            )

            self.assertIn("Otodom", desc)
            self.assertEqual(img, "http://otodom.img")
            mock_fetch.assert_called_once()

    async def test_extract_helpers(self):
        scr = self.OLXScraper()
        soup = BeautifulSoup(DETAIL_HTML, "html.parser")
        img = scr._extract_highres_image(soup)
        self.assertEqual(img, "http://b.jpg")
        desc = scr._extract_description(soup)
        self.assertIn("Some long description", desc)

    async def test_parse_times(self):
        scr = self.OLXScraper()
        dt, pretty = scr._parse_times("12:00")
        self.assertIsNotNone(dt)
        self.assertIsInstance(pretty, str)

    async def test_fetch_new_items_skips_non_today_items(self):
        """Test that items without 'Dzisiaj' are skipped."""
        html_with_old = """
        <html><body>
          <div data-testid="l-card">
            <p data-testid="location-date">Warszawa - Wczoraj o 12:34</p>
            <div data-cy="ad-card-title"><a href="/oferta/1">Old item</a></div>
          </div>
        </body></html>
        """
        list_resp = MagicMock(status_code=200, text=html_with_old)

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=list_resp)):
            scr = self.OLXScraper()
            summarizer = types.SimpleNamespace(summarize=AsyncMock())
            items = await scr.fetch_new_items(
                "http://olx", existing_urls=set(), summarizer=summarizer
            )

        self.assertEqual(len(items), 0)

    async def test_fetch_new_items_skips_existing_urls(self):
        """Test that items with URLs in existing_urls are skipped."""
        list_resp = MagicMock(status_code=200, text=OLX_LISTING_HTML)

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=list_resp)):
            with patch(
                "tools.utils.time_helpers.TimeUtils.within_last_minutes",
                side_effect=[True, True],  # Both items pass time check
            ):
                scr = self.OLXScraper()
                summarizer = types.SimpleNamespace(summarize=AsyncMock())
                # Add both URLs to existing_urls so all items are skipped
                items = await scr.fetch_new_items(
                    "http://olx",
                    existing_urls={
                        "https://www.olx.pl/oferta/1",
                        "https://www.olx.pl/oferta/2",
                    },
                    summarizer=summarizer,
                )

        self.assertEqual(len(items), 0)

    async def test_fetch_new_items_normalizes_relative_urls(self):
        """Test that relative URLs are converted to absolute URLs."""
        html_relative = """
        <html><body>
          <div data-testid="l-card">
            <p data-testid="location-date">Warszawa - Dzisiaj o 12:34</p>
            <div data-cy="ad-card-title"><a href="/oferta/relative">Item</a></div>
            <p data-testid="ad-price">1000 zł</p>
          </div>
        </body></html>
        """
        list_resp = MagicMock(status_code=200, text=html_relative)
        detail_resp = MagicMock(status_code=200, text=DETAIL_HTML)

        with patch(
            "httpx.AsyncClient.get", new=AsyncMock(side_effect=[list_resp, detail_resp])
        ):
            with patch(
                "tools.utils.time_helpers.TimeUtils.within_last_minutes",
                return_value=True,
            ):
                scr = self.OLXScraper()
                summarizer = types.SimpleNamespace(summarize=AsyncMock())
                items = await scr.fetch_new_items(
                    "http://olx", existing_urls=set(), summarizer=summarizer
                )

        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].item_url.startswith("https://www.olx.pl"))
        self.assertIn("/oferta/relative", items[0].item_url)

    async def test_fetch_new_items_replaces_image_with_highres(self):
        """Test that highres image replaces thumbnail when available."""
        html_with_img = """
        <html><body>
          <div data-testid="l-card">
            <p data-testid="location-date">Warszawa - Dzisiaj o 12:34</p>
            <div data-cy="ad-card-title"><a href="http://olx.pl/item">Item</a></div>
            <div data-testid="image-container"><img src="http://thumbnail.jpg"/></div>
          </div>
        </body></html>
        """
        detail_with_highres = """
        <html><body>
          <div data-cy="ad_description">Description</div>
          <img data-testid="swiper-image-1" src="http://highres.jpg"/>
        </body></html>
        """
        list_resp = MagicMock(status_code=200, text=html_with_img)
        detail_resp = MagicMock(status_code=200, text=detail_with_highres)

        with patch(
            "httpx.AsyncClient.get", new=AsyncMock(side_effect=[list_resp, detail_resp])
        ):
            with patch(
                "tools.utils.time_helpers.TimeUtils.within_last_minutes",
                return_value=True,
            ):
                scr = self.OLXScraper()
                summarizer = types.SimpleNamespace(summarize=AsyncMock())
                items = await scr.fetch_new_items(
                    "http://olx", existing_urls=set(), summarizer=summarizer
                )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].image_url, "http://highres.jpg")

    async def test_get_detail_fetcher_lazy_loads_scrapers(self):
        """Test that detail fetchers are lazy-loaded and cached."""
        scr = self.OLXScraper()

        # First call should create the scraper
        with patch("tools.scraping.olx.get_scraper_registry") as mock_registry:
            mock_otodom_class = MagicMock()
            mock_otodom_instance = MagicMock()
            mock_otodom_class.return_value = mock_otodom_instance
            mock_registry.return_value = {ScraperType.OTODOM: mock_otodom_class}

            fetcher1 = scr._get_detail_fetcher(ScraperType.OTODOM)

            # Second call should return cached instance
            fetcher2 = scr._get_detail_fetcher(ScraperType.OTODOM)

            # Should be the same instance
            self.assertIs(fetcher1, fetcher2)
            # Should only instantiate the scraper once (cached on second call)
            mock_otodom_class.assert_called_once()

    async def test_close_closes_delegated_scrapers(self):
        """Test that close() closes all delegated scrapers."""
        scr = self.OLXScraper()

        # Create a mock delegated scraper
        mock_delegated = MagicMock()
        mock_delegated.close = AsyncMock()
        scr._detail_fetchers[ScraperType.OTODOM] = mock_delegated

        with patch.object(scr.client, "aclose", new=AsyncMock()) as mock_client_close:
            await scr.close()

            # Verify client was closed
            mock_client_close.assert_awaited_once()
            # Verify delegated scraper was closed
            mock_delegated.close.assert_awaited_once()

    async def test_extract_highres_image_handles_missing_tag(self):
        """Test _extract_highres_image returns empty string when img tag is missing."""
        html_no_img = "<html><body><div>No image here</div></body></html>"
        soup = BeautifulSoup(html_no_img, "html.parser")

        scr = self.OLXScraper()
        result = scr._extract_highres_image(soup)

        self.assertEqual(result, "")

    async def test_extract_highres_image_prefers_src_attribute(self):
        """Test _extract_highres_image prefers src over srcset."""
        html_with_src = """
        <html><body>
          <img data-testid="swiper-image-1" src="http://direct.jpg" 
               srcset="http://a.jpg 200w, http://b.jpg 800w"/>
        </body></html>
        """
        soup = BeautifulSoup(html_with_src, "html.parser")

        scr = self.OLXScraper()
        result = scr._extract_highres_image(soup)

        self.assertEqual(result, "http://direct.jpg")

    async def test_extract_highres_image_handles_invalid_srcset(self):
        """Test _extract_highres_image handles malformed srcset gracefully."""
        html_bad_srcset = """
        <html><body>
          <img data-testid="swiper-image-1" srcset="invalid format, http://good.jpg 800w"/>
        </body></html>
        """
        soup = BeautifulSoup(html_bad_srcset, "html.parser")

        scr = self.OLXScraper()
        result = scr._extract_highres_image(soup)

        # Should return the valid one
        self.assertEqual(result, "http://good.jpg")

    async def test_extract_highres_image_handles_exception(self):
        """Test _extract_highres_image returns empty string on exception."""
        # Create a soup that will cause an exception
        soup = MagicMock()
        soup.find.side_effect = Exception("Test exception")

        scr = self.OLXScraper()
        result = scr._extract_highres_image(soup)

        self.assertEqual(result, "")

    async def test_extract_highres_image_returns_empty_for_empty_srcset(self):
        """Test _extract_highres_image returns empty string when srcset is empty."""
        html_empty_srcset = """
        <html><body>
          <img data-testid="swiper-image-1" srcset=""/>
        </body></html>
        """
        soup = BeautifulSoup(html_empty_srcset, "html.parser")

        scr = self.OLXScraper()
        result = scr._extract_highres_image(soup)

        self.assertEqual(result, "")
