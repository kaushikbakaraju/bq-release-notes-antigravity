# Backend Flask Parser Design Analysis

This document outlines the architectural design, implementation details, error handling strategies, and testing plans for the Backend Flask Parser milestone (M2) of the BigQuery Release Notes Web Application.

---

## 1. Architectural Architecture & Design

The backend consists of two key components:
1. **`parser.py`**: A dedicated parser utility module responsible for fetching the raw XML feed from Google Cloud, parsing the structured elements, extracting individual release items, normalizing their dates into ISO 8601 (UTC) format, and returning standard dictionaries.
2. **`app.py`**: A lightweight Flask web application that exposes the two main endpoints:
   - `GET /`: Serves the user interface HTML template (`templates/index.html`).
   - `GET /api/releases`: Serves the JSON-serialized release notes to the frontend.

Both modules are designed to run locally, operate statelessly, and communicate via structured JSON contracts.

### System Flow
```
[ User Browser ] 
       │ 
       ▼ (GET /api/releases)
 ┌───────────┐ 
 │  app.py   │ ◄─── Checks memory cache (TTL: 5 min)
 └─────┬─────┘
       │ (Cache Miss)
       ▼
 ┌───────────┐
 │ parser.py │ ◄─── Fetches XML from Google Feed (Timeout: 5s connection, 10s read)
 └─────┬─────┘
       │ (Parses XML, normalizes date to UTC, handles namespace)
       ▼
[ JSON Output ] ───► [ app.py ] ───► [ Cached & Returned to Browser ]
```

---

## 2. Component Detailed Design

### A. Parser Module (`parser.py`)

The parser module must be resilient to feed changes, namespacing variations, and date format inconsistencies. We use standard library modules (`xml.etree.ElementTree`, `datetime`, `email.utils`) to keep the application lightweight and minimize external dependencies.

#### Proposed `parser.py` Source Design

```python
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timezone
import email.utils
import logging

logger = logging.getLogger(__name__)

FEED_URL = "https://docs.cloud.google.com/feeds/bigquery-release-notes.xml"

class FeedParserError(Exception):
    """Base exception for feed parser errors."""
    pass

class FeedFetchError(FeedParserError):
    """Exception raised when fetching the feed fails."""
    pass

class FeedParseError(FeedParserError):
    """Exception raised when parsing the feed fails."""
    pass


def get_tag_local_name(tag: str) -> str:
    """Helper to extract tag name without namespace."""
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag


def parse_and_format_date(date_str: str) -> str:
    """
    Parse date from XML (Atom ISO 8601 or RSS RFC 2822/822) and convert to 
    ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ (UTC).
    """
    if not date_str:
        return ""
    
    clean_str = date_str.strip()

    # 1. Try ISO 8601 format (typically used in Atom feeds)
    try:
        # Pre-3.11 Python compatibility: replace 'Z' suffix with UTC offset '+00:00'
        if clean_str.endswith('Z'):
            iso_str = clean_str[:-1] + '+00:00'
        else:
            iso_str = clean_str
            
        dt = datetime.fromisoformat(iso_str)
        # Ensure it is timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        pass

    # 2. Try RFC 2822 format (typically used in RSS 2.0 feeds)
    try:
        dt = email.utils.parsedate_to_datetime(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    except (ValueError, TypeError):
        pass

    # Fallback to returning original trimmed string if unparseable
    logger.warning(f"Could not parse date format: {date_str}. Returning original.")
    return clean_str


def fetch_feed_xml(url: str = FEED_URL, timeout: float = 10.0) -> str:
    """
    Fetches XML feed from URL with timeouts and SSL error handling.
    """
    try:
        # Disable default proxy behavior if running in isolated test environments
        # Set a standard User-Agent to avoid blocking by cloud firewalls
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'BigQuery-Release-Notes-Parser/1.0'}
        )
        
        # Use a context for urllib connection
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
            
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP Error {e.code} when fetching feed: {e.reason}")
        raise FeedFetchError(f"HTTP Error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        # Distinguish SSL errors
        if isinstance(e.reason, ssl.SSLError):
            logger.error(f"SSL handshake error when fetching feed: {e.reason}")
            raise FeedFetchError(f"SSL verification failed: {e.reason}")
        logger.error(f"Network connection error when fetching feed: {e.reason}")
        raise FeedFetchError(f"Network error: {e.reason}")
    except Exception as e:
        logger.error(f"Unexpected error fetching feed: {e}")
        raise FeedFetchError(f"Fetch failure: {e}")


def parse_xml_feed(xml_content: str) -> list:
    """
    Namespace-agnostic parser that handles both Atom <feed> and RSS <rss> feeds.
    Returns list of release note dictionaries:
    [
        {"title": str, "link": str, "date": str, "content": str}, ...
    ]
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        logger.error(f"XML Parsing Error: {e}")
        raise FeedParseError(f"Malformed XML payload: {e}")

    releases = []
    items = []
    root_tag = get_tag_local_name(root.tag)

    # Detect feed standard (Atom vs. RSS)
    if root_tag == 'feed':
        # Atom standard: entries are direct children of feed
        for child in root:
            if get_tag_local_name(child.tag) == 'entry':
                items.append(child)
    elif root_tag == 'rss':
        # RSS standard: items are children of root -> channel
        channel = None
        for child in root:
            if get_tag_local_name(child.tag) == 'channel':
                channel = child
                break
        if channel is not None:
            for child in channel:
                if get_tag_local_name(child.tag) == 'item':
                    items.append(child)
    else:
        logger.warning(f"Unknown root feed tag: {root_tag}. Attempting recursive search for entries.")
        # Fallback recursive search for namespaced or custom nodes
        for node in root.iter():
            local_name = get_tag_local_name(node.tag)
            if local_name in ('entry', 'item'):
                items.append(node)

    # Process items namespace-agnostically
    for item in items:
        title = ""
        link = ""
        date_str = ""
        content = ""

        for child in item:
            local_name = get_tag_local_name(child.tag)
            if local_name == 'title':
                title = child.text or ""
            elif local_name == 'link':
                # Atom links are attributes: <link href="URL"/>
                # RSS links are element text: <link>URL</link>
                link = child.attrib.get('href', child.text or "")
            elif local_name in ('updated', 'published', 'pubDate'):
                date_str = child.text or ""
            elif local_name in ('content', 'summary', 'description'):
                content = child.text or ""

        formatted_date = parse_and_format_date(date_str)

        releases.append({
            "title": title.strip(),
            "link": link.strip(),
            "date": formatted_date,
            "content": content.strip()
        })

    return releases


def get_releases() -> list:
    """
    High-level orchestrator function to fetch and parse release notes.
    """
    xml_data = fetch_feed_xml()
    return parse_xml_feed(xml_data)
```

---

### B. Flask Server Module (`app.py`)

`app.py` serves the primary frontend page (`GET /`) and the API releases data (`GET /api/releases`). To ensure performance and server survivability, we design an in-memory TTL caching layer.

#### Caching Strategy (Survivability & Resilience)
Instead of fetching the Google feed synchronously on every API query (which is slow, risks rate limiting, and leaves us vulnerable to upstream feed outages), we implement a **Stale-While-Revalidate (SWR)** style cache fallback:
1. Cache entries have a TTL (e.g. 5 minutes).
2. If cache hit and valid: return cached list instantly.
3. If cache missed/expired: attempt to fetch from Google.
4. If fetch succeeds: update cache and return.
5. **Critical Outage Handling**: If fetch fails (feed down, timeout, SSL error) and we have expired cache data in memory, **return the expired cache data** with a logging warning rather than throwing a 502/500 error to the user. This ensures maximum service availability.

#### Proposed `app.py` Source Design

```python
from flask import Flask, jsonify, render_template, request
import parser
import time
import logging

# Configure logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Simple in-memory cache configuration
class ReleaseCache:
    def __init__(self, ttl_seconds=300):
        self.ttl = ttl_seconds
        self.data = None
        self.last_updated = 0

    def get(self):
        """Returns cache content if it is still within the TTL."""
        if self.data is not None and (time.time() - self.last_updated) < self.ttl:
            return self.data
        return None

    def set(self, data):
        self.data = data
        self.last_updated = time.time()

    def get_expired(self):
        """Returns cache data regardless of expiration status."""
        return self.data

cache = ReleaseCache(ttl_seconds=300)  # 5 minutes TTL


@app.route('/', methods=['GET'])
def index():
    """Serves the frontend application homepage."""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Template rendering failed: {e}")
        return "Internal Server Error", 500


@app.route('/api/releases', methods=['GET'])
def get_releases_api():
    """
    API endpoint returning list of releases.
    Handles caching, error scenarios, and query overrides.
    """
    # Allow client to force cache bypass via ?refresh=true (e.g., from UI refresh button)
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'

    if not force_refresh:
        cached_data = cache.get()
        if cached_data is not None:
            logger.info("Serving releases from active cache.")
            return jsonify(cached_data)

    try:
        logger.info("Fetching and parsing fresh release notes feed.")
        releases = parser.get_releases()
        cache.set(releases)
        return jsonify(releases)
        
    except parser.FeedParserError as e:
        logger.error(f"Parser error while refreshing feed: {e}")
        
        # Fallback to expired cache if available during downtime
        expired_data = cache.get_expired()
        if expired_data is not None:
            logger.warning("Upstream feed is down. Serving stale cached data as fallback.")
            return jsonify(expired_data)
            
        # Standard error return contract
        return jsonify({"error": "Failed to fetch or parse release notes feed"}), 502
        
    except Exception as e:
        logger.error(f"Unexpected error in API endpoint: {e}")
        
        expired_data = cache.get_expired()
        if expired_data is not None:
            logger.warning("Unexpected server error. Serving stale cached data as fallback.")
            return jsonify(expired_data)
            
        return jsonify({"error": "Failed to fetch or parse release notes feed"}), 500


if __name__ == '__main__':
    # Default to port 5000 in accordance with standard Flask deployments
    app.run(host='0.0.0.0', port=5000, debug=False)
```

---

## 3. Critical Edge Cases & Robustness

| Edge Case | Problem | Mitigation Strategy |
|-----------|---------|---------------------|
| **Feed Timezone Differences** | Feed entries might mix UTC (`Z`), offsets (e.g. `-07:00`), or lack zone flags entirely. | 1. Parse datetime with Python standard ISO / RFC utilities.<br>2. Convert all datetimes to UTC timezone-aware objects.<br>3. Format explicitly to `YYYY-MM-DDTHH:MM:SSZ`. |
| **Feed Formatting Changes** | Feed namespaces can vary (`atom`, `rss`, `ns0`, or none) or elements might use tags like `<description>` instead of `<content>`. | 1. Implement a **Namespace-Agnostic** parser that inspects tags by local names (splitting out namespaces).<br>2. Support fallbacks for key tags: `updated`/`published`/`pubDate`, and `content`/`summary`/`description`. |
| **Connection Timeout** | Slow network requests will block the Flask server worker indefinitely if no timeout is defined. | 1. Force a strict timeout limit of `10.0` seconds on all HTTP network actions.<br>2. Gracefully raise a `FeedFetchError` mapped to HTTP 502 instead of timing out the user request. |
| **Upstream Outages** | Feed server down or returning 500/503. | 1. Utilize the `ReleaseCache` in-memory store.<br>2. Serve the last known good stale data if available during failures.<br>3. Return HTTP 502 with error JSON only if cache is empty. |
| **Malformed XML Payload** | Incomplete or corrupted feed downloads causing parsing failure. | 1. Wrap the element tree parser in a strict `try-except ET.ParseError` handler.<br>2. Log the XML format failure details and raise `FeedParseError` to report 502 safely. |
| **SSL Handshake Failures** | Expired, self-signed, or invalid certificate on the feed host. | 1. Catch `ssl.SSLError` inside urllib URL resolution.<br>2. Log details for developers to debug potential MITM or configuration issues.<br>3. Return structured error JSON to client. |

---

## 4. Test Strategy and Unit Test Design

We will write unit tests using `pytest`. The tests will cover the parser, XML transformations, date normalization, Flask HTTP routing, error mappings, and cache fallbacks. All external requests are mocked to ensure reliable test execution under CODE_ONLY isolation.

### Proposed Test Module (`tests/test_backend.py`)

```python
import pytest
from unittest.mock import patch, MagicMock
import urllib.error
import ssl
from app import app, cache
import parser

# --- 1. Mock XML Payloads ---

MOCK_ATOM_VALID = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>BigQuery release notes</title>
  <entry>
    <title>BigQuery ML improvements</title>
    <link href="https://cloud.google.com/bigquery/docs/release-notes#June_20_2026"/>
    <updated>2026-06-20T12:00:00Z</updated>
    <content type="html">&lt;p&gt;Model execution optimized.&lt;/p&gt;</content>
  </entry>
  <entry>
    <title>New SQL functions</title>
    <link href="https://cloud.google.com/bigquery/docs/release-notes#June_15_2026"/>
    <published>2026-06-15T09:30:00-07:00</published>
    <summary>Added new array helper functions.</summary>
  </entry>
</feed>
"""

MOCK_RSS_VALID = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>BigQuery release notes</title>
    <item>
      <title>Storage pricing changes</title>
      <link>https://cloud.google.com/bigquery/docs/release-notes#pricing</link>
      <pubDate>Mon, 01 Jun 2026 14:00:00 GMT</pubDate>
      <description>Updated pricing tiers.</description>
    </item>
  </channel>
</rss>
"""

MOCK_MALFORMED_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Malformed Feed
  <entry>
    <title>Broken Entry</title>
"""


# --- 2. Parser Unit Tests ---

def test_parse_valid_atom_feed():
    """Verifies parsing of standard Atom XML feeds, including timezone offsets."""
    releases = parser.parse_xml_feed(MOCK_ATOM_VALID)
    assert len(releases) == 2
    
    # Check first item (UTC)
    assert releases[0]['title'] == "BigQuery ML improvements"
    assert releases[0]['link'] == "https://cloud.google.com/bigquery/docs/release-notes#June_20_2026"
    assert releases[0]['date'] == "2026-06-20T12:00:00Z"
    assert releases[0]['content'] == "<p>Model execution optimized.</p>"
    
    # Check second item (PDT -07:00 conversion to UTC)
    assert releases[1]['title'] == "New SQL functions"
    # -07:00 offset translates to +7 hours in UTC (09:30 -> 16:30)
    assert releases[1]['date'] == "2026-06-15T16:30:00Z"
    assert releases[1]['content'] == "Added new array helper functions."


def test_parse_valid_rss_feed():
    """Verifies namespace-agnostic parsing of standard RSS 2.0 feeds."""
    releases = parser.parse_xml_feed(MOCK_RSS_VALID)
    assert len(releases) == 1
    assert releases[0]['title'] == "Storage pricing changes"
    assert releases[0]['link'] == "https://cloud.google.com/bigquery/docs/release-notes#pricing"
    assert releases[0]['date'] == "2026-06-01T14:00:00Z"
    assert releases[0]['content'] == "Updated pricing tiers."


def test_parse_malformed_xml():
    """Verifies that malformed XML causes the parser to raise FeedParseError."""
    with pytest.raises(parser.FeedParseError):
        parser.parse_xml_feed(MOCK_MALFORMED_XML)


def test_date_parsing_edge_cases():
    """Tests various parsing edge cases like missing zones or empty values."""
    # Empty date returns empty
    assert parser.parse_and_format_date("") == ""
    assert parser.parse_and_format_date(None) == ""
    
    # Timezone-naive date defaults to UTC
    assert parser.parse_and_format_date("2026-06-20T12:00:00") == "2026-06-20T12:00:00Z"
    
    # Unparseable date strings return original string trimmed
    assert parser.parse_and_format_date("invalid-date-format") == "invalid-date-format"


@patch('urllib.request.urlopen')
def test_fetch_feed_network_error(mock_urlopen):
    """Mocks network error to verify FetchError is raised."""
    mock_urlopen.side_effect = urllib.error.URLError("DNS Resolution Failed")
    with pytest.raises(parser.FeedFetchError):
        parser.fetch_feed_xml()


@patch('urllib.request.urlopen')
def test_fetch_feed_ssl_error(mock_urlopen):
    """Mocks SSL certification error to verify SSL exception propagation."""
    ssl_err = ssl.SSLError("SSL: CERTIFICATE_VERIFY_FAILED")
    mock_urlopen.side_effect = urllib.error.URLError(ssl_err)
    with pytest.raises(parser.FeedFetchError) as exc_info:
        parser.fetch_feed_xml()
    assert "SSL" in str(exc_info.value)


# --- 3. Flask Server & Cache Tests ---

@pytest.fixture
def client():
    app.config['TESTING'] = True
    # Clear cache before each test
    cache.invalidate()
    with app.test_client() as client:
        yield client


def test_serve_frontend(client):
    """Verifies that the index route correctly serves HTML templates."""
    response = client.get('/')
    assert response.status_code == 200
    # Templates will be fully created in M3, but this asserts basic loading
    assert response.data is not None


@patch('parser.fetch_feed_xml')
def test_api_releases_success(mock_fetch, client):
    """Verifies that the releases API returns formatted JSON and caches the result."""
    mock_fetch.return_value = MOCK_ATOM_VALID
    
    response = client.get('/api/releases')
    assert response.status_code == 200
    data = response.json
    assert len(data) == 2
    assert data[0]['title'] == "BigQuery ML improvements"
    
    # Verify cache is populated
    assert cache.data is not None
    assert len(cache.data) == 2
    
    # Verify subsequent request uses cache without calling network fetch again
    mock_fetch.reset_mock()
    response2 = client.get('/api/releases')
    assert response2.status_code == 200
    mock_fetch.assert_not_called()


@patch('parser.fetch_feed_xml')
def test_api_releases_failure_no_cache(mock_fetch, client):
    """Verifies 502 code when network fails and no cached copy exists."""
    mock_fetch.side_effect = parser.FeedFetchError("Connection Timed Out")
    
    response = client.get('/api/releases')
    assert response.status_code == 502
    assert response.json == {"error": "Failed to fetch or parse release notes feed"}


@patch('parser.fetch_feed_xml')
def test_api_releases_failure_with_stale_cache(mock_fetch, client):
    """Verifies stale cache is served as fallback if upstream is down."""
    # 1. Warm cache
    mock_fetch.return_value = MOCK_ATOM_VALID
    client.get('/api/releases')
    assert cache.data is not None
    
    # 2. Simulate upstream failure and force refresh
    mock_fetch.side_effect = parser.FeedFetchError("Connection Timed Out")
    response = client.get('/api/releases?refresh=true')
    
    # Should serve stale cache instead of failing with 502
    assert response.status_code == 200
    data = response.json
    assert len(data) == 2
    assert data[0]['title'] == "BigQuery ML improvements"
```

---

## 5. Directory Layout & Workspace Compliance

As required by the workflow rules, the backend implementation and tests will strictly adhere to the project workspace configuration guidelines. No implementation code or python scripts will be committed to the `.agents/` metadata subdirectory.

### Target Directory Layout
```
├── app.py                     # Flask entry point
├── parser.py                  # Custom feed parser library
├── requirements.txt           # Python application dependencies
├── run.sh                     # Local startup script
├── templates/
│   └── index.html             # Homepage template placeholder
├── static/
│   ├── app.js                 # Javascript AJAX and Twitter intents
│   └── styles.css             # Theme stylesheet
└── tests/
    ├── conftest.py            # pytest configuration and mock server setup
    └── test_backend.py        # Complete unit testing suite for parser/routes
```

---

## 6. Execution Instructions for the Implementer

1. **Dependencies**: Create a virtual environment using `python3 -m venv venv` and install the package requirements via `pip install -r requirements.txt`.
2. **Launch Application**: Execute `./run.sh` to boot up the Flask web server on port 5000.
3. **Run Verification Tests**: Execute `pytest tests/test_backend.py -v --cov` to run unit test suites and verify logic code coverage thresholds.
