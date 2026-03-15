import asyncio
import yaml
import logging
import datetime
from logger import setup_logger
from src.browser_manager import BrowserManager
from src.whatsapp_monitor import WhatsAppMonitor
from src.zoom_parser import ZoomParser
from src.zoom_joiner import ZoomJoiner

async def main():
    # 1. Load Configuration
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config.yaml: {e}")
        return

    # 2. Setup Logger
    log_config = config.get("logging", {})
    logger = setup_logger(
        "automator", 
        log_config.get("file", "automator.log"),
        log_config.get("level", "INFO")
    )

    logger.info("Starting WhatsApp to Zoom Automator...")

    # 3. Initialize Components
    browser_cfg = config.get("browser", {})
    whatsapp_cfg = config.get("whatsapp", {})
    
    browser_manager = BrowserManager(browser_cfg.get("cdp_url"))
    zoom_parser = ZoomParser()
    zoom_joiner = ZoomJoiner(browser_manager)
    
    output_cfg = config.get("output", {})
    links_file_path = output_cfg.get("links_file", "found_zoom_links.txt")
    
    zoom_cfg = config.get("zoom", {})
    auto_join = zoom_cfg.get("auto_join", False)
    display_name = zoom_cfg.get("display_name", "Automator Guest")
    
    async def on_new_message(text: str):
        logger.info(f"CHAT MESSAGE: {text}")
        
        # Run the message through the specialized regex parser
        zoom_details = zoom_parser.parse_message(text)
        
        if zoom_details:
            # We found a meeting! Create/Append to a file with the details
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            output_line = f"[{timestamp}] Zoom Match Found -> ID: {zoom_details['meeting_id']} | Passcode: {zoom_details['passcode']} | URL: {zoom_details['url']}\n"
            
            try:
                with open(links_file_path, "a") as out_file:
                    out_file.write(output_line)
                logger.info(f"Zoom details successfully appended to '{links_file_path}'.")
            except Exception as e:
                logger.error(f"Failed to write to '{links_file_path}': {e}")
            
            # Conditionally launch the zoom meeting using the robust ZoomJoiner
            if auto_join:
                await zoom_joiner.join_meeting(zoom_details, display_name=display_name)

    # Pass the callback function to the monitor
    monitor = WhatsAppMonitor(whatsapp_cfg.get("target_chat"), message_callback=on_new_message)

    try:
        # 4. Connect to Browser
        page = await browser_manager.connect()
        
        # 5. Start WhatsApp Monitoring
        await monitor.start_monitoring(page)
        
        # 6. Main execution loop
        poll_interval = whatsapp_cfg.get("poll_interval", 1.0)
        logger.info(f"Monitoring active. Poll interval: {poll_interval}s. Press Ctrl+C to exit.")
        
        while True:
            # Check if page is still alive
            if page.is_closed():
                logger.warning("Browser page was closed. Attempting to reconnect...")
                page = await browser_manager.connect()
                await monitor.start_monitoring(page)
                
            await asyncio.sleep(poll_interval)

    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown requested...")
    except Exception as e:
        logger.critical(f"Unexpected error: {str(e)}", exc_info=True)
    finally:
        await browser_manager.close()
        logger.info("Application exited.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
