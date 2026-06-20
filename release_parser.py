import os
import logging
import requests
import feedparser
import datetime
import email.utils
import re

logger = logging.getLogger(__name__)

# Default BigQuery Release Notes feed URL
DEFAULT_FEED_URL = "https://docs.cloud.google.com/feeds/bigquery-release-notes.xml"

# Configuration for request timeouts
DEFAULT_TIMEOUT = 10.0  # seconds

def parse_date_to_iso8601(date_str):
    """
    Normalizes a date string from the feed (Atom/RSS format or timezone offsets)
    to ISO 8601 UTC format: YYYY-MM-DDTHH:MM:SSZ.
    
    Handles:
    1. RFC 2822: 'Mon, 15 Jun 2026 18:00:00 GMT'
    2. ISO 8601 with 'Z': '2026-06-15T18:00:00Z'
    3. ISO 8601 with offset: '2026-06-15T10:00:00-07:00' or without colons: '2026-06-15T10:00:00-0700'
    4. Date-only: '2026-06-15'
    """
    if not date_str:
        raise ValueError("Empty date string provided")
        
    date_str = date_str.strip()
    
    # 1. Try parsing as RFC 2822 (common in RSS feeds)
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        dt_utc = dt.astimezone(datetime.timezone.utc)
        return dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    except (ValueError, TypeError, IndexError):
        pass

    # 2. Try parsing as ISO 8601 (Atom standard)
    normalized = date_str
    # Normalize timezone offsets without colons (e.g. -0700 to -07:00, +0200 to +02:00) at the end of the string
    normalized = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', normalized)
    
    if normalized.endswith('Z'):
        # Normalize trailing Z to +00:00 for Python datetime parser compatibility
        normalized = normalized[:-1] + '+00:00'
        
    try:
        if len(normalized) == 10:  # YYYY-MM-DD
            normalized += 'T00:00:00+00:00'
        dt = datetime.datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        dt_utc = dt.astimezone(datetime.timezone.utc)
        return dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        pass

    # 3. Fallback: Parse using dateutil if installed (provides extra resilience)
    try:
        import dateutil.parser
        dt = dateutil.parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        dt_utc = dt.astimezone(datetime.timezone.utc)
        return dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    except (ImportError, ValueError, TypeError):
        pass

    raise ValueError(f"Unable to parse date string: {date_str}")


def fetch_and_parse_feed(feed_url=None, timeout=DEFAULT_TIMEOUT):
    """
    Fetches the RSS/Atom feed from feed_url (falls back to RELEASE_NOTES_FEED_URL or FEED_URL env var or DEFAULT_FEED_URL)
    using requests with SSL verification and timeouts, parses it with feedparser, and returns
    a list of formatted release note dicts.
    
    Raises:
        requests.RequestException: For network, timeout, HTTP, and SSL errors.
        ValueError: For malformed XML or missing critical properties.
    """
    url = feed_url or os.environ.get("RELEASE_NOTES_FEED_URL") or os.environ.get("FEED_URL") or DEFAULT_FEED_URL
    
    logger.info(f"Fetching release notes feed from {url}")
    
    try:
        # Perform HTTP GET request with SSL verification and configured timeout
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while fetching feed: {str(e)}")
        raise e

    # Parse response content using feedparser (using bytes content to avoid UTF-8 scrambling)
    feed_data = feedparser.parse(response.content)
    
    # Handle malformed XML via feedparser's bozo flag.
    # bozo is set to 1 if the feed is not well-formed XML.
    if feed_data.bozo:
        bozo_exc = feed_data.get("bozo_exception")
        # Ignore encoding warnings, but raise errors for actual structural parsing failures
        if bozo_exc and not isinstance(bozo_exc, feedparser.CharacterEncodingOverride):
            logger.error(f"Malformed XML detected: {str(bozo_exc)}")
            raise ValueError(f"Malformed XML: {str(bozo_exc)}")
            
    releases = []
    
    # Check if entries exist
    if not hasattr(feed_data, 'entries') or not feed_data.entries:
        # If the feed has no entries and was marked bozo (warning), raise an error
        if feed_data.bozo:
            raise ValueError("Failed to parse feed: invalid XML structure and no entries found.")
        return []

    for entry in feed_data.entries:
        # Extract title (default if missing)
        title = entry.get("title", "No Title")
        
        # Extract link and handle possible nested dictionary/list structures from feedparser
        link = entry.get("link", "")
        if isinstance(link, list) and len(link) > 0:
            link = link[0].get("href", "")
        elif isinstance(link, dict):
            link = link.get("href", "")
            
        # Extract raw date from published, updated, or date elements
        date_raw = entry.get("updated") or entry.get("published") or entry.get("date")
        
        # If raw date is missing but parsed date is present, construct from parsed time tuple
        if not date_raw and entry.get("updated_parsed"):
            parsed_time = entry.updated_parsed
            dt = datetime.datetime(*parsed_time[:6], tzinfo=datetime.timezone.utc)
            date_iso = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        elif not date_raw and entry.get("published_parsed"):
            parsed_time = entry.published_parsed
            dt = datetime.datetime(*parsed_time[:6], tzinfo=datetime.timezone.utc)
            date_iso = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        elif date_raw:
            try:
                date_iso = parse_date_to_iso8601(date_raw)
            except ValueError as date_err:
                logger.error(f"Error parsing date '{date_raw}' for entry '{title}': {str(date_err)}")
                raise ValueError(f"Invalid date format in feed entry: {str(date_err)}")
        else:
            logger.error(f"Release entry missing date: {title}")
            raise ValueError(f"Entry missing date: {title}")
            
        # Extract content (content element takes precedence over summary)
        content = ""
        if "content" in entry and entry.content:
            content = entry.content[0].value
        else:
            content = entry.get("summary", "")
            
        releases.append({
            "title": title,
            "link": link,
            "date": date_iso,
            "content": content
        })
        
    return releases
