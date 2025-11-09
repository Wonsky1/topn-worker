import asyncio
import logging

from clients import close_client, topn_db_client
from core.config import settings
from core.logging_config import setup_logging
from tools.monitoring.monitor import ItemMonitor
from tools.scraping.olx import OLXScraper

# Initialize logging system
setup_logging(
    log_level=settings.LOG_LEVEL,
    log_filename="topn_worker.log",
    rotation_when="midnight",
    rotation_interval=1,
    backup_count=30,
    console_output=True,
)

logger = logging.getLogger(__name__)


async def worker_main():
    monitor = ItemMonitor(db_client=topn_db_client, scraper_cls=OLXScraper)
    try:
        while True:
            try:
                logger.info("Starting new item search cycle")
                await monitor.run_once()
            except Exception as e:
                logger.error(f"Error in item finder: {e}", exc_info=True)
            logger.info(
                f"Sleeping for {settings.CYCLE_FREQUENCY_SECONDS} seconds before next cycle"
            )
            await asyncio.sleep(settings.CYCLE_FREQUENCY_SECONDS)
    finally:
        logger.info("Closing ItemMonitor and scraper resources")
        await monitor.close()


async def main():
    try:
        logger.info("Starting OLX item notification worker")
        await worker_main()
    finally:
        logger.info("Shutting down OLX item notification worker")
        await close_client()


if __name__ == "__main__":
    asyncio.run(main())
