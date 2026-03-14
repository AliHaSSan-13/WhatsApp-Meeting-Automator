import logging
import asyncio
from playwright.async_api import Page, Error as PlaywrightError
from typing import Dict

logger = logging.getLogger("automator.zoom_joiner")

class ZoomJoiner:
    """
    Handles the process of opening Zoom links in the browser.
    Designed to be robust, handle tabs cleanly, and log exactly what happens.
    """
    
    def __init__(self, browser_manager):
        """
        Expects a BrowserManager instance to request new tabs.
        """
        self.browser_manager = browser_manager

    async def join_meeting(self, zoom_details: Dict[str, str], timeout_seconds: int = 30):
        """
        Opens a new tab in the connected browser and navigates to the Zoom link.
        """
        url = zoom_details.get('url')
        meeting_id = zoom_details.get('meeting_id')
        passcode = zoom_details.get('passcode')
        
        if not url:
            # If we don't have a direct URL but have ID and Passcode, construct one.
            if meeting_id:
                url = f"https://zoom.us/j/{meeting_id}"
                if passcode:
                    url += f"?pwd={passcode}"
            else:
                logger.error("No valid URL or Meeting ID provided to ZoomJoiner.")
                return False

        page = None
        try:
            logger.info(f"Preparing to join Zoom Meeting [{meeting_id}]...")
            
            # Step 1: Open a new tab in the existing browser context
            page = await self.browser_manager.get_new_page()
            
            # Step 2: Navigate to the Zoom link
            logger.info(f"Navigating to Zoom URL: {url}")
            
            # We use a reasonable timeout so we don't hang forever
            # 'domcontentloaded' means the base HTML is ready
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
            
            # Step 3: Handle the 'Launch Meeting' interaction if necessary
            # When you open a Zoom link, the browser usually prompts to open the native App.
            # We wait a moment to let the browser OS-level protocol handle `zoommtg://`
            logger.info("Zoom page loaded. Waiting for native Zoom App to launch or handling web fallback...")
            
            # At this point, Chrome usually shows "Open xdg-open?" or similar for the Zoom app.
            # If the user has Zoom installed, it opens automatically.
            
            # Optional: We could attempt to click "Launch Meeting" if the automatic redirect fails
            launch_button = page.locator('div.launch-meeting-btn a.btn, div.action-btn-container button.mb-button')
            
            # Wait for up to 5 seconds to see if a manual launch button is needed/available
            try:
                if await launch_button.count() > 0:
                    logger.info("Found 'Launch Meeting' button, clicking to ensure protocol is triggered.")
                    await launch_button.first.click(timeout=5000)
                else:
                    # Generic fallback button matching text
                    generic_btn = page.locator("text='Launch Meeting'")
                    if await generic_btn.count() > 0:
                        logger.info("Found generic 'Launch Meeting' text, triggering click.")
                        await generic_btn.first.click(timeout=5000)
            except Exception as wait_e:
                logger.debug(f"Manual launch button interaction skipped/failed: {str(wait_e)}")
            
            logger.info(f"Successfully executed join flow for Zoom Meeting [{meeting_id}].")
            return True

        except PlaywrightError as e:
            logger.error(f"Playwright error while trying to join Zoom: {str(e)}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error while joining Zoom: {str(e)}", exc_info=True)
            return False
            
        finally:
            # Step 4: Clean up
            # Usually, after Zoom launches, we don't need the tab sitting there forever.
            # We wait a few seconds and then gracefully close the tab.
            if page:
                # We do this asynchronously without blocking the main event loop too long
                asyncio.create_task(self._delayed_close(page, meeting_id))

    async def _delayed_close(self, page: Page, meeting_id: str):
        """Closes the tab after a delay so Zoom has time to process the URL."""
        try:
            logger.info(f"Tab for [{meeting_id}] will close in 15 seconds to keep the browser clean...")
            await asyncio.sleep(15)
            if not page.is_closed():
                await page.close()
                logger.info(f"Closed Zoom tab for [{meeting_id}].")
        except Exception as e:
            logger.debug(f"Error during delayed tab closing: {str(e)}")
