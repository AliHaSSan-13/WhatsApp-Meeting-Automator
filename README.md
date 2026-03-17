# WhatsApp Meeting Automator (Zoom & Google Meet)

An automated tool that monitors a specific WhatsApp Web chat for meeting links (Zoom or Google Meet), extracts the details, and automatically joins the meeting using the browser.

> [!WARNING]
> **Disclaimer:** Use this tool at your own risk. Automating interactions on platforms like WhatsApp, Zoom, and Google Meet may violate their Terms of Service. The developers are not responsible for any account bans, suspensions, or other negative consequences that may arise from using this software.

## Prerequisites

- Google Chrome browser
- Python 3.8+

## 1. Launch Chrome with Remote Debugging

To allow the automator to interact with your browser, you must launch Google Chrome with the remote debugging port enabled (`9222`). We also use a dedicated "Automation Profile" to keep your daily browsing separate and ensure clean sessions.

**Close any running instances of Chrome, then run the appropriate command for your OS in the terminal:**

### Linux
```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="$HOME/chrome-automation-profile"
```

### Windows
```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%LOCALAPPDATA%\Google\Chrome\AutomationProfile"
```

### macOS
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/Library/Application Support/Google/Chrome/AutomationProfile"
```

## 2. Setup WhatsApp Web

1. In the Chrome instance that just opened, navigate to [WhatsApp Web](https://web.whatsapp.com).
2. Scan the QR code with your phone to log in (you will only need to do this once for the automation profile).
3. Click on the specific chat (contact or group) where you expect to receive the links.
4. **Important:** Wait for the chat to fully load and ensure the chat messages are visible on the screen before proceeding.
5. **Important:** Don't touch or scroll the browser after the bot starts.

## 3. Configuration

Open the `config.yaml` file in the project directory and set your preferences:

```yaml
whatsapp:
  target_chat: "<CHAT NAME>"  # The exact name of the chat or group

zoom:
  auto_join: true              # Automatically join Zoom meetings
  display_name: "<YOUR NAME>"   # Your desired name for both Zoom & Meet

meet:
  auto_join: true              # Automatically join Google Meet meetings
```

## 4. Run the Automator

In a new terminal window, navigate to the project directory and set up the environment:

1. **Initialize the virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install requirements:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Run the main script:**
   ```bash
   python main.py
   ```

## How It Works

1. **Monitors:** The script connects to your active Chrome session via CDP. It injects a reliable `MutationObserver` + Fallback Scanner to monitor the specific WhatsApp chat for *new* incoming messages in real-time.
2. **Parses:** When a message is received, powerful Regex patterns detect if it's a **Zoom** or **Google Meet** link.
3. **Joins:** 
   - **Zoom:** Opens a new tab directly to the Zoom Web Client, handles permission dialogs, and enters your display name.
   - **Google Meet:** Opens a new tab, handles mic/cam dismissals, and clicks "Join now" or "Ask to join".
4. **Resets:** The script switches focus back to the WhatsApp tab, ready for the next meeting.

## Troubleshooting

- **`Connection refused` error:** Ensure Chrome was started with the commands in step 1. Check Task Manager to kill any lingering Chrome processes.
- **Bot misses messages:** Ensure the WhatsApp chat is actively selected and fully loaded.
- **Duplicate joins:** The bot has a built-in cache to prevent joining the exact same meeting ID multiple times in a single session.
