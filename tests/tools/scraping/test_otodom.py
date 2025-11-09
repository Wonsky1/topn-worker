import json
import os
import types
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

# Sample Otodom __NEXT_DATA__ JSON structure
OTODOM_NEXT_DATA_JSON = {
    "props": {
        "pageProps": {
            "ad": {
                "description": "<p>Beautiful apartment in the city center.</p><p>Newly renovated with modern amenities.</p>",
                "images": [
                    {
                        "large": "http://otodom.img/large1.jpg",
                        "medium": "http://otodom.img/medium1.jpg",
                    },
                    {
                        "large": "http://otodom.img/large2.jpg",
                        "medium": "http://otodom.img/medium2.jpg",
                    },
                ],
                "title": "Luxury Apartment",
                "price": {"value": 500000, "currency": "PLN"},
            }
        }
    }
}

# Alternative structure with "photos" instead of "images"
OTODOM_NEXT_DATA_PHOTOS_JSON = {
    "props": {
        "pageProps": {
            "ad": {
                "description": "Simple description text",
                "photos": [
                    {"url": "http://otodom.img/photo1.jpg"},
                    {"link": "http://otodom.img/photo2.jpg"},
                ],
            }
        }
    }
}

# Empty/missing data scenarios
OTODOM_NEXT_DATA_EMPTY = {"props": {"pageProps": {"ad": {}}}}

OTODOM_DETAIL_HTML_TEMPLATE = """
<html>
<head>
    <script id="__NEXT_DATA__" type="application/json">{json_data}</script>
</head>
<body>
    <div>Otodom property page</div>
</body>
</html>
"""


class TestOtodomScraper(IsolatedAsyncioTestCase):
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

        from tools.scraping.otodom import OtodomScraper

        self.OtodomScraper = OtodomScraper

    async def asyncTearDown(self):
        pass

    async def test_fetch_new_items_returns_empty_with_warning(self):
        """Test that fetch_new_items returns empty list (not yet implemented)."""
        scr = self.OtodomScraper()
        summarizer = types.SimpleNamespace(summarize=AsyncMock(return_value="sum"))

        with patch("tools.scraping.otodom.logger") as mock_logger:
            items = await scr.fetch_new_items(
                "http://otodom.pl/search", existing_urls=set(), summarizer=summarizer
            )

        self.assertEqual(items, [])
        mock_logger.warning.assert_called_once()
        self.assertIn("not yet implemented", mock_logger.warning.call_args[0][0])

    async def test_fetch_item_details_extracts_description_and_image(self):
        """Test successful extraction of description and image from __NEXT_DATA__."""
        html_content = OTODOM_DETAIL_HTML_TEMPLATE.format(
            json_data=json.dumps(OTODOM_NEXT_DATA_JSON)
        )
        mock_response = MagicMock(status_code=200, text=html_content)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            scr = self.OtodomScraper()
            summarizer = types.SimpleNamespace(summarize=AsyncMock())
            desc, img = await scr.fetch_item_details(
                "http://otodom.pl/property/123", summarizer
            )

        self.assertIn("Beautiful apartment", desc)
        self.assertIn("Newly renovated", desc)
        self.assertEqual(img, "http://otodom.img/large1.jpg")

    async def test_fetch_item_details_handles_photos_field(self):
        """Test extraction when 'photos' field is used instead of 'images'."""
        html_content = OTODOM_DETAIL_HTML_TEMPLATE.format(
            json_data=json.dumps(OTODOM_NEXT_DATA_PHOTOS_JSON)
        )
        mock_response = MagicMock(status_code=200, text=html_content)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            scr = self.OtodomScraper()
            summarizer = types.SimpleNamespace(summarize=AsyncMock())
            desc, img = await scr.fetch_item_details(
                "http://otodom.pl/property/456", summarizer
            )

        self.assertEqual(desc, "Simple description text")
        self.assertEqual(img, "http://otodom.img/photo1.jpg")

    async def test_fetch_item_details_handles_empty_data(self):
        """Test handling of empty/missing data in __NEXT_DATA__."""
        html_content = OTODOM_DETAIL_HTML_TEMPLATE.format(
            json_data=json.dumps(OTODOM_NEXT_DATA_EMPTY)
        )
        mock_response = MagicMock(status_code=200, text=html_content)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            scr = self.OtodomScraper()
            summarizer = types.SimpleNamespace(summarize=AsyncMock())
            desc, img = await scr.fetch_item_details(
                "http://otodom.pl/property/789", summarizer
            )

        self.assertEqual(desc, "")
        self.assertEqual(img, "")

    async def test_fetch_item_details_handles_missing_script_tag(self):
        """Test handling when __NEXT_DATA__ script tag is missing."""
        html_content = "<html><body>No script tag here</body></html>"
        mock_response = MagicMock(status_code=200, text=html_content)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            scr = self.OtodomScraper()
            summarizer = types.SimpleNamespace(summarize=AsyncMock())
            desc, img = await scr.fetch_item_details(
                "http://otodom.pl/property/999", summarizer
            )

        self.assertEqual(desc, "")
        self.assertEqual(img, "")

    async def test_fetch_item_details_handles_invalid_json(self):
        """Test handling of invalid JSON in __NEXT_DATA__."""
        html_content = """
        <html>
        <head>
            <script id="__NEXT_DATA__" type="application/json">invalid json{</script>
        </head>
        </html>
        """
        mock_response = MagicMock(status_code=200, text=html_content)
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            with patch("tools.scraping.otodom.logger") as mock_logger:
                scr = self.OtodomScraper()
                summarizer = types.SimpleNamespace(summarize=AsyncMock())
                desc, img = await scr.fetch_item_details(
                    "http://otodom.pl/property/invalid", summarizer
                )

        self.assertEqual(desc, "")
        self.assertEqual(img, "")
        mock_logger.warning.assert_called_once()
        self.assertIn("Invalid JSON", mock_logger.warning.call_args[0][0])

    async def test_fetch_item_details_handles_http_error(self):
        """Test error handling when HTTP request fails."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")

        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            with patch("tools.scraping.otodom.logger") as mock_logger:
                scr = self.OtodomScraper()
                summarizer = types.SimpleNamespace(summarize=AsyncMock())
                desc, img = await scr.fetch_item_details(
                    "http://otodom.pl/property/notfound", summarizer
                )

        self.assertIn("Failed to load description", desc)
        self.assertEqual(img, "")
        mock_logger.exception.assert_called_once()

    async def test_extract_from_next_data_with_html_entities(self):
        """Test that HTML entities in description are properly unescaped."""
        from bs4 import BeautifulSoup

        json_data = {
            "props": {
                "pageProps": {
                    "ad": {
                        "description": "&lt;p&gt;Test &amp; description&lt;/p&gt;",
                    }
                }
            }
        }
        html_content = OTODOM_DETAIL_HTML_TEMPLATE.format(
            json_data=json.dumps(json_data)
        )
        soup = BeautifulSoup(html_content, "html.parser")

        scr = self.OtodomScraper()
        desc, img = scr._extract_from_next_data(soup)

        self.assertIn("Test & description", desc)
        self.assertNotIn("&lt;", desc)
        self.assertNotIn("&gt;", desc)

    async def test_extract_from_next_data_image_priority(self):
        """Test that 'large' image is preferred over other sizes."""
        from bs4 import BeautifulSoup

        json_data = {
            "props": {
                "pageProps": {
                    "ad": {
                        "description": "Test",
                        "images": [
                            {
                                "medium": "http://medium.jpg",
                                "large": "http://large.jpg",
                                "url": "http://url.jpg",
                            }
                        ],
                    }
                }
            }
        }
        html_content = OTODOM_DETAIL_HTML_TEMPLATE.format(
            json_data=json.dumps(json_data)
        )
        soup = BeautifulSoup(html_content, "html.parser")

        scr = self.OtodomScraper()
        desc, img = scr._extract_from_next_data(soup)

        self.assertEqual(img, "http://large.jpg")

    async def test_extract_from_next_data_fallback_to_medium(self):
        """Test fallback to 'medium' when 'large' is not available."""
        from bs4 import BeautifulSoup

        json_data = {
            "props": {
                "pageProps": {
                    "ad": {
                        "description": "Test",
                        "images": [
                            {
                                "medium": "http://medium.jpg",
                                "url": "http://url.jpg",
                            }
                        ],
                    }
                }
            }
        }
        html_content = OTODOM_DETAIL_HTML_TEMPLATE.format(
            json_data=json.dumps(json_data)
        )
        soup = BeautifulSoup(html_content, "html.parser")

        scr = self.OtodomScraper()
        desc, img = scr._extract_from_next_data(soup)

        self.assertEqual(img, "http://medium.jpg")

    async def test_extract_from_next_data_handles_non_string_image_values(self):
        """Test that non-string image values are skipped."""
        from bs4 import BeautifulSoup

        json_data = {
            "props": {
                "pageProps": {
                    "ad": {
                        "description": "Test",
                        "images": [
                            {"large": None, "medium": 123, "url": "http://valid.jpg"}
                        ],
                    }
                }
            }
        }
        html_content = OTODOM_DETAIL_HTML_TEMPLATE.format(
            json_data=json.dumps(json_data)
        )
        soup = BeautifulSoup(html_content, "html.parser")

        scr = self.OtodomScraper()
        desc, img = scr._extract_from_next_data(soup)

        self.assertEqual(img, "http://valid.jpg")

    async def test_close_closes_client(self):
        """Test that close method properly closes the httpx client."""
        scr = self.OtodomScraper()

        with patch.object(scr.client, "aclose", new=AsyncMock()) as mock_close:
            await scr.close()
            mock_close.assert_awaited_once()
