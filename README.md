# WhatsApp to Zoom Automator

An automated tool that monitors a specific WhatsApp Web chat for Zoom meeting links, extracts the meeting details, and automatically joins the meeting using the Zoom web client.

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
3. Click on the specific chat (contact or group) where you expect to receive the Zoom links.
4. **Important:** Wait for the chat to fully load and ensure the chat messages are visible on the screen before proceeding.
5. **Important:** Don't Touch or scroll the browser after the bot starts.

## 3. Configuration

Open the `config.yaml` file in the project directory and set your preferences:

```yaml
whatsapp:
  target_chat_name: "<CHAT NAME>"  # The exact name of the chat or group

zoom:
  auto_join: true                      # Set to true to automatically join the meeting
  display_name: "<YOUR NAME>"           # Your desired name in the Zoom meeting
```

## 4. Run the Automator

In a new terminal window, navigate to the project directory and set up the environment:

1. **Initialize the virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
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

1. **Monitors:** The script securely connects to your active Chrome session via CDP. It injects a reliable `MutationObserver` to monitor the specific WhatsApp chat for *new* incoming messages.
2. **Parses:** When a message is received, powerful Regex patterns extract the Zoom `Meeting ID` and `Passcode` (handling messy multiline texts and varying formats).
3. **Joins:** 
   - A new browser tab is opened directly to the Zoom Web Client.
   - It intelligently handles permissions ("Continue without microphone and camera").
   - It inputs your display name and joins the room.
4. **Resets:** The script switches focus back to the WhatsApp tab, ready to catch the next meeting link.

## Troubleshooting

- **`Connection refused` error:** Ensure Chrome was started with the commands in step 1. If it fails, completely close Chrome (check Task Manager/Activity Monitor) and try the command again.
- **Bot misses messages:** Ensure the WhatsApp chat is actively selected and fully loaded in the browser. 
- **Duplicate joins:** The bot has a built-in cache to prevent joining the exact same meeting ID multiple times in a single session.
