import re
import logging
import sys
import subprocess
import json
from playwright.async_api import Page

logger = logging.getLogger("automator.whatsapp")

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
                        if (this.fallbackInterval) clearInterval(this.fallbackInterval);
                        window.wa_automator_instance = null;
                    }},
                    
                    isTargetChatOpen: function() {{
                        const normalize = (s) => (s || "").replace(/\\s+/g, ' ').trim().toLowerCase();
                        const targetNorm = normalize(TARGET);
                        
                        const selectors = [
                            'header [data-testid="conversation-info-header-chat-title"]',
                            'header span[title]',
                            '#main header span',
                            '[data-testid="chat-header"] span',
                            'header [role="button"]',
                            '#main header'
                        ];

                        for (const sel of selectors) {{
                            const elements = document.querySelectorAll(sel);
                            for (const el of elements) {{
                                const text = normalize(el.getAttribute('title') || el.innerText || el.textContent);
                                if (text && text.includes(targetNorm)) return true;
                            }}
                        }}
                        return false;
                    }},

                    checkAndAttach: function() {{
                        const now = Date.now();
                        if (now - lastObserverCheck < 1000) return;
                        lastObserverCheck = now;

                        const isOpen = this.isTargetChatOpen();
                        
                        if (!isOpen) {{
                            if (this.msgObserver) {{
                                this.msgObserver.disconnect();
                                this.msgObserver = null;
                                if (this.fallbackInterval) clearInterval(this.fallbackInterval);
                                window.log_from_js("Target chat not detected.");
                            }}
                            
                            if (now - lastRequestTime > 15000) {{
                                window.log_from_js("Chat '" + TARGET + "' hidden. Click requested.");
                                lastRequestTime = now;
                                window.request_click(TARGET);
                            }}
                            return;
                        }}

                        const container = document.querySelector('#main') || 
                                        document.querySelector('[data-testid="conversation-panel-messages"]') ||
                                        document.querySelector('[role="application"]');
                        
                        if (!container || (instance.lastContainer === container && instance.msgObserver)) return;
                        
                        if (instance.msgObserver) instance.msgObserver.disconnect();
                        if (instance.fallbackInterval) clearInterval(instance.fallbackInterval);
                        
                        window.log_from_js("Link monitoring started for: " + TARGET);

                        const seenIds = new Set();
                        
                        const processElements = (elements) => {{
                            for (const el of elements) {{
                                const msgId = el.getAttribute('data-id');
                                if (!msgId || seenIds.has(msgId)) continue;
                                seenIds.add(msgId);
                                
                                // el.innerText contains both message text and preview card text.
                                const text = (el.innerText || el.textContent || "").trim();
                                
                                if (text.length > 0) {{
                                    if (msgId.includes('@g.us')) {{
                                        window.log_from_js("Captured group msg: " + msgId.substring(msgId.length - 15));
                                    }}
                                    window.notify_python(text);
                                }}
                            }}
                        }};

                        // Initial scan
                        container.querySelectorAll('[data-id]').forEach(el => {{
                            const id = el.getAttribute('data-id');
                            if (id) seenIds.add(id);
                        }});

                        // 1. Mutation Observer (Deep subtree + Attributes)
                        instance.msgObserver = new MutationObserver((mutations) => {{
                            let toProcess = [];
                            for (const mutation of mutations) {{
                                if (mutation.type === 'childList') {{
                                    mutation.addedNodes.forEach(node => {{
                                        if (node.nodeType === 1) {{
                                            if (node.getAttribute('data-id')) toProcess.push(node);
                                            toProcess.push(...node.querySelectorAll('[data-id]'));
                                        }}
                                    }});
                                }} else if (mutation.type === 'attributes' && mutation.attributeName === 'data-id') {{
                                    toProcess.push(mutation.target);
                                }}
                            }}
                            if (toProcess.length > 0) processElements(toProcess);
                        }});

                        instance.msgObserver.observe(container, {{ 
                            childList: true, 
                            subtree: true,
                            attributes: true,
                            attributeFilter: ['data-id']
                        }});

                        // 2. High-frequency Backup Scanner
                        instance.fallbackInterval = setInterval(() => {{
                            const all = container.querySelectorAll('[data-id]');
                            const fresh = Array.from(all).filter(el => !seenIds.has(el.getAttribute('data-id')));
                            if (fresh.length > 0) processElements(fresh);
                        }}, 1000);

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
        logger.info(f"[Browser] {clean_text}")
        
        if self.message_callback:
            if asyncio.iscoroutinefunction(self.message_callback):
                await self.message_callback(clean_text)
            else:
                self.message_callback(clean_text)
        else:
            logger.info(f"CHAT MESSAGE: {clean_text}")

    