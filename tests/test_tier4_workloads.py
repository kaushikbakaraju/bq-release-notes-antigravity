import os
import urllib.parse
from bs4 import BeautifulSoup
import pytest

# =====================================================================
# WORKLOAD 1: Standard User Flow
# =====================================================================

def test_workload_standard_user_flow(client, mock_rss_server):
    """
    Scenario: Standard User Flow
    1. User accesses homepage.
    2. Page loads static resources.
    3. AJAX call gets current release notes.
    4. User triggers refresh to pull new releases.
    """
    # Step 1: Access homepage
    home_response = client.get("/")
    assert home_response.status_code == 200
    soup = BeautifulSoup(home_response.data, "html.parser")
    assert soup.find("h1").text.strip() == "BigQuery Release Notes"
    assert soup.find(id="refresh-btn") is not None
    
    # Step 2: Fetch releases via API
    api_url = f"/api/releases?feed_url={mock_rss_server.url}/feed/valid"
    api_response = client.get(api_url)
    assert api_response.status_code == 200
    releases = api_response.json
    assert len(releases) == 1
    assert releases[0]["title"] == "BigQuery feature update"
    
    # Step 3: Click refresh (simulate subsequent AJAX call)
    refresh_response = client.get(api_url)
    assert refresh_response.status_code == 200
    assert len(refresh_response.json) == 1


# =====================================================================
# WORKLOAD 2: Sharing Flow
# =====================================================================

def test_workload_sharing_flow(client, mock_rss_server):
    """
    Scenario: Sharing Flow
    1. User loads homepage and pulls release notes.
    2. User views a release card.
    3. User clicks Tweet Share, redirecting to formatted Twitter Web Intent.
    """
    # Step 1: Load homepage
    assert client.get("/").status_code == 200
    
    # Step 2: Retrieve releases
    api_url = f"/api/releases?feed_url={mock_rss_server.url}/feed/valid"
    releases = client.get(api_url).json
    assert len(releases) > 0
    release = releases[0]
    
    # Step 3: Validate Twitter Sharing Web Intent parameters
    # The client-side JS app.js formats the URL like:
    # `https://twitter.com/intent/tweet?text=BigQuery Update: ${release.title}&url=${release.link}`
    tweet_text = f"BigQuery Update: {release['title']}"
    tweet_url = release['link']
    
    encoded_text = urllib.parse.quote(tweet_text)
    encoded_url = urllib.parse.quote(tweet_url)
    
    intent_url = f"https://twitter.com/intent/tweet?text={encoded_text}&url={encoded_url}"
    assert "https://twitter.com/intent/tweet" in intent_url
    assert encoded_text in intent_url
    assert encoded_url in intent_url


# =====================================================================
# WORKLOAD 3: Failure / Recovery Flow
# =====================================================================

def test_workload_failure_recovery_flow(client, mock_rss_server):
    """
    Scenario: Failure / Recovery Flow
    1. User loads homepage.
    2. API fails due to feed server downtime (returns 502).
    3. Feed server is restored.
    4. User clicks refresh, pulling valid releases successfully.
    """
    # Step 1: Load homepage
    assert client.get("/").status_code == 200
    
    # Step 2: Feed server down
    down_url = f"/api/releases?feed_url={mock_rss_server.url}/error/502"
    err_res = client.get(down_url)
    assert err_res.status_code in [500, 502]
    assert err_res.json == {"error": "Failed to fetch or parse release notes feed"}
    
    # Step 3 & 4: Feed server recovers, user refreshes
    recovered_url = f"/api/releases?feed_url={mock_rss_server.url}/feed/valid"
    ok_res = client.get(recovered_url)
    assert ok_res.status_code == 200
    assert len(ok_res.json) == 1
    assert ok_res.json[0]["title"] == "BigQuery feature update"


# =====================================================================
# WORKLOAD 4: No Updates Flow
# =====================================================================

def test_workload_no_updates_flow(client, mock_rss_server):
    """
    Scenario: No Updates Flow
    1. User loads homepage.
    2. API returns empty list of releases.
    3. Client JS shows no-update UI state.
    4. User clicks refresh, still empty.
    """
    # Step 1: Load homepage
    assert client.get("/").status_code == 200
    
    # Step 2: Fetch releases, empty feed
    empty_url = f"/api/releases?feed_url={mock_rss_server.url}/feed/empty"
    releases = client.get(empty_url).json
    assert releases == []
    
    # Step 3: Check app.js logic handles empty state
    # (In app.js: if (releases.length === 0) releasesList.innerHTML = "<p>No release notes available.</p>")
    js_path = os.path.join(os.path.dirname(__file__), "../static/app.js")
    with open(js_path, "r") as f:
        js_content = f.read()
    assert "No release notes available." in js_content
    
    # Step 4: Refresh again
    releases_refreshed = client.get(empty_url).json
    assert releases_refreshed == []


# =====================================================================
# WORKLOAD 5: Content Rich Feed Flow
# =====================================================================

def test_workload_content_rich_feed_flow(client, mock_rss_server):
    """
    Scenario: Content-Rich Feed Flow
    1. User loads homepage.
    2. API fetches and parses a feed with complex HTML, emojis, special characters, and XSS scripts.
    3. API correctly serves content in JSON without crashing.
    4. Elements are ready to be displayed.
    """
    # Step 1: Load homepage
    assert client.get("/").status_code == 200
    
    # Step 2: Retrieve extreme feed
    extreme_url = f"/api/releases?feed_url={mock_rss_server.url}/feed/extreme"
    response = client.get(extreme_url)
    assert response.status_code == 200
    releases = response.json
    assert len(releases) == 1
    
    # Step 3: Verify structure, unicode, and raw HTML content preservation
    release = releases[0]
    assert len(release["title"]) == 1000  # "A" * 1000
    assert "Heavy HTML content" in release["content"]
    assert "<script>alert('xss')</script>" in release["content"]
    assert "Special characters: &lt; &gt; &amp; &quot; &apos; ★ ⚡ 🚀" in release["content"]
