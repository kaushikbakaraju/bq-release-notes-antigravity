import os
from unittest.mock import patch
from bs4 import BeautifulSoup
import pytest
import requests

def test_combination_frontend_load_and_server_down(client, mock_rss_server):
    """Combination: Frontend load when backend feed server is down (returns 500/502)."""
    # 1. Load Frontend
    frontend_res = client.get("/")
    assert frontend_res.status_code == 200
    
    # 2. Call API (mocking a down server)
    feed_url = f"{mock_rss_server.url}/error/500"
    api_res = client.get(f"/api/releases?feed_url={feed_url}")
    assert api_res.status_code in [500, 502]
    assert api_res.json == {"error": "Failed to fetch or parse release notes feed"}

def test_combination_frontend_load_and_server_empty(client, mock_rss_server):
    """Combination: Frontend load when backend feed is empty."""
    # 1. Load Frontend
    frontend_res = client.get("/")
    assert frontend_res.status_code == 200
    
    # 2. Call API (pointing to empty feed)
    feed_url = f"{mock_rss_server.url}/feed/empty"
    api_res = client.get(f"/api/releases?feed_url={feed_url}")
    assert api_res.status_code == 200
    assert api_res.json == []

def test_combination_frontend_load_and_server_slow(client, mock_rss_server):
    """Combination: Frontend load when feed server is slow (verifying timeout/latency handling)."""
    # 1. Load Frontend
    frontend_res = client.get("/")
    assert frontend_res.status_code == 200
    
    # 2. Call API (pointing to slow feed)
    feed_url = f"{mock_rss_server.url}/feed/delay"
    api_res = client.get(f"/api/releases?feed_url={feed_url}")
    assert api_res.status_code == 200
    assert len(api_res.json) == 1

def test_combination_frontend_load_and_server_updated(client, mock_rss_server):
    """Combination: Frontend load, first fetch gets empty feed, subsequent refresh gets updated feed."""
    # 1. Load Frontend
    frontend_res = client.get("/")
    assert frontend_res.status_code == 200
    
    # 2. First fetch: Empty feed
    feed_url_empty = f"{mock_rss_server.url}/feed/empty"
    api_res_1 = client.get(f"/api/releases?feed_url={feed_url_empty}")
    assert api_res_1.status_code == 200
    assert len(api_res_1.json) == 0
    
    # 3. Second fetch (Refresh): Valid feed
    feed_url_valid = f"{mock_rss_server.url}/feed/valid"
    api_res_2 = client.get(f"/api/releases?feed_url={feed_url_valid}")
    assert api_res_2.status_code == 200
    assert len(api_res_2.json) == 1
    assert api_res_2.json[0]["title"] == "BigQuery feature update"

def test_combination_frontend_load_and_server_xss_payload(client, mock_rss_server):
    """Combination: Frontend load when feed contains malicious XSS payload (extreme)."""
    # 1. Load Frontend
    frontend_res = client.get("/")
    assert frontend_res.status_code == 200
    
    # 2. Call API with extreme feed URL
    feed_url = f"{mock_rss_server.url}/feed/extreme"
    api_res = client.get(f"/api/releases?feed_url={feed_url}")
    assert api_res.status_code == 200
    
    # Verify content contains script element which must be safely passed to client JS
    data = api_res.json
    assert len(data) == 1
    assert "<script>alert('xss')</script>" in data[0]["content"]

def test_combination_frontend_refresh_after_server_recovery(client, mock_rss_server):
    """Combination: API server initially fails, then recovers, client successfully refreshes."""
    # 1. First fetch: Down server
    feed_url_down = f"{mock_rss_server.url}/error/502"
    res_1 = client.get(f"/api/releases?feed_url={feed_url_down}")
    assert res_1.status_code in [500, 502]
    
    # 2. Second fetch: Recovered server
    feed_url_ok = f"{mock_rss_server.url}/feed/valid"
    res_2 = client.get(f"/api/releases?feed_url={feed_url_ok}")
    assert res_2.status_code == 200
    assert len(res_2.json) == 1

def test_combination_frontend_refresh_empty_to_nonempty(client):
    """Combination: Verify transition from empty state to filled state."""
    # 1. Empty feed setup
    empty_xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0"><channel><title>Updates</title></channel></rss>"""
    
    # 2. Non-empty feed setup
    non_empty_xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>Updates</title>
        <item>
          <title>New Release</title>
          <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>"""
    
    with patch("requests.get") as mock_get:
        mock_res = mock_get.return_value
        mock_res.status_code = 200
        mock_res.text = empty_xml
        
        # Call empty feed
        res1 = client.get("/api/releases?feed_url=http://empty.xml")
        assert len(res1.json) == 0
        
        # Mock updates
        mock_res.text = non_empty_xml
        
        # Refresh API call
        res2 = client.get("/api/releases?feed_url=http://non-empty.xml")
        assert len(res2.json) == 1
        assert res2.json[0]["title"] == "New Release"
