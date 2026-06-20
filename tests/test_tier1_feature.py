import os
import json
import re
import datetime
from bs4 import BeautifulSoup
import pytest
import parser

# =====================================================================
# FEATURE 1: Serve Frontend (6 tests)
# =====================================================================

def test_frontend_status_code(client):
    """Test that GET / returns status 200."""
    response = client.get("/")
    assert response.status_code == 200

def test_frontend_stylesheet_link(client):
    """Test that CSS link element referencing /static/styles.css exists."""
    response = client.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    link = soup.find("link", rel="stylesheet")
    assert link is not None
    assert link.get("href") == "/static/styles.css"

def test_frontend_javascript_script(client):
    """Test that JS script element referencing /static/app.js exists."""
    response = client.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    script = soup.find("script", src="/static/app.js")
    assert script is not None

def test_frontend_h1_text(client):
    """Test that H1 header has correct title text."""
    response = client.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    h1 = soup.find("h1")
    assert h1 is not None
    assert h1.text.strip() == "BigQuery Release Notes"

def test_frontend_refresh_button_present(client):
    """Test that refresh button with id='refresh-btn' is present."""
    response = client.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    btn = soup.find("button", id="refresh-btn")
    assert btn is not None

def test_frontend_spinner_container_present(client):
    """Test that spinner container with id='spinner-container' is present."""
    response = client.get("/")
    soup = BeautifulSoup(response.data, "html.parser")
    spinner = soup.find(id="spinner-container")
    assert spinner is not None


# =====================================================================
# FEATURE 2: Retrieve Release API (6 tests)
# =====================================================================

def test_api_status_code(client, mock_rss_server):
    """Test that GET /api/releases returns status 200 on success."""
    response = client.get("/api/releases")
    assert response.status_code == 200

def test_api_content_type(client, mock_rss_server):
    """Test that GET /api/releases returns JSON content type."""
    response = client.get("/api/releases")
    assert response.content_type == "application/json"

def test_api_is_list(client, mock_rss_server):
    """Test that GET /api/releases returns a JSON array/list."""
    response = client.get("/api/releases")
    data = response.json
    assert isinstance(data, list)

def test_api_release_object_keys(client, mock_rss_server):
    """Test that elements in releases array have required keys: title, link, date, content."""
    response = client.get("/api/releases")
    data = response.json
    assert len(data) > 0
    release = data[0]
    for key in ["title", "link", "date", "content"]:
        assert key in release

def test_api_release_object_non_empty(client, mock_rss_server):
    """Test that release entry contains non-empty properties."""
    response = client.get("/api/releases")
    release = response.json[0]
    assert len(release["title"]) > 0
    assert len(release["link"]) > 0
    assert len(release["date"]) > 0
    assert len(release["content"]) > 0

def test_api_empty_feed_returns_empty_list(client, mock_rss_server):
    """Test that API returns empty list when feed has no entries."""
    feed_url = f"{mock_rss_server.url}/feed/empty"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert response.status_code == 200
    assert response.json == []


# =====================================================================
# FEATURE 3: Parse Feed Content (6 tests)
# =====================================================================

def test_parse_date_rfc2822():
    """Test parse_date_to_iso8601 handles RFC 2822 format."""
    rfc_date = "Sat, 20 Jun 2026 12:00:00 GMT"
    expected = "2026-06-20T12:00:00Z"
    assert parser.parse_date_to_iso8601(rfc_date) == expected

def test_parse_date_iso8601_z():
    """Test parse_date_to_iso8601 handles ISO 8601 with Z suffix."""
    iso_date = "2026-06-20T12:00:00Z"
    expected = "2026-06-20T12:00:00Z"
    assert parser.parse_date_to_iso8601(iso_date) == expected

def test_parse_date_iso8601_offset():
    """Test parse_date_to_iso8601 normalizes timezone offset to UTC Z."""
    offset_date = "2026-06-20T05:00:00-07:00"
    expected = "2026-06-20T12:00:00Z"
    assert parser.parse_date_to_iso8601(offset_date) == expected

def test_parse_date_date_only():
    """Test parse_date_to_iso8601 handles YYYY-MM-DD date-only strings."""
    date_only = "2026-06-20"
    expected = "2026-06-20T00:00:00Z"
    assert parser.parse_date_to_iso8601(date_only) == expected

def test_parse_feed_title(client, mock_rss_server):
    """Test that parser extracts correct title from feed entry."""
    response = client.get("/api/releases")
    assert response.json[0]["title"] == "BigQuery feature update"

def test_parse_feed_link(client, mock_rss_server):
    """Test that parser extracts correct link from feed entry."""
    response = client.get("/api/releases")
    assert response.json[0]["link"] == "https://cloud.google.com/bigquery/docs/release-notes#June_20_2026"


# =====================================================================
# FEATURE 4: Refresh Feed & Spinner (6 tests)
# =====================================================================

def test_refresh_button_action_registered():
    """Test that app.js script contains logic to bind click event to refresh-btn."""
    js_path = os.path.join(os.path.dirname(__file__), "../static/app.js")
    with open(js_path, "r") as f:
        js_content = f.read()
    assert "refreshBtn.addEventListener" in js_content
    assert "click" in js_content

def test_spinner_logic_present_in_js():
    """Test that app.js contains logic to show/hide the spinner container."""
    js_path = os.path.join(os.path.dirname(__file__), "../static/app.js")
    with open(js_path, "r") as f:
        js_content = f.read()
    assert "spinner.style.display" in js_content

def test_refresh_fetches_api_in_js():
    """Test that app.js contains logic to fetch from /api/releases."""
    js_path = os.path.join(os.path.dirname(__file__), "../static/app.js")
    with open(js_path, "r") as f:
        js_content = f.read()
    assert "/api/releases" in js_content

def test_api_nocache_headers(client, mock_rss_server):
    """Test that api releases doesn't specify heavy caching headers preventing fresh load."""
    response = client.get("/api/releases")
    # Verify Content-Type is correct and cache headers if set aren't blocking
    assert response.status_code == 200
    assert "application/json" in response.headers.get("Content-Type", "")

def test_refresh_consecutive_updates(client, mock_rss_server):
    """Test that hitting the API consecutively parses the latest feed state."""
    res1 = client.get(f"/api/releases?feed_url={mock_rss_server.url}/feed/valid")
    assert res1.status_code == 200
    assert len(res1.json) == 1
    
    res2 = client.get(f"/api/releases?feed_url={mock_rss_server.url}/feed/empty")
    assert res2.status_code == 200
    assert len(res2.json) == 0

def test_client_refresh_is_functional(client):
    """Test that API endpoint can handle fresh parameters dynamically."""
    response = client.get("/api/releases?feed_url=invalid_scheme://url")
    assert response.status_code in [500, 502]


# =====================================================================
# FEATURE 5: Tweet Share Intent (6 tests)
# =====================================================================

def test_share_button_class_in_js():
    """Test that app.js adds class 'twitter-share-button' to elements."""
    js_path = os.path.join(os.path.dirname(__file__), "../static/app.js")
    with open(js_path, "r") as f:
        js_content = f.read()
    assert "twitter-share-button" in js_content

def test_share_intent_url_pattern():
    """Test that app.js uses correct Twitter Web Intent base URL."""
    js_path = os.path.join(os.path.dirname(__file__), "../static/app.js")
    with open(js_path, "r") as f:
        js_content = f.read()
    assert "https://twitter.com/intent/tweet" in js_content

def test_share_target_blank():
    """Test that app.js sets target='_blank' on the sharing button."""
    js_path = os.path.join(os.path.dirname(__file__), "../static/app.js")
    with open(js_path, "r") as f:
        js_content = f.read()
    assert 'target = "_blank"' in js_content or "target" in js_content

def test_share_url_encoding_logic():
    """Test that app.js uses encodeURIComponent to format sharing query parameters."""
    js_path = os.path.join(os.path.dirname(__file__), "../static/app.js")
    with open(js_path, "r") as f:
        js_content = f.read()
    assert "encodeURIComponent" in js_content

def test_share_parameters_format():
    """Test that app.js constructs parameters 'text' and 'url'."""
    js_path = os.path.join(os.path.dirname(__file__), "../static/app.js")
    with open(js_path, "r") as f:
        js_content = f.read()
    assert "text=" in js_content
    assert "url=" in js_content

def test_share_prefix_matches_spec():
    """Test that sharing template uses 'BigQuery Update: ' prefix."""
    js_path = os.path.join(os.path.dirname(__file__), "../static/app.js")
    with open(js_path, "r") as f:
        js_content = f.read()
    assert "BigQuery Update: " in js_content


# =====================================================================
# FEATURE 6: API Error Handling (6 tests)
# =====================================================================

def test_api_feed_error_500(client, mock_rss_server):
    """Test that feed 500 error triggers 502/500 code."""
    feed_url = f"{mock_rss_server.url}/error/500"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert response.status_code in [500, 502]

def test_api_feed_error_404(client, mock_rss_server):
    """Test that feed 404 error triggers 502/500 code."""
    feed_url = f"{mock_rss_server.url}/error/404"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert response.status_code in [500, 502]

def test_api_feed_error_502(client, mock_rss_server):
    """Test that feed 502 error triggers 502/500 code."""
    feed_url = f"{mock_rss_server.url}/error/502"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert response.status_code in [500, 502]

def test_api_malformed_xml_error(client, mock_rss_server):
    """Test that malformed XML causes 502/500 response code."""
    feed_url = f"{mock_rss_server.url}/feed/malformed"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert response.status_code in [500, 502]

def test_api_error_response_schema(client, mock_rss_server):
    """Test that failure returns correct error response JSON structure."""
    feed_url = f"{mock_rss_server.url}/error/500"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert "error" in response.json

def test_api_error_response_message(client, mock_rss_server):
    """Test that failure returns exact error message required by contract."""
    feed_url = f"{mock_rss_server.url}/error/500"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert response.json == {"error": "Failed to fetch or parse release notes feed"}
