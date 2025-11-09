import os
import types
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch


class TestItemMonitor(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        os.environ.setdefault("TOPN_DB_BASE_URL", "http://api")
        os.environ.setdefault("GROQ_MODEL_NAME", "dummy")
        import sys

        # Stub langchain_groq to let core.config import succeed
        sys.modules.setdefault(
            "langchain_groq",
            types.SimpleNamespace(
                ChatGroq=type("ChatGroq", (), {"__init__": lambda *a, **k: None})
            ),
        )

        # Import after stubs are ready
        from models import Item
        from tools.monitoring.monitor import ItemMonitor

        self.Item = Item
        self.ItemMonitor = ItemMonitor

        # Fake db client with async methods
        self.db = AsyncMock()
        self.db.get_all_tasks.return_value = {
            "tasks": [
                {"url": "https://u1"},
                {"url": "https://u1"},  # duplicate to check distinct
                {"url": "https://u2"},
            ]
        }
        self.db.get_items_by_source_url.return_value = {
            "items": [{"item_url": "https://old"}]
        }
        self.db.create_item = AsyncMock()

        # Fake scraper class
        class FakeScraper:
            def __init__(self):
                self.closed = False

            async def fetch_new_items(self, url, existing_urls, summarizer):
                # return two new items per URL, one old filtered
                return [
                    self.Item(
                        title=f"t-{url}",
                        price="p",
                        image_url="i",
                        created_at=None,
                        location="l",
                        item_url=f"{url}/new1",
                        description="d",
                        created_at_pretty="cp",
                    ),
                    self.Item(
                        title=f"t2-{url}",
                        price="p2",
                        image_url="i2",
                        created_at=None,
                        location="l2",
                        item_url=f"{url}/new2",
                        description="d2",
                        created_at_pretty="cp2",
                    ),
                ]

            async def close(self):
                self.closed = True

        # Bind Item on class for closure
        FakeScraper.Item = self.Item

        self.monitor = ItemMonitor(
            db_client=self.db, scraper_cls=FakeScraper, cycle_sleep_seconds=0
        )

    async def asyncTearDown(self):
        await self.monitor.close()

    async def test_run_once_persists_items_and_sleeps_between(self):
        with patch("tools.monitoring.monitor.asyncio.sleep", new=AsyncMock()) as sl:
            await self.monitor.run_once()
        # Called for two distinct URLs
        self.assertGreaterEqual(self.db.create_item.await_count, 4)
        sl.assert_awaited()

    async def test_persist_items_sets_source_field(self):
        # Build items with various urls
        items = [
            self.Item(
                title="a",
                price="",
                image_url="",
                created_at=None,
                location="",
                item_url="https://otodom.pl/x",
                description="",
                created_at_pretty="",
            ),
            self.Item(
                title="b",
                price="",
                image_url="",
                created_at=None,
                location="",
                item_url="https://www.olx.pl/y",
                description="",
                created_at_pretty="",
            ),
            self.Item(
                title="c",
                price="",
                image_url="",
                created_at=None,
                location="",
                item_url="https://example.com/z",
                description="",
                created_at_pretty="",
            ),
        ]
        await self.monitor._persist_items(items, source_url="SRC")
        # Extract payloads from awaited calls (positional or kw)
        payloads = [
            call.args[0] if call.args else call.kwargs["item_data"]
            for call in self.db.create_item.await_args_list
        ]
        self.assertEqual(
            [p["source"] for p in payloads], ["OTODOM", "OLX", "OLX"]
        )  # default fallback is OLX
        self.assertEqual([p["source_url"] for p in payloads], ["SRC", "SRC", "SRC"])

    async def test_run_once_handles_fetch_errors_and_continues(self):
        # Make get_items_by_source_url raise for first url only
        self.db.get_items_by_source_url.side_effect = [
            RuntimeError("boom"),
            {"items": []},
        ]
        with patch("tools.monitoring.monitor.asyncio.sleep", new=AsyncMock()):
            await self.monitor.run_once()
        # Should still attempt second url, so not zero persisting calls
        self.assertGreaterEqual(self.db.create_item.await_count, 1)

    async def test_run_once_raises_on_outer_error(self):
        self.db.get_all_tasks.side_effect = RuntimeError("fatal")
        with self.assertRaises(RuntimeError):
            await self.monitor.run_once()

    async def test_close_delegates_to_scraper(self):
        scr = self.monitor.scraper
        await self.monitor.close()
        self.assertTrue(getattr(scr, "closed", False))
