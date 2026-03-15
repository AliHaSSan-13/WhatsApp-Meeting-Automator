import re
import logging
import sys
import subprocess
import json
from playwright.async_api import Page

logger = logging.getLogger("automator.whatsapp")

# Zoom Regex
ZOOM_REGEX = r"https?:\/\/[\w\.]*zoom\.us\/j\/(\d+)(?:\S+pwd=([\w\d]+))?"

class WhatsAppMonitor:
    """Monitors WhatsApp for Zoom links and handles them."""
    def __init__(self, target_chat: str, message_callback=None):
        self.target_chat = target_chat.strip()
        self.page = None
        self.message_callback = message_callback

    async def start_monitoring(self, page: Page):
        """Injects the monitoring logic into the page."""
        self.page = page
        
        # Expose functions to bridge JS and Python
        await self.page.expose_function("notify_python", self.handle_message)
        await self.page.expose_function("log_from_js", self.handle_js_log)
        await self.page.expose_function("request_click", self.perform_native_click)

        # Inject JavaScript that handles detection and chat switching
        await self.page.evaluate(f"""
            (function() {{
                // 1. Force cleanup of any previous instances
                if (window.wa_automator_instance) {{
                    window.wa_automator_instance.cleanup();
                    window.log_from_js("Cleanup complete. Starting new instance for: {self.target_chat}");
                }}

                const TARGET = "{self.target_chat}";
                let lastRequestTime = 0;
                let lastObserverCheck = 0;

                const instance = {{
                    cleanup: function() {{
                        if (this.uiObserver) this.uiObserver.disconnect();
                        if (this.msgObserver) this.msgObserver.disconnect();
                        window.wa_automator_instance = null;
                    }},
                    
                    isTargetChatOpen: function() {{
                        // 1. Try the specific selector provided by the user (highest priority)
                        const userSelector = '#main > header > div.x78zum5.xdt5ytf.x1iyjqo2.xl56j7k.xeuugli.xtnn1bt.x9v5kkp.xmw7ebm.xrdum7p > div > div > div > div > span';
                        const userEl = document.querySelector(userSelector);
                        if (userEl) {{
                            const title = (userEl.innerText || userEl.textContent).replace(/\\s+/g, ' ').trim().toLowerCase();
                            if (title.includes(TARGET.toLowerCase())) return true;
                        }}

                        const header = document.querySelector('header');
                        if (!header) return false;

                        // 2. Try data-testid fallback
                        const headerTitleEl = header.querySelector('[data-testid="conversation-info-header-chat-title"]');
                        if (headerTitleEl) {{
                            const title = (headerTitleEl.innerText || headerTitleEl.textContent).replace(/\\s+/g, ' ').trim().toLowerCase();
                            if (title.includes(TARGET.toLowerCase())) return true;
                        }}

                        // 3. Check all spans with title in header
                        const titleSpans = header.querySelectorAll('span[title]');
                        let foundTitles = [];
                        for (const s of titleSpans) {{
                            const title = s.getAttribute('title').replace(/\\s+/g, ' ').trim().toLowerCase();
                            foundTitles.push(title);
                            if (title.includes(TARGET.toLowerCase())) return true;
                        }}

                        return false;
                    }},

                    checkAndAttach: function() {{
                        const now = Date.now();
                        if (now - lastObserverCheck < 500) return; // Throttling
                        lastObserverCheck = now;

                        const isOpen = this.isTargetChatOpen();
                        
                        if (!isOpen) {{
                            if (this.msgObserver) {{
                                this.msgObserver.disconnect();
                                this.msgObserver = null;
                                window.log_from_js("Chat '" + TARGET + "' is not active. Disconnecting message observer.");
                            }}
                            
                            // Re-open if enough time passed since last click
                            if (now - lastRequestTime > 10000) {{
                                window.log_from_js("Requesting click to open '" + TARGET + "'...");
                                lastRequestTime = now;
                                window.request_click(TARGET);
                            }}
                            return;
                        }}

                        // If open, attach/update message observer
                        const container = document.querySelector('#main') || 
                                        document.querySelector('[data-testid="conversation-panel-messages"]') || 
                                        document.querySelector('div[role="application"]');
                        
                        if (!container) return;
                        if (instance.lastContainer === container && instance.msgObserver) return;
                        
                        if (instance.msgObserver) instance.msgObserver.disconnect();
                        window.log_from_js("Target chat detected. Monitoring messages...");

                        const seenIds = new Set();
                        
                        // PRE-PROCESS EXISTING MESSAGES:
                        // This prevents the bot from reacting to old messages that are already on screen
                        // or get shifted around by WhatsApp's virtualized list during scrolling.
                        const existingMsgs = container.querySelectorAll('[data-id]');
                        for (const msgEl of existingMsgs) {{
                            const msgId = msgEl.getAttribute('data-id');
                            if (msgId) seenIds.add(msgId);
                        }}
                        
                        // Keep the set size manageable, keeping the most recent.
                        if (seenIds.size > 200) {{
                            const arr = Array.from(seenIds);
                            const toKeep = new Set(arr.slice(arr.length - 200));
                            seenIds.clear();
                            toKeep.forEach(id => seenIds.add(id));
                        }}
                        
                        window.log_from_js("Pre-loaded " + existingMsgs.length + " existing messages to ignore.");

                        instance.msgObserver = new MutationObserver((mutations) => {{
                            for (const mutation of mutations) {{
                                for (const node of mutation.addedNodes) {{
                                    if (node.nodeType === 1) {{ 
                                        // 1. Find message containers within the added nodes
                                        const msgElements = node.querySelectorAll ? node.querySelectorAll('[data-id]') : [];
                                        
                                        // Also check the node itself
                                        const elementsToProcess = [...msgElements];
                                        if (node.hasAttribute && node.getAttribute('data-id')) {{
                                            elementsToProcess.push(node);
                                        }}

                                        for (const msgEl of elementsToProcess) {{
                                            // Get unique ID (very reliable for WhatsApp)
                                            const msgId = msgEl.getAttribute('data-id');
                                            if (!msgId || seenIds.has(msgId)) continue;
                                            
                                            seenIds.add(msgId);
                                            // Keep buffer size reasonable
                                            if (seenIds.size > 200) {{
                                                const firstValue = seenIds.values().next().value;
                                                seenIds.delete(firstValue);
                                            }}

                                            // Extract content using specific selectors from the user's snippet
                                            const selectableText = msgEl.querySelector('span[data-testid="selectable-text"]');
                                            const textEl = selectableText || msgEl.querySelector('.copyable-text [dir]') || msgEl;
                                            
                                            const text = (textEl.innerText || "").trim();
                                            if (text.length > 0) {{
                                                window.notify_python(text);
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                        }});

                        instance.msgObserver.observe(container, {{ childList: true, subtree: true }});
                        instance.lastContainer = container;
                    }}
                }};

                window.wa_automator_instance = instance;
                
                instance.uiObserver = new MutationObserver(() => {{
                    instance.checkAndAttach();
                }});

                instance.uiObserver.observe(document.body, {{ childList: true, subtree: true }});
                
                // Initial kickstart
                instance.checkAndAttach();
                window.log_from_js("Automator V3 Initialized for: " + TARGET);
            }})();
        """)
        logger.info(f"Monitoring injected for: {self.target_chat}")

    async def perform_native_click(self, target: str):
        """Uses Playwright's native mouse pointer to click the chat in the sidebar."""
        try:
            # Locate the chat in the sidebar using a robust selector
            # We look for a span that contains the target name inside the sidebar pane
            selector = f'#pane-side span[title*="{target}"]'
            
            logger.info(f"Attempting native Playwright click on: {target}")
            
            # Use Playwright's click which handles scrolling and real mouse events
            # We find the cell container to ensure a clean click
            locator = self.page.locator(selector).first
            
            # Check if it exists
            if await locator.count() > 0:
                # Click the parent row for better reliability
                row_locator = self.page.locator(f'div[role="row"]:has(span[title*="{target}"])').first
                if await row_locator.count() > 0:
                    await row_locator.click(timeout=5000)
                else:
                    await locator.click(timeout=5000)
                logger.info("Native click performed successfully.")
            else:
                logger.warning(f"Could not find '{target}' in sidebar for native click. Is the sidebar visible?")
        except Exception as e:
            logger.error(f"Error during native click: {str(e)}")

    def handle_js_log(self, msg: str):
        """Handles logs from the browser's JavaScript context."""
        logger.info(f"[Browser] {msg}")

    async def handle_message(self, text: str):
        """Passes the detected message content back via the callback, or logs it."""
        import asyncio
        clean_text = text.replace('\n', ' ').strip()
        
        if self.message_callback:
            if asyncio.iscoroutinefunction(self.message_callback):
                await self.message_callback(clean_text)
            else:
                self.message_callback(clean_text)
        else:
            logger.info(f"CHAT MESSAGE: {clean_text}")

    def launch_zoom(self, meeting_id: str, passcode: str = None):
        """Cross-platform Zoom meeting launcher."""
        uri = f"zoommtg://zoom.us/join?confno={meeting_id}"
        if passcode:
            uri += f"&pwd={passcode}"
        
        logger.info(f"Attempting to launch Zoom...")
        
        try:
            if sys.platform == "linux":
                subprocess.run(["xdg-open", uri], check=True)
            elif sys.platform == "win32":
                import os
                os.startfile(uri)
            elif sys.platform == "darwin":
                subprocess.run(["open", uri], check=True)
            logger.info("Zoom launch command executed successfully.")
        except Exception as e:
            logger.error(f"Failed to launch Zoom: {str(e)}")
