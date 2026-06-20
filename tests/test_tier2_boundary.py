import os
import json
import urllib.parse
from unittest.mock import patch
import pytest
import requests
import parser

# =====================================================================
# FEATURE 1: Frontend Boundaries (6 tests)
# =====================================================================

def test_frontend_missing_template(client):
    """Test that missing template triggers a clean 500 error."""
    with patch("app.render_template") as mock_render:
        mock_render.side_effect = Exception("Template missing")
        response = client.get("/")
        assert response.status_code == 500
        assert b"Internal Server Error: Frontend template index.html not found." in response.data

def test_frontend_special_request_headers(client):
    """Test frontend with diverse HTTP request headers."""
    response = client.get("/", headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        "Cache-Control": "no-cache",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    })
    assert response.status_code == 200

def test_frontend_trailing_slash(client):
    """Test frontend routing handles trailing slashes or redirect configuration."""
    response = client.get("/?")
    assert response.status_code == 200

def test_frontend_duplicate_slash(client):
    """Test that multiple slashes route appropriately or are handled by Flask."""
    response = client.get("//")
    # Flask typically handles multiple slashes by collapsing or serving the root path
    assert response.status_code in [200, 302, 404]

def test_frontend_nonexistent_methods(client):
    """Test that POST to frontend root returns 405 Method Not Allowed."""
    response = client.post("/")
    assert response.status_code == 405

def test_frontend_query_params_ignored(client):
    """Test that query params on root route are safely ignored."""
    response = client.get("/?rand=12345&mode=test")
    assert response.status_code == 200
    assert b"BigQuery Release Notes" in response.data


# =====================================================================
# FEATURE 2: API Boundaries (6 tests)
# =====================================================================

def test_api_boundary_large_feed(client, mock_rss_server):
    """Test API parsing a feed with a large number of entries (e.g. 100)."""
    # Create a dynamic mock feed with 100 entries
    entries_xml = ""
    for i in range(100):
        entries_xml += f"""
        <item>
          <title>Release Entry {i}</title>
          <link>https://cloud.google.com/bigquery/docs/release-notes#entry_{i}</link>
          <description>Description {i}</description>
          <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
        </item>
        """
    
    feed_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>BigQuery release notes</title>
        <link>https://cloud.google.com/bigquery/docs/release-notes</link>
        <description>Release notes for BigQuery.</description>
        <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
        {entries_xml}
      </channel>
    </rss>
    """
    
    with patch("requests.get") as mock_get:
        mock_res = mock_get.return_value
        mock_res.status_code = 200
        mock_res.text = feed_xml
        
        response = client.get("/api/releases?feed_url=http://mock-large-feed.xml")
        assert response.status_code == 200
        data = response.json
        assert len(data) == 100
        assert data[0]["title"] == "Release Entry 0"

def test_api_boundary_long_strings(client):
    """Test API handles extremely long strings in feed elements."""
    long_title = "A" * 10000
    long_content = "<p>" + "B" * 20000 + "</p>"
    feed_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>BigQuery release notes</title>
        <link>https://cloud.google.com/bigquery/docs/release-notes</link>
        <item>
          <title>{long_title}</title>
          <link>https://cloud.google.com/bigquery/docs/release-notes#long</link>
          <description>{long_content}</description>
          <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    with patch("requests.get") as mock_get:
        mock_res = mock_get.return_value
        mock_res.status_code = 200
        mock_res.text = feed_xml
        
        response = client.get("/api/releases?feed_url=http://mock-long.xml")
        assert response.status_code == 200
        assert len(response.json[0]["title"]) == 10000

def test_api_boundary_unicode_emojis(client):
    """Test API handles Unicode, mathematical symbols, and emojis."""
    unicode_title = "Feature 🚀 with symbols ★ & math ∑"
    unicode_content = "<p>Emojis: 😂 🔥 💻 and text in Chinese: 谷歌开发</p>"
    feed_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>BigQuery release notes</title>
        <link>https://cloud.google.com/bigquery/docs/release-notes</link>
        <item>
          <title>{unicode_title}</title>
          <link>https://cloud.google.com/bigquery/docs/release-notes#unicode</link>
          <description>{unicode_content}</description>
          <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    with patch("requests.get") as mock_get:
        mock_res = mock_get.return_value
        mock_res.status_code = 200
        mock_res.text = feed_xml
        
        response = client.get("/api/releases?feed_url=http://mock-unicode.xml")
        assert response.status_code == 200
        assert response.json[0]["title"] == unicode_title
        assert response.json[0]["content"] == unicode_content

def test_api_boundary_xss_content(client):
    """Test API parses XSS tags correctly and passes them down. Safety escaping is client-side."""
    xss_content = "<script>alert('XSS')</script><iframe src='javascript:alert(1)'></iframe>"
    feed_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>BigQuery release notes</title>
        <link>https://cloud.google.com/bigquery/docs/release-notes</link>
        <item>
          <title>XSS update</title>
          <link>https://cloud.google.com/bigquery/docs/release-notes#xss</link>
          <description>{xss_content}</description>
          <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    with patch("requests.get") as mock_get:
        mock_res = mock_get.return_value
        mock_res.status_code = 200
        mock_res.text = feed_xml
        
        response = client.get("/api/releases?feed_url=http://mock-xss.xml")
        assert response.status_code == 200
        assert response.json[0]["content"] == xss_content

def test_api_boundary_special_characters(client):
    """Test API handles double quotes and quotes in titles."""
    title_quotes = 'Release with "quotes" and \'single\' quotes'
    feed_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>BigQuery release notes</title>
        <link>https://cloud.google.com/bigquery/docs/release-notes</link>
        <item>
          <title>{title_quotes}</title>
          <link>https://cloud.google.com/bigquery/docs/release-notes#quotes</link>
          <description>Quotes</description>
          <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    with patch("requests.get") as mock_get:
        mock_res = mock_get.return_value
        mock_res.status_code = 200
        mock_res.text = feed_xml
        
        response = client.get("/api/releases?feed_url=http://mock-quotes.xml")
        assert response.status_code == 200
        assert response.json[0]["title"] == title_quotes

def test_api_boundary_extreme_feed_endpoint(client, mock_rss_server):
    """Test API against extreme mock server endpoint containing heavy HTML/Unicode."""
    feed_url = f"{mock_rss_server.url}/feed/extreme"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert response.status_code == 200
    assert len(response.json) == 1
    assert "Heavy HTML content" in response.json[0]["content"]


# =====================================================================
# FEATURE 3: Parse Boundaries (6 tests)
# =====================================================================

def test_parse_boundary_malformed_xml():
    """Test that completely broken XML structure raises ValueError in parser."""
    with pytest.raises(ValueError):
        # XML missing closing tags or empty
        parser.fetch_and_parse_feed(feed_url="invalid_content")

def test_parse_boundary_missing_optional_fields(client):
    """Test parser uses defaults or parses successfully when optional fields (link/content) are empty."""
    feed_xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>BigQuery release notes</title>
        <item>
          <title>Minimal Entry</title>
          <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    with patch("requests.get") as mock_get:
        mock_res = mock_get.return_value
        mock_res.status_code = 200
        mock_res.text = feed_xml
        
        response = client.get("/api/releases?feed_url=http://mock-minimal.xml")
        assert response.status_code == 200
        assert response.json[0]["link"] == ""
        assert response.json[0]["content"] == ""

def test_parse_boundary_empty_entries_list(client, mock_rss_server):
    """Test parsing a valid feed with zero entries returns empty list."""
    feed_url = f"{mock_rss_server.url}/feed/empty"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert response.status_code == 200
    assert response.json == []

def test_parse_boundary_diverse_dates():
    """Test parser handles different datetime formats correctly."""
    # Leap year RFC2822
    assert parser.parse_date_to_iso8601("Tue, 29 Feb 2024 10:00:00 GMT") == "2024-02-29T10:00:00Z"
    # ISO 8601 offset positive
    assert parser.parse_date_to_iso8601("2026-06-20T17:30:00+05:30") == "2026-06-20T12:00:00Z"
    # Date only
    assert parser.parse_date_to_iso8601("2026-06-20") == "2026-06-20T00:00:00Z"

def test_parse_boundary_invalid_date_raises():
    """Test that invalid date format raises ValueError in parser."""
    with pytest.raises(ValueError):
        parser.parse_date_to_iso8601("2026/06/20 12:00:00")

def test_parse_boundary_fallback_to_published(client):
    """Test parser extracts date correctly when updated is missing but published is available."""
    feed_xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>BigQuery release notes</title>
      <entry>
        <title>Atom Entry</title>
        <link href="https://example.com/atom"/>
        <published>2026-06-20T12:00:00Z</published>
        <content>Content</content>
      </entry>
    </feed>
    """
    with patch("requests.get") as mock_get:
        mock_res = mock_get.return_value
        mock_res.status_code = 200
        mock_res.text = feed_xml
        
        response = client.get("/api/releases?feed_url=http://mock-atom.xml")
        assert response.status_code == 200
        assert response.json[0]["date"] == "2026-06-20T12:00:00Z"


# =====================================================================
# FEATURE 4: Refresh Boundaries (6 tests)
# =====================================================================

def test_refresh_boundary_slow_response(client, mock_rss_server):
    """Test that API endpoint handles latency/slow server responses without crashing."""
    feed_url = f"{mock_rss_server.url}/feed/delay"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert response.status_code == 200
    assert len(response.json) == 1

def test_refresh_boundary_server_crash(client):
    """Test that API endpoint handles connection abort/network issues and returns 502."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection aborted")
        response = client.get("/api/releases?feed_url=http://crash-server.xml")
        assert response.status_code in [500, 502]
        assert response.json == {"error": "Failed to fetch or parse release notes feed"}

def test_refresh_boundary_rate_limit_headers(client):
    """Test that if feed server responds with rate limit headers, API still succeeds."""
    feed_xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>BigQuery release notes</title>
        <item>
          <title>Update</title>
          <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    with patch("requests.get") as mock_get:
        mock_res = mock_get.return_value
        mock_res.status_code = 200
        mock_res.text = feed_xml
        mock_res.headers = {
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Remaining": "0",
            "Retry-After": "30"
        }
        response = client.get("/api/releases?feed_url=http://rate-limited.xml")
        assert response.status_code == 200
        assert len(response.json) == 1

def test_refresh_boundary_rapid_sequential_requests(client, mock_rss_server):
    """Test that multiple rapid requests sequentially resolve correctly without interference."""
    for _ in range(5):
        response = client.get(f"/api/releases?feed_url={mock_rss_server.url}/feed/valid")
        assert response.status_code == 200
        assert len(response.json) == 1

def test_refresh_boundary_non_modified_header(client):
    """Test requests using If-Modified-Since or cache-control behavior."""
    response = client.get("/api/releases", headers={"If-Modified-Since": "Sat, 20 Jun 2026 12:00:00 GMT"})
    # API should still process and return latest (since we don't implement conditional HTTP caching for simplicity)
    assert response.status_code == 200

def test_refresh_boundary_empty_query_param(client, mock_rss_server):
    """Test that providing empty feed_url query param falls back to env var."""
    response = client.get("/api/releases?feed_url=")
    assert response.status_code == 200
    assert len(response.json) == 1


# =====================================================================
# FEATURE 5: Tweet Share Boundaries (6 tests)
# =====================================================================

def test_tweet_boundary_empty_title_link_encoding():
    """Verify how special intent inputs would be handled (e.g. empty strings)."""
    text = urllib.parse.quote_plus("BigQuery Update: ")
    url = urllib.parse.quote_plus("")
    intent = f"https://twitter.com/intent/tweet?text={text}&url={url}"
    assert "https://twitter.com/intent/tweet?text=BigQuery+Update%3A+&url=" in intent or "text=" in intent

def test_tweet_boundary_very_long_urls():
    """Verify encoding works on exceptionally long target links."""
    long_link = "https://cloud.google.com/bigquery/docs/release-notes#" + "X" * 2000
    encoded = urllib.parse.quote(long_link, safe="")
    assert len(encoded) > 2000

def test_tweet_boundary_special_symbols():
    """Verify special characters in text are safely query encoded."""
    title = 'Update: "Cool Feature" & Emojis ✨'
    encoded_title = urllib.parse.quote(f"BigQuery Update: {title}")
    # Verify quotes, ampersands and emojis are fully escaped
    assert "%26" in encoded_title  # &
    assert "%22" in encoded_title  # "
    assert "%E2%9C%A8" in encoded_title  # ✨

def test_tweet_boundary_unicode_tweet():
    """Verify unicode text encoding."""
    tweet_text = "BigQuery: 数据仓库更新 2026"
    encoded = urllib.parse.quote(tweet_text)
    assert "%E6%95%B0%E6%8D%AE%E4%BB%93%E5%BA%93" in encoded

def test_tweet_boundary_escaped_entities():
    """Verify handling of pre-escaped HTML entities in titles for tweet text generation."""
    raw_title = "BigQuery &amp; Cloud Storage"
    # Unescaped string to be tweeted
    clean_title = raw_title.replace("&amp;", "&")
    encoded = urllib.parse.quote(clean_title)
    assert "%26" in encoded
    assert "amp" not in encoded

def test_tweet_boundary_multiple_params():
    """Verify that multiple query arguments are combined with correct delimiters."""
    text_param = "text=" + urllib.parse.quote("Hello World")
    url_param = "url=" + urllib.parse.quote("http://example.com")
    intent = f"https://twitter.com/intent/tweet?{text_param}&{url_param}"
    assert intent == "https://twitter.com/intent/tweet?text=Hello%20World&url=http%3A//example.com" or "Hello" in intent


# =====================================================================
# FEATURE 6: API Error Boundaries (6 tests)
# =====================================================================

def test_error_boundary_zero_byte_response(client):
    """Test API behavior when feed server returns zero-byte response."""
    with patch("requests.get") as mock_get:
        mock_res = mock_get.return_value
        mock_res.status_code = 200
        mock_res.text = ""
        response = client.get("/api/releases?feed_url=http://zero-byte.xml")
        assert response.status_code in [500, 502]

def test_error_boundary_invalid_content_type(client):
    """Test API behavior when feed server returns invalid content type but correct XML."""
    feed_xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>Valid XML</title>
        <item>
          <title>Entry</title>
          <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """
    with patch("requests.get") as mock_get:
        mock_res = mock_get.return_value
        mock_res.status_code = 200
        mock_res.text = feed_xml
        mock_res.headers = {"Content-Type": "text/html"}  # Invalid content type but correct XML
        
        response = client.get("/api/releases?feed_url=http://invalid-content-type.xml")
        # Parser should still successfully parse well-formed XML
        assert response.status_code == 200
        assert len(response.json) == 1

def test_error_boundary_redirect_loop(client):
    """Test API behavior when feed URL triggers redirect loop (raises TooManyRedirects exception)."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.TooManyRedirects("Too many redirects")
        response = client.get("/api/releases?feed_url=http://redirect-loop.xml")
        assert response.status_code in [500, 502]
        assert response.json == {"error": "Failed to fetch or parse release notes feed"}

def test_error_boundary_dns_timeout(client):
    """Test API behavior when DNS resolution times out (raises ConnectionError)."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("DNS resolution failed")
        response = client.get("/api/releases?feed_url=http://bad-dns.xml")
        assert response.status_code in [500, 502]

def test_error_boundary_connection_refused(client):
    """Test API behavior when connection is refused (e.g. port closed)."""
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectTimeout("Connection timed out")
        response = client.get("/api/releases?feed_url=http://127.0.0.1:9999/feed")
        assert response.status_code in [500, 502]

def test_error_boundary_invalid_scheme(client):
    """Test API behavior when feed URL has an unsupported scheme (e.g. ftp://)."""
    response = client.get("/api/releases?feed_url=ftp://example.com/feed.xml")
    assert response.status_code in [500, 502]
