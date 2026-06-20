import os
import requests
from bs4 import BeautifulSoup

def test_mock_rss_server_running(mock_rss_server):
    """Test that the mock RSS server is running and responds to HTTP requests."""
    response = requests.get(f"{mock_rss_server.url}/feed/valid")
    assert response.status_code == 200
    assert "BigQuery release notes" in response.text

def test_mock_rss_server_endpoints(mock_rss_server):
    """Test all feed types served by the mock RSS server."""
    # Empty feed
    response = requests.get(f"{mock_rss_server.url}/feed/empty")
    assert response.status_code == 200
    assert "BigQuery release notes" in response.text
    
    # Malformed feed
    response = requests.get(f"{mock_rss_server.url}/feed/malformed")
    assert response.status_code == 200
    
    # Extreme feed
    response = requests.get(f"{mock_rss_server.url}/feed/extreme")
    assert response.status_code == 200
    
    # Error endpoints
    response = requests.get(f"{mock_rss_server.url}/error/500")
    assert response.status_code == 500
    
    response = requests.get(f"{mock_rss_server.url}/error/502")
    assert response.status_code == 502
    
    response = requests.get(f"{mock_rss_server.url}/error/404")
    assert response.status_code == 404

def test_flask_app_endpoints(client, mock_rss_server):
    """Test that the Flask app serves the index page and release notes JSON."""
    # 1. Test Serve Frontend (index.html)
    response = client.get("/")
    assert response.status_code == 200
    soup = BeautifulSoup(response.data, "html.parser")
    assert soup.find("h1").text == "BigQuery Release Notes"
    assert soup.find(id="refresh-btn") is not None
    assert soup.find(id="spinner-container") is not None
    assert soup.find(id="releases-list") is not None

    # 2. Test Retrieve Release API (uses mock_rss_server pointing to valid feed by default)
    response = client.get("/api/releases")
    assert response.status_code == 200
    data = response.json
    assert len(data) == 1
    assert data[0]["title"] == "BigQuery feature update"
    assert data[0]["link"] == "https://cloud.google.com/bigquery/docs/release-notes#June_20_2026"
    assert data[0]["date"] == "2026-06-20T12:00:00Z"
    assert "We have released a new feature." in data[0]["content"]

def test_flask_app_api_error_handling(client, mock_rss_server):
    """Test API error handling when feed is unavailable or invalid."""
    # Test HTTP error 500 from feed server -> Flask API should return 502 or 500
    feed_url = f"{mock_rss_server.url}/error/500"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert response.status_code in [500, 502]
    assert response.json == {"error": "Failed to fetch or parse release notes feed"}

    # Test HTTP error 404 from feed server
    feed_url = f"{mock_rss_server.url}/error/404"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert response.status_code in [500, 502]
    assert response.json == {"error": "Failed to fetch or parse release notes feed"}

    # Test malformed xml from feed server
    feed_url = f"{mock_rss_server.url}/feed/malformed"
    response = client.get(f"/api/releases?feed_url={feed_url}")
    assert response.status_code in [500, 502]
    assert response.json == {"error": "Failed to fetch or parse release notes feed"}
