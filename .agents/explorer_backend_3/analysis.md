# Detailed Design Analysis — Backend Flask Parser (M2)

## 1. Objective & Requirements
The goal of Milestone 2 (M2) is to design and implement a robust, production-grade Flask backend that fetches, parses, and caches the BigQuery Release Notes RSS/Atom feed from `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml`, returning a structured JSON list of releases.

### Key Deliverables:
- **`app.py`**: Flask server exposing:
  - `GET /`: Renders the single-page HTML frontend template.
  - `GET /api/releases`: API endpoint returning a JSON list of formatted releases.
- **`parser.py`**: Parser module executing feed retrieval, date normalization, error detection, and process-level caching (with Stale-While-Revalidate fallback).
- **Graceful Error Handling**: Returning `502 Bad Gateway` (or `500` for application-level crashes) with `{"error": "Failed to fetch or parse release notes feed"}` on network, parsing, SSL, or timeout errors.
- **Unit Test Suite**: Verification under happy-path, edge cases, caching, and network failure modes.

---

## 2. Interface Contracts

### 2.1 API Endpoint: `/api/releases`
- **Method**: `GET`
- **Query Parameters**: None
- **Response Headers**: `Content-Type: application/json`
- **Success Status**: `200 OK`
- **Success Payload Schema**:
  ```json
  [
    {
      "title": "string (Title of the release, e.g., 'BigQuery features updated')",
      "link": "string (URL to the release note section)",
      "date": "string (Normalized UTC ISO 8601 string, format: YYYY-MM-DDTHH:MM:SSZ)",
      "content": "string (HTML or plain text representation of the update detail)"
    }
  ]
  ```
- **Failure Status**: `502 Bad Gateway` (Upstream connection, timeout, SSL, or malformed XML failures) or `500 Internal Server Error` (Unexpected runtime exceptions)
- **Failure Payload Schema**:
  ```json
  {
    "error": "Failed to fetch or parse release notes feed"
  }
  ```

### 2.2 Template Endpoint: `/`
- **Method**: `GET`
- **Response Headers**: `Content-Type: text/html`
- **Success Status**: `200 OK`
- **Behavior**: Renders `templates/index.html`.

---

## 3. Detailed Architecture Design

### 3.1 Code Layout Compliance
Conforming to the layout specified in `PROJECT.md`:
```
workspace-root/
├── app.py
├── parser.py
├── requirements.txt
├── run.sh
├── templates/
│   └── index.html
├── static/
│   ├── styles.css
│   └── app.js
├── tests/
│   ├── conftest.py
│   └── test_parser.py    # Unit tests for the parser and caching
└── .agents/
    └── explorer_backend_3/
        ├── BRIEFING.md
        ├── ORIGINAL_REQUEST.md
        ├── progress.md
        ├── analysis.md   # This file
        └── handoff.md
```

### 3.2 Parser Module (`parser.py`) Architecture
`parser.py` isolates XML scraping and parsing from the Web router. It employs a custom hierarchy of exceptions to distinguish network errors from XML parsing issues, allowing Flask routes to react appropriately.

#### Process-Level Caching (Stale-While-Revalidate)
To protect against upstream feed downtime, network bottlenecks, and rate limits, `parser.py` implements an in-memory cache:
- **Cache TTL**: 5 minutes (300 seconds).
- **Downtime Resiliency**: If a cache refresh fails due to a temporary network drop or upstream server error (503/500/SSL error/Timeout), and the process has an existing stale cache, it will log a warning and return the stale data. This prevents user-facing errors.

```python
# parser.py - Draft Code Structure

import time
import logging
from datetime import datetime, timezone
import requests
import feedparser
import xml.sax

logger = logging.getLogger(__name__)

class FeedError(Exception):
    """Base exception for all feed processing failures."""
    pass

class FeedFetchError(FeedError):
    """Raised when HTTP request fails, timeouts occur, or SSL fails."""
    pass

class FeedParseError(FeedError):
    """Raised when XML parsing fails or feed is critically malformed."""
    pass

# Global process-level cache
_releases_cache = {
    "data": None,
    "last_fetched": 0
}
CACHE_TTL = 300  # 5 minutes

def parse_date_string(date_str):
    """
    Fallback parser for raw date strings of varying formats.
    Attempts ISO 8601 (with Z suffix compatibility) and RFC 2822.
    """
    if not date_str:
        return None
        
    # 1. Clean and convert standard ISO 8601 format
    try:
        clean_str = date_str.strip()
        if clean_str.endswith('Z'):
            clean_str = clean_str[:-1] + '+00:00'
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        pass

    # 2. Try RFC 2822 format (common in RSS 2.0 channels)
    import email.utils
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        pass

    return None

def fetch_and_parse_feed(url, timeout=(3.05, 10)):
    """
    Retrieves XML content over HTTP and extracts releases.
    Includes explicit connection and read timeouts.
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout connecting to upstream feed: {e}")
        raise FeedFetchError("Connection timeout while fetching feed") from e
    except requests.exceptions.SSLError as e:
        logger.error(f"SSL handshake or validation failed: {e}")
        raise FeedFetchError("SSL verification failed") from e
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Network connection failed: {e}")
        raise FeedFetchError("Network connection error") from e
    except requests.exceptions.HTTPError as e:
        logger.error(f"Upstream returned HTTP error {response.status_code}: {e}")
        raise FeedFetchError(f"HTTP error {response.status_code}") from e
    except requests.exceptions.RequestException as e:
        logger.error(f"Unexpected network error: {e}")
        raise FeedFetchError("Generic network error") from e

    # Parse using feedparser
    try:
        feed = feedparser.parse(response.text)
    except Exception as e:
        logger.error(f"feedparser crashed during parsing: {e}")
        raise FeedParseError("Failed to parse XML content") from e

    # Validate feed syntax. bozo=1 indicates malformed XML.
    if feed.get('bozo', 0) == 1:
        exc = feed.get('bozo_exception')
        # Check if exception represents a fatal XML structure syntax error
        if isinstance(exc, xml.sax.SAXParseException):
            logger.error(f"Fatal XML structural error: {exc}")
            raise FeedParseError("Malformed XML feed structure") from exc

    releases = []
    for entry in feed.entries:
        title = entry.get('title', 'No Title').strip()
        
        # Link fallback
        link = entry.get('link', '').strip()
        if not link:
            link = "https://cloud.google.com/bigquery/docs/release-notes"

        # Date normalization
        date_str = None
        struct_time = entry.get('updated_parsed') or entry.get('published_parsed')
        if struct_time:
            try:
                # time.struct_time contains UTC parameters
                dt = datetime(*struct_time[:6], tzinfo=timezone.utc)
                date_str = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            except Exception as e:
                logger.warning(f"Failed to format struct_time: {e}")

        # String parsing fallback if struct_time conversion fails
        if not date_str:
            raw_date = entry.get('updated') or entry.get('published') or entry.get('pubDate')
            date_str = parse_date_string(raw_date)

        # Final absolute fallback to current time to ensure feed resilience
        if not date_str:
            logger.warning(f"Could not parse date for '{title}'. Defaulting to current UTC.")
            date_str = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        # Content parsing (Atom content vs summary vs RSS description)
        content = ""
        if 'content' in entry and entry.content:
            content = entry.content[0].get('value', '')
        elif 'summary' in entry:
            content = entry.summary
        elif 'description' in entry:
            content = entry.description

        content = content.strip() if content else "No content available."

        releases.append({
            "title": title,
            "link": link,
            "date": date_str,
            "content": content
        })

    return releases

def get_releases(url):
    """
    Thread-safe interface returning release objects. Utilizes process-level
    caching and stale recovery during server downtime.
    """
    global _releases_cache
    now = time.time()
    
    # Serve cached data if within TTL
    if _releases_cache["data"] is not None and now < _releases_cache["last_fetched"] + CACHE_TTL:
        logger.debug("Serving from live cache.")
        return _releases_cache["data"]
        
    try:
        # Revalidate / Refresh cache
        logger.info("Cache expired or empty. Refreshing feed data.")
        fresh_data = fetch_and_parse_feed(url)
        _releases_cache["data"] = fresh_data
        _releases_cache["last_fetched"] = now
        return fresh_data
    except FeedError as e:
        # Feed downtime recovery: fallback to stale cache if available
        if _releases_cache["data"] is not None:
            logger.warning(f"Upstream update failed: {e}. Recovered using stale cache.")
            return _releases_cache["data"]
        # If cache is entirely empty, propagate the failure
        raise e
```

---

### 3.3 Flask Server Web API (`app.py`) Design
`app.py` acts as the thin controller exposing routing and converting exceptions raised by the parser into proper JSON error responses conforming to the specification contract.

```python
# app.py - Draft Code Structure

import logging
from flask import Flask, jsonify, render_template
import parser

app = Flask(__name__)

# Configure application-wide logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

FEED_URL = "https://docs.cloud.google.com/feeds/bigquery-release-notes.xml"

@app.route('/')
def index():
    """Serves the main single-page UI template."""
    return render_template('index.html')

@app.route('/api/releases')
def get_releases_api():
    """
    API endpoint serving formatted releases. Handles network or parsing failures
    gracefully, transforming them into JSON responses.
    """
    try:
        releases = parser.get_releases(FEED_URL)
        return jsonify(releases)
    except parser.FeedFetchError as e:
        logger.error(f"Failed to fetch feed: {e}")
        return jsonify({"error": "Failed to fetch or parse release notes feed"}), 502
    except parser.FeedParseError as e:
        logger.error(f"Failed to parse feed content: {e}")
        return jsonify({"error": "Failed to fetch or parse release notes feed"}), 502
    except Exception as e:
        # Catch-all for internal software faults
        logger.error(f"Unhandled app exception: {e}")
        return jsonify({"error": "Failed to fetch or parse release notes feed"}), 500

if __name__ == '__main__':
    # Default local configuration
    app.run(host='0.0.0.0', port=5000)
```

---

## 4. Edge Case Analysis & Mitigation

| Edge Case | Risk | Design Mitigation |
|---|---|---|
| **Feed Downtime / DNS Outages** | API responds with errors continuously, causing high frontend failure rates. | **Process Caching / Stale Fallback**: Cache results for 5 minutes. If a fetch fails during cache revalidation, return the stale cache instead of 502. |
| **Connection Timeout/Slow Network** | Long-hanging sockets starve Flask workers, causing latency spikes for all routes. | **Explicit Socket Timeouts**: Set `timeout=(3.05, 10)` in requests. Connect phase fails fast at 3.05s, read phase at 10s. |
| **SSL Handshake & Cert Failures** | Strict requests behavior raises `SSLError` blocking fetches during certificate rotation. | **Handled Exception Propagation**: Detect `SSLError`, map it to `FeedFetchError` and respond with `502 Bad Gateway` cleanly, logging the specific TLS diagnostics. |
| **Malformed XML Syntax** | Non-well-formed XML causes `feedparser` to return incomplete data or fail. | **bozo + SAX Exception Check**: Inspect `feed.bozo`. If `bozo == 1` and `bozo_exception` is a structural parse exception, raise `FeedParseError`. If it's a minor warning, extract data leniently. |
| **Timezone Variations** | Date representation strings in feed differ (e.g. UTC Z, offset timezone, or naive UTC). | **Double-Layer Parsing**: Prefer `updated_parsed` (always GMT). If unavailable, try string parse fallback (`fromisoformat` + `parsedate_to_datetime`) and enforce timezone conversion to UTC. |
| **Empty Upstream Feed** | An empty feed returns `200` but contains 0 items, leading to `IndexError` or crash. | **Safe Loop Guard**: Return an empty list `[]` instead of raising parsing errors if the feed contains no entries but is valid XML. |
| **Missing entry fields** | Missing `title`, `link`, or `content` in individual entries crashes serialization. | **Default Field Values**: Set fallback values like `"No Title"`, `"No content available"`, and feed main URL if fields are missing. |

---

## 5. Unit Test Suite Design

The unit test suite validates `parser.py` and `app.py` in isolation and integration. Mock responses are used to prevent external networking dependency (which is critical in `CODE_ONLY` mode).

### 5.1 Test Configuration Structure
A pytest module (`tests/test_parser.py`) should be created. It uses `unittest.mock.patch` to redirect `requests.get` to mock objects mimicking success and failure scenarios.

### 5.2 Unit Test Implementations

```python
# tests/test_parser.py - Proposed Implementation

import pytest
from unittest.mock import patch, MagicMock
import requests
import time
from datetime import datetime, timezone
import parser

# --- Test Mock Data ---

ATOM_FEED_SUCCESS = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>BigQuery Release Notes</title>
  <updated>2026-06-18T19:00:00Z</updated>
  <entry>
    <title>BigQuery features updated</title>
    <link href="https://cloud.google.com/bigquery/docs/release-notes#June_18_2026"/>
    <updated>2026-06-18T12:00:00-07:00</updated>
    <content type="html">BigQuery now supports new SQL features.</content>
  </entry>
</feed>
"""

RSS_FEED_SUCCESS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>BigQuery Release Notes</title>
    <link>https://cloud.google.com/bigquery/docs/release-notes</link>
    <item>
      <title>BigQuery features updated</title>
      <link>https://cloud.google.com/bigquery/docs/release-notes#June_18_2026</link>
      <pubDate>Thu, 18 Jun 2026 19:00:00 GMT</pubDate>
      <description>BigQuery now supports new SQL features.</description>
    </item>
  </channel>
</rss>
"""

MALFORMED_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>BigQuery Release Notes</title>
  <entry>
    <title>Truncated entry
"""

EMPTY_FEED = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Empty Feed</title>
</feed>
"""

# --- Parser Tests ---

@patch('requests.get')
def test_fetch_and_parse_atom_success(mock_get):
    """Verifies that a valid Atom feed with offset dates is correctly parsed and converted to UTC ISO 8601."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = ATOM_FEED_SUCCESS
    mock_get.return_value = mock_resp

    releases = parser.fetch_and_parse_feed("http://mock-feed")
    assert len(releases) == 1
    assert releases[0]['title'] == "BigQuery features updated"
    assert releases[0]['link'] == "https://cloud.google.com/bigquery/docs/release-notes#June_18_2026"
    assert releases[0]['date'] == "2026-06-18T19:00:00Z"  # -07:00 timezone offset correctly normalized to UTC Z
    assert releases[0]['content'] == "BigQuery now supports new SQL features."

@patch('requests.get')
def test_fetch_and_parse_rss_success(mock_get):
    """Verifies that a valid RSS feed with RFC 2822 dates parses correctly."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = RSS_FEED_SUCCESS
    mock_get.return_value = mock_resp

    releases = parser.fetch_and_parse_feed("http://mock-feed")
    assert len(releases) == 1
    assert releases[0]['title'] == "BigQuery features updated"
    assert releases[0]['link'] == "https://cloud.google.com/bigquery/docs/release-notes#June_18_2026"
    assert releases[0]['date'] == "2026-06-18T19:00:00Z"
    assert releases[0]['content'] == "BigQuery now supports new SQL features."

@patch('requests.get')
def test_fetch_timeout_exception(mock_get):
    """Verifies that requests timeout generates a FeedFetchError."""
    mock_get.side_effect = requests.exceptions.Timeout("Connect timeout")
    with pytest.raises(parser.FeedFetchError) as exc_info:
        parser.fetch_and_parse_feed("http://mock-feed")
    assert "timeout" in str(exc_info.value).lower()

@patch('requests.get')
def test_fetch_ssl_exception(mock_get):
    """Verifies that TLS cert failure generates a FeedFetchError."""
    mock_get.side_effect = requests.exceptions.SSLError("Verification failed")
    with pytest.raises(parser.FeedFetchError) as exc_info:
        parser.fetch_and_parse_feed("http://mock-feed")
    assert "ssl" in str(exc_info.value).lower()

@patch('requests.get')
def test_fetch_connection_exception(mock_get):
    """Verifies that connection drop generates a FeedFetchError."""
    mock_get.side_effect = requests.exceptions.ConnectionError("Connection reset")
    with pytest.raises(parser.FeedFetchError) as exc_info:
        parser.fetch_and_parse_feed("http://mock-feed")
    assert "connection" in str(exc_info.value).lower()

@patch('requests.get')
def test_fetch_http_error_propagation(mock_get):
    """Verifies that a 503 response propagates a FeedFetchError."""
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("503 Service Unavailable")
    mock_get.return_value = mock_resp

    with pytest.raises(parser.FeedFetchError) as exc_info:
        parser.fetch_and_parse_feed("http://mock-feed")
    assert "503" in str(exc_info.value)

@patch('requests.get')
def test_parse_malformed_xml_syntax_error(mock_get):
    """Verifies that unclosed tags and truncated XML structure raise a FeedParseError."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = MALFORMED_XML
    mock_get.return_value = mock_resp

    with pytest.raises(parser.FeedParseError):
        parser.fetch_and_parse_feed("http://mock-feed")

@patch('requests.get')
def test_parse_empty_feed(mock_get):
    """Verifies that a valid feed with no entries returns an empty list instead of crashing."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = EMPTY_FEED
    mock_get.return_value = mock_resp

    releases = parser.fetch_and_parse_feed("http://mock-feed")
    assert isinstance(releases, list)
    assert len(releases) == 0

def test_date_string_normalization():
    """Verifies internal date normalization for multiple timezone formats."""
    # UTC ISO 8601
    assert parser.parse_date_string("2026-06-18T19:00:00Z") == "2026-06-18T19:00:00Z"
    # Offset ISO 8601
    assert parser.parse_date_string("2026-06-18T12:00:00-07:00") == "2026-06-18T19:00:00Z"
    # RFC 2822
    assert parser.parse_date_string("Thu, 18 Jun 2026 19:00:00 GMT") == "2026-06-18T19:00:00Z"
    # Invalid dates
    assert parser.parse_date_string("not-a-date") is None

# --- Cache & Downtime Recovery Tests ---

@patch('parser.fetch_and_parse_feed')
def test_caching_and_expiration(mock_fetch):
    """Verifies that consecutive calls within the TTL window hit the in-memory cache, and expires appropriately."""
    # Reset cache state
    parser._releases_cache["data"] = None
    parser._releases_cache["last_fetched"] = 0

    mock_fetch.return_value = [{"title": "Cached Release", "link": "http://link", "date": "2026-06-18T19:00:00Z", "content": "Desc"}]
    
    # First invocation should fetch from source
    res1 = parser.get_releases("http://mock-feed")
    assert len(res1) == 1
    assert mock_fetch.call_count == 1

    # Second invocation within TTL should reuse cache
    res2 = parser.get_releases("http://mock-feed")
    assert res1 == res2
    assert mock_fetch.call_count == 1  # No additional network requests

    # Advance time mock past TTL (e.g. expire cache)
    with patch('time.time', return_value=time.time() + parser.CACHE_TTL + 10):
        # Third invocation should refresh cache
        parser.get_releases("http://mock-feed")
        assert mock_fetch.call_count == 2

@patch('parser.fetch_and_parse_feed')
def test_stale_cache_fallback_on_downtime(mock_fetch):
    """Verifies that if the feed fails during a refresh cycle, the parser returns stale cache instead of failing."""
    # Reset cache with historical valid data
    parser._releases_cache["data"] = [{"title": "Stale Title", "link": "http://stale", "date": "2026-06-18T19:00:00Z", "content": "Stale content"}]
    parser._releases_cache["last_fetched"] = time.time() - (parser.CACHE_TTL + 10)  # Expired

    # Mock fetch to raise a networking timeout
    mock_fetch.side_effect = parser.FeedFetchError("Connection timed out")

    # Should fall back to cached data and not raise error
    res = parser.get_releases("http://mock-feed")
    assert len(res) == 1
    assert res[0]["title"] == "Stale Title"
