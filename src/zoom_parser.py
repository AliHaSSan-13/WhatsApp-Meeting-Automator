import re
import logging
from typing import Optional, Dict

logger = logging.getLogger("automator.zoom")

class ZoomParser:
    """
    Highly robust Zoom link and credential parser.
    Designed to extract meeting details regardless of the message structure.
    """
    def __init__(self):
        # 1. Matches URLs like: https://us04web.zoom.us/j/12345678901?pwd=abcdefg
        # Also handles zoom.us/my/vanityurls
        self.url_pattern = re.compile(
            r'https?://(?:[\w-]+\.)?zoom\.us/(?:j|my|w)/(\d+)(?:\S*pwd=([a-zA-Z0-9]+))?',
            re.IGNORECASE
        )
        
        # 2. Matches raw text like: "Meeting ID: 123 4567 8901" or "ID: 123-4567-8901"
        self.meeting_id_pattern = re.compile(
            r'(?:Meeting\s*ID|ID)\s*[:\-]?\s*(\d{3}[\s\-]?\d{3,4}[\s\-]?\d{3,4}|\d{9,11})',
            re.IGNORECASE
        )
        
        # 3. Matches raw text like: "Passcode: 123456" or "Password: abc"
        self.passcode_pattern = re.compile(
            r'(?:Passcode|Password|Pwd)\s*[:\-]?\s*([a-zA-Z0-9]+)',
            re.IGNORECASE
        )

    def parse_message(self, message: str) -> Optional[Dict[str, str]]:
        """
        Parses a message string to extract Zoom meeting information.
        Returns a dictionary with 'meeting_id', 'passcode', and 'url' if found.
        """
        result = {'meeting_id': None, 'passcode': None, 'url': None}
        
        # Step 1: Attempt to extract from embedded links
        url_match = self.url_pattern.search(message)
        if url_match:
            result['meeting_id'] = url_match.group(1)
            result['url'] = url_match.group(0)
            if url_match.group(2):
                result['passcode'] = url_match.group(2)
                
        # Step 2: Fallback to raw text extraction if URL didn't provide everything
        if not result['meeting_id']:
            id_match = self.meeting_id_pattern.search(message)
            if id_match:
                # Clean up spaces and dashes to get the raw numbers
                result['meeting_id'] = re.sub(r'[\s\-]', '', id_match.group(1))
                
        if not result['passcode']:
            pwd_match = self.passcode_pattern.search(message)
            if pwd_match:
                result['passcode'] = pwd_match.group(1)
                
        # If we successfully found at least a Meeting ID, return the result
        if result['meeting_id']:
            logger.info(f"Zoom details extracted -> ID: {result['meeting_id']}, Passcode: {result['passcode']}")
            return result
            
        return None
