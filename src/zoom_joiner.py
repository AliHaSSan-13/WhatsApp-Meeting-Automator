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
        self._joined_meetings = set()

    async def join_meeting(self, zoom_details: Dict[str, str], display_name: str = "Automator Guest", timeout_seconds: int = 45):
        """
        Opens a new tab in the connected browser, navigates to the Zoom link, 
        and performs the necessary UI interactions to join via the web browser client.
        """
        url = zoom_details.get('url')
        meeting_id = zoom_details.get('meeting_id')
        passcode = zoom_details.get('passcode')
        
        if not meeting_id and not url:
            logger.error("No valid URL or Meeting ID provided to ZoomJoiner.")
            return False
            
        # Deduplication check: Don't join the exact same meeting twice in one run
        if meeting_id and meeting_id in self._joined_meetings:
            logger.info(f"Meeting [{meeting_id}] was already joined in this session. Skipping to prevent duplicates.")
            return False
            
        if meeting_id:
            self._joined_meetings.add(meeting_id)
            # Limit cache size to prevent memory leaks over long runs
            if len(self._joined_meetings) > 100:
                self._joined_meetings.pop()

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
            
            # Step 1: Build the direct web client URL.
            # Using app.zoom.us/wc/join/ bypasses the landing page (zoom.us/j/) entirely,
            # which is what triggers the native "Open Zoom Workplace?" OS popup.
            if meeting_id:
                wc_url = f"https://app.zoom.us/wc/join/{meeting_id}"
                if passcode:
                    wc_url += f"?pwd={passcode}"
            else:
                # Fall back to the original URL if we only have a raw link
                wc_url = url
            
            # Step 2: Open a new tab and navigate directly to the web client
            page = await self.browser_manager.get_new_page()
            logger.info(f"Navigating directly to Zoom Web Client: {wc_url}")
            
            try:
                await page.goto(wc_url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
            except PlaywrightError as nav_e:
                if "net::ERR_ABORTED" in str(nav_e):
                    logger.info("Navigation aborted (expected for app handoff), continuing web flow.")
                else:
                    logger.warning(f"Navigation warning: {str(nav_e)}")
            
            # Step 3: Wait for the Zoom React app to fully initialise
            logger.info("Waiting for Zoom web client to fully load...")
            try:
                await page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                logger.warning("Network did not reach idle state — proceeding with extra time buffer.")
            await asyncio.sleep(3)

            logger.info("Phase 1 join flow complete for meeting. Waiting for permission dialog...")
            
            # Step 4: Wait for network idle and handle the "Continue without microphone and camera" permission
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await asyncio.sleep(2)

            async def force_click_in_frames(locator_str: str) -> bool:
                for frame in page.frames:
                    try:
                        el = frame.locator(locator_str).first
                        if await el.count() > 0:
                            logger.info(f"Found '{locator_str}' in frame: '{frame.name or 'main'}'")
                            await el.evaluate("node => node.click()")
                            return True
                    except Exception:
                        continue
                return False

            # Specific selector provided by user
            permission_selector = "span.pepc-permission-dialog__footer-button"
            
            # User mentioned it needs to be clicked 2 times
            for i in range(2):
                logger.info(f"Attempting to click permission button (Continue without mic/cam) - attempt {i+1}...")
                if await force_click_in_frames(permission_selector):
                    logger.info(f"Clicked permission button on attempt {i+1}.")
                    await asyncio.sleep(2)  # Wait for UI to react
                else:
                    # Generic fallback if specific selector fails
                    if await force_click_in_frames("span:has-text('Continue without')"):
                        logger.info(f"Clicked permission button via text fallback on attempt {i+1}.")
                        await asyncio.sleep(2)
                    else:
                        logger.debug(f"Permission button not found on attempt {i+1}.")
                        break

            # Step 6: Fill the Name input
            logger.info(f"Attempting to enter name: {display_name}")
            name_filled = False
            for frame in page.frames:
                try:
                    name_input = frame.locator("#input-for-name").first
                    if await name_input.count() > 0:
                        logger.info(f"Found name input in frame: '{frame.name or 'main'}'")
                        await name_input.fill(display_name)
                        name_filled = True
                        break
                except Exception:
                    continue
            
            if not name_filled:
                logger.warning("Could not find name input field via locator. Trying JS fallback...")
                name_filled = await page.evaluate(f"""() => {{
                    const input = document.querySelector('#input-for-name');
                    if (input) {{
                        input.value = "{display_name}";
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        return true;
                    }}
                    return false;
                }}""")
            
            if name_filled:
                logger.info("Successfully entered display name.")
            else:
                logger.warning("Failed to enter display name.")

            await asyncio.sleep(2)

            # Step 7: Click the final Join button
            logger.info("Attempting to click final Join button...")
            join_btn_selector = "button.preview-join-button"
            
            if await force_click_in_frames(join_btn_selector):
                logger.info("Successfully clicked final Join button.")
            else:
                # Fallback to text match
                if await force_click_in_frames("button:has-text('Join')"):
                    logger.info("Clicked Join button via text fallback.")
                else:
                    logger.warning("Could not find final Join button.")

            logger.info(f"Join flow completed for meeting [{meeting_id}].")
            
            # Switch focus back to the main WhatsApp tab to keep monitoring active and visible
            await self.browser_manager.switch_to_main_page()
            
            return True

        except Exception as e:
            logger.error(f"Critical error during Zoom join: {str(e)}", exc_info=True)
            return False
