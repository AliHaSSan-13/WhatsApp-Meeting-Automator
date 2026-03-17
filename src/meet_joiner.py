import logging
import asyncio
from playwright.async_api import Page, Error as PlaywrightError
from typing import Dict

logger = logging.getLogger("automator.meet_joiner")

class MeetJoiner:
    """
    Handles the process of joining Google Meet meetings in the browser.
    """
    
    def __init__(self, browser_manager):
        self.browser_manager = browser_manager
        self._joined_meetings = set()

    async def join_meeting(self, meet_details: Dict[str, str], display_name: str = "Automator Guest", timeout_seconds: int = 45):
        """
        Navigates to a Google Meet link and performs UI interactions to join.
        """
        url = meet_details.get('url')
        meet_id = meet_details.get('id')
        
        if not url and not meet_id:
            logger.error("No valid URL or ID provided to MeetJoiner.")
            return False
            
        if not url:
            url = f"https://meet.google.com/{meet_id}"

        # Deduplication check
        if meet_id and meet_id in self._joined_meetings:
            logger.info(f"Meeting [{meet_id}] already joined. Skipping.")
            return False
            
        if meet_id:
            self._joined_meetings.add(meet_id)
            if len(self._joined_meetings) > 100:
                self._joined_meetings.pop()

        page = None
        try:
            logger.info(f"Preparing to join Google Meet [{meet_id}]...")
            page = await self.browser_manager.get_new_page()
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
            except PlaywrightError as nav_e:
                logger.warning(f"Navigation warning: {str(nav_e)}")
            
            # Wait for content to stabilize
            await asyncio.sleep(5)

            # --- 1. Fill Name (if not logged in) ---
            try:
                # Based on user HTML: <input ... aria-label="Your name" ...>
                name_selector = 'input[aria-label="Your name"]'
                logger.info(f"Waiting for name input: {name_selector}")
                
                name_input = page.locator(name_selector).first
                # Wait for visibility
                await name_input.wait_for(state="visible", timeout=15000)
                
                logger.info(f"Entering name: {display_name}")
                await name_input.fill(display_name)
                await asyncio.sleep(1)
            except Exception as e:
                logger.debug(f"Name input field not found or not needed (perhaps already logged in): {str(e)}")

            # --- 2. Click Join Button ---
            # Try specific selectors for "Join now" and "Ask to join"
            join_selectors = [
                'button:has-text("Ask to join")',
                'button:has-text("Join now")',
                '[role="button"]:has-text("Ask to join")',
                '[role="button"]:has-text("Join now")'
            ]
            
            joined = False
            for sel in join_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0:
                        logger.info(f"Found join button with selector: {sel}")
                        await btn.click(timeout=5000)
                        joined = True
                        break
                except:
                    continue
            
            if joined:
                logger.info(f"Successfully clicked join for Google Meet [{meet_id}].")
            else:
                logger.warning(f"Failed to find a join button for [{meet_id}].")

            # Switch back to WhatsApp
            await self.browser_manager.switch_to_main_page()
            return True

        except Exception as e:
            logger.error(f"Error during Google Meet join: {str(e)}", exc_info=True)
            return False
