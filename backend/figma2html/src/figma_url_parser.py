"""
Figma URL Parser
Parse Figma design URLs to extract file key and node ID
"""

import re
import logging
from urllib.parse import urlparse, parse_qs, unquote
from typing import Optional, Tuple



class FigmaUrlParser:
    """Parse Figma URLs to extract file key and node ID"""

    def __init__(self):
        # Figma URL pattern: https://www.figma.com/design/{file_key}/{name}?node-id={node_id}
        self.figma_url_pattern = re.compile(
            r"https://www\.figma\.com/(?:file|design)/([a-zA-Z0-9]+)/[^?]*(?:\?.*)?"
        )

    def parse_url(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse a Figma URL to extract file key and node ID

        Args:
            url: Figma design URL

        Returns:
            Tuple of (file_key, node_id) or (None, None) if parsing fails
        """
        try:
            # Extract file key from URL
            match = self.figma_url_pattern.match(url)
            if not match:
                return None, None

            file_key = match.group(1)

            # Extract node ID from query parameters
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)

            node_id = None
            if "node-id" in query_params:
                node_id = query_params["node-id"][0]
                # Convert node-id format from "795-156" to "795:156"
                node_id = node_id.replace("-", ":")

            return file_key, node_id

        except Exception as e:
            logging.error(f"Error parsing URL: {e}")
            return None, None

    def validate_url(self, url: str) -> bool:
        """
        Validate if the URL is a valid Figma design URL

        Args:
            url: URL to validate

        Returns:
            True if valid Figma URL, False otherwise
        """
        file_key, _ = self.parse_url(url)
        return file_key is not None


def parse_figma_url(url: str):
    """
    Parse a Figma design URL and extract the file key and node id (if present).
    Returns (file_key, node_id or None)
    """
    url = url.strip()
    url = unquote(url)

    # Figma file key is always after /file/ or /design/
    match = re.search(r"/(file|design)/([a-zA-Z0-9]+)", url)
    file_key = match.group(2) if match else None

    node_id = None
    parsed = urlparse(url)
    # 쿼리에서 역슬래시 제거
    query_str = parsed.query.replace("\\", "")
    logging.debug(f"Query string: {query_str}")
    if query_str:
        qs = parse_qs(query_str)
        if "node-id" in qs:
            node_id = qs["node-id"][0].replace("-", ":")
        elif "id" in qs:
            node_id = qs["id"][0].replace("-", ":")
    if not node_id and parsed.fragment:
        frag = parse_qs(parsed.fragment)
        if "node-id" in frag:
            node_id = frag["node-id"][0].replace("-", ":")

    return file_key, node_id


if __name__ == "__main__":
    # Test cases
    test_urls = [
        "https://www.figma.com/design/ShIThk2v6s6kFHSuuuC2L0/Positivus-Landing-Page-Design--Community-?node-id=795-156&m=dev",
        "https://www.figma.com/file/abc123/Some-Design?node-id=1-2",
        "https://www.figma.com/file/abc123/Some-Design#node-id=1-2",
        "https://www.figma.com/design/abc123/Some-Design",
        "https://www.figma.com/file/abc123/Some-Design?id=1-2",
    ]
    for url in test_urls:
        file_key, node_id = parse_figma_url(url)
        logging.debug(f"URL: {url}\n  file_key: {file_key}\n  node_id: {node_id}\n")
