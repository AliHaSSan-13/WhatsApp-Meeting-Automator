import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger("automator.browser")

class BrowserManager:
    """Manages the connection to the host browser via CDP."""

    def __init__(self, cdp_url: str):
        self.cdp_url = cdp_url
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def connect(self) -> Page:
        """Connects to the browser via CDP and returns the first page."""
        try:
            logger.info(f"Connecting to browser at {self.cdp_url}...")
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)
            
            if not self._browser.contexts:
                raise RuntimeError("No browser contexts found. Is Chrome open?")
            
            self._context = self._browser.contexts[0]
            
            if not self._context.pages:
                raise RuntimeError("No open pages found. Please open WhatsApp Web.")
            
            self._page = self._context.pages[0]
            
            # Use a more resilient way to check if connected
            try:
                title = await self._page.title()
                logger.info(f"Connected successfully. Current page title: {title}")
            except Exception:
                logger.info("Connected successfully. Page is currently busy or navigating.")
            
            return self._page

        except Exception as e:
            logger.error(f"Failed to connect to browser: {str(e)}")
            await self.close()
            raise

    async def get_new_page(self) -> Page:
        """Returns a new tab in the connected browser context."""
        if not self._context:
            raise RuntimeError("Browser is not connected.")
        
        logger.info("Opening a new browser tab...")
        return await self._context.new_page()

    async def switch_to_main_page(self):
        """Brings the initial page (WhatsApp) back to the front."""
        if self._page:
            try:
                logger.info("Switching focus back to the main WhatsApp tab...")
                await self._page.bring_to_front()
                return True
            except Exception as e:
                logger.error(f"Failed to switch back to main page: {str(e)}")
        return False

    async def close(self):
        """Cleanly closes playwright resources."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser connection closed.")
