import re
import logging
from typing import Optional, Dict

logger = logging.getLogger("automator.zoom")

class MessageParser:
    """
    Robust message parser for extracting meeting links (Zoom, Google Meet).
    """
    def __init__(self):
        # 1. Matches Zoom URLs
        self.zoom_url_pattern = re.compile(
            r'https?://(?:[\w-]+\.)?zoom\.us/(?:j|my|w)/(\d+)(?:\S*pwd=([a-zA-Z0-9\._\-]+))?',
            re.IGNORECASE
        )
        
        # 2. Matches Zoom raw ID
        self.zoom_id_pattern = re.compile(
            r'(?:Meeting\s*ID|ID)\s*[:\-]?\s*(\d{3}[\s\-]?\d{3,4}[\s\-]?\d{3,4}|\d{9,11})',
            re.IGNORECASE
        )
        
        # 3. Matches Zoom Passcode
        self.zoom_passcode_pattern = re.compile(
            r'(?:Passcode|Password|Pwd)\s*[:\-]?\s*([a-zA-Z0-9]+)',
            re.IGNORECASE
        )

        # 4. Matches Google Meet URLs - Flexible to various ID formats
        self.meet_url_pattern = re.compile(
            r'meet\.google\.com/([a-z0-9-]+)(?:\?.*)?',
            re.IGNORECASE
        )

    def parse_message(self, message: str) -> Optional[Dict[str, str]]:
        """
        Parses a message string to extract meeting information.
        Returns a dictionary with 'type', 'meeting_id', 'url', etc.
        """
        # --- Check Google Meet First ---
        meet_match = self.meet_url_pattern.search(message)
        if meet_match:
            meet_id = meet_match.group(1).split('?')[0].strip('/')
            meet_url = meet_match.group(0)
            if not meet_url.startswith('http'):
                meet_url = 'https://' + meet_url
            
            # Simple check: Google meet codes are usually 10+ chars (with dashes)
            if len(meet_id.replace('-', '')) >= 9:
                logger.info(f"Google Meet detected -> ID: {meet_id}")
                return {
                    'type': 'meet',
                    'id': meet_id,
                    'meeting_id': meet_id, # Consistent naming
                    'url': meet_url
                }

        # --- Check Zoom ---
        zoom_result = {'type': 'zoom', 'meeting_id': None, 'passcode': None, 'url': None}
        
        url_match = self.zoom_url_pattern.search(message)
        if url_match:
            zoom_result['meeting_id'] = url_match.group(1)
            zoom_result['url'] = url_match.group(0)
            if url_match.group(2):
                zoom_result['passcode'] = url_match.group(2)
                
        if not zoom_result['meeting_id']:
            id_match = self.zoom_id_pattern.search(message)
            if id_match:
                zoom_result['meeting_id'] = re.sub(r'[\s\-]', '', id_match.group(1))
                
        if not zoom_result['passcode']:
            pwd_match = self.zoom_passcode_pattern.search(message)
            if pwd_match:
                zoom_result['passcode'] = pwd_match.group(1)
                
        if zoom_result['meeting_id']:
            logger.info(f"Zoom details extracted -> ID: {zoom_result['meeting_id']}")
            return zoom_result
            
        return None
