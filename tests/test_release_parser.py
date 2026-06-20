import unittest
from unittest.mock import patch, MagicMock
import requests
import feedparser
from flask import json

# Import the parser and app under test
import release_parser as parser
from app import app

class TestParser(unittest.TestCase):
    def test_parse_date_to_iso8601_utc_z(self):
        """Test parsing dates with Z suffix (standard UTC)"""
        raw_date = "2026-06-15T18:00:00Z"
        expected = "2026-06-15T18:00:00Z"
        self.assertEqual(parser.parse_date_to_iso8601(raw_date), expected)

    def test_parse_date_to_iso8601_offset(self):
        """Test parsing dates with negative or positive offsets, normalizing to UTC"""
        # PDT offset (UTC-7)
        raw_date = "2026-06-15T10:00:00-07:00"
        expected = "2026-06-15T17:00:00Z"
        self.assertEqual(parser.parse_date_to_iso8601(raw_date), expected)

        # EDT offset (UTC-4)
        raw_date = "2026-06-15T13:00:00-04:00"
        expected = "2026-06-15T17:00:00Z"
        self.assertEqual(parser.parse_date_to_iso8601(raw_date), expected)

    def test_parse_date_to_iso8601_rfc2822(self):
        """Test parsing RFC 2822 format date strings"""
        raw_date = "Mon, 15 Jun 2026 18:00:00 GMT"
        expected = "2026-06-15T18:00:00Z"
        self.assertEqual(parser.parse_date_to_iso8601(raw_date), expected)

    def test_parse_date_to_iso8601_date_only(self):
        """Test parsing date-only string"""
        raw_date = "2026-06-15"
        expected = "2026-06-15T00:00:00Z"
        self.assertEqual(parser.parse_date_to_iso8601(raw_date), expected)

    def test_parse_date_to_iso8601_invalid(self):
        """Test that invalid date strings raise ValueError"""
        with self.assertRaises(ValueError):
            parser.parse_date_to_iso8601("not-a-date")
        with self.assertRaises(ValueError):
            parser.parse_date_to_iso8601("")

    @patch("requests.get")
    def test_fetch_and_parse_feed_success(self, mock_get):
        """Test successful fetch and parse of a standard Atom feed"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Mock XML Atom Feed Content
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>BigQuery release notes</title>
            <entry>
                <title>BigQuery release notes - June 15, 2026</title>
                <link href="https://cloud.google.com/bigquery/docs/release-notes#June_15_2026"/>
                <updated>2026-06-15T18:00:00Z</updated>
                <content type="html">&lt;p&gt;Added a new feature.&lt;/p&gt;</content>
            </entry>
        </feed>
        """
        # Also need response.content to be mock bytes to satisfy the byte-based feedparser.parse call
        mock_response.content = mock_response.text.encode('utf-8')
        mock_get.return_value = mock_response

        releases = parser.fetch_and_parse_feed("http://mock-url.xml")
        self.assertEqual(len(releases), 1)
        self.assertEqual(releases[0]["title"], "BigQuery release notes - June 15, 2026")
        self.assertEqual(releases[0]["link"], "https://cloud.google.com/bigquery/docs/release-notes#June_15_2026")
        self.assertEqual(releases[0]["date"], "2026-06-15T18:00:00Z")
        self.assertEqual(releases[0]["content"], "<p>Added a new feature.</p>")

    @patch("requests.get")
    def test_fetch_and_parse_feed_empty(self, mock_get):
        """Test feed with no entries"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>BigQuery release notes</title>
        </feed>
        """
        mock_response.content = mock_response.text.encode('utf-8')
        mock_get.return_value = mock_response

        releases = parser.fetch_and_parse_feed("http://mock-url.xml")
        self.assertEqual(releases, [])

    @patch("requests.get")
    def test_fetch_and_parse_feed_timeout(self, mock_get):
        """Test connection/read timeout handling"""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        
        with self.assertRaises(requests.exceptions.Timeout):
            parser.fetch_and_parse_feed("http://mock-url.xml")

    @patch("requests.get")
    def test_fetch_and_parse_feed_ssl_error(self, mock_get):
        """Test SSL certificate error handling"""
        mock_get.side_effect = requests.exceptions.SSLError("SSL verification failed")
        
        with self.assertRaises(requests.exceptions.SSLError):
            parser.fetch_and_parse_feed("http://mock-url.xml")

    @patch("requests.get")
    def test_fetch_and_parse_feed_malformed_xml(self, mock_get):
        """Test parsing completely broken/malformed XML structure"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Expat/SAX parses this as malformed because of the missing closing tag
        mock_response.text = "<feed><entry><title>Broken XML"
        mock_response.content = mock_response.text.encode('utf-8')
        mock_get.return_value = mock_response
        
        with self.assertRaises(ValueError):
            parser.fetch_and_parse_feed("http://mock-url.xml")

    @patch("requests.get")
    def test_fetch_and_parse_feed_missing_fields(self, mock_get):
        """Test parsing entries that are missing critical date fields"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <title>No Date Entry</title>
                <link href="https://cloud.google.com/bigquery/docs/release-notes"/>
                <content>Some content</content>
            </entry>
        </feed>
        """
        mock_response.content = mock_response.text.encode('utf-8')
        mock_get.return_value = mock_response
        
        with self.assertRaises(ValueError) as context:
            parser.fetch_and_parse_feed("http://mock-url.xml")
        self.assertIn("Entry missing date", str(context.exception))


class TestFlaskServer(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_index_route(self):
        """Test the GET / route serving index.html"""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"BigQuery Release Notes", response.data)

    @patch("release_parser.fetch_and_parse_feed")
    def test_api_releases_success(self, mock_fetch):
        """Test GET /api/releases returning parsed release notes"""
        mock_releases = [
            {
                "title": "Release 1",
                "link": "https://example.com/1",
                "date": "2026-06-15T18:00:00Z",
                "content": "<p>Content 1</p>"
            }
        ]
        mock_fetch.return_value = mock_releases

        response = self.app.get('/api/releases')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Release 1")
        self.assertEqual(data[0]["date"], "2026-06-15T18:00:00Z")

    @patch("release_parser.fetch_and_parse_feed")
    def test_api_releases_failure(self, mock_fetch):
        """Test GET /api/releases handling parser exceptions by returning 502 with error message"""
        mock_fetch.side_effect = ValueError("Parsing failed")

        response = self.app.get('/api/releases')
        self.assertEqual(response.status_code, 502)
        
        data = json.loads(response.data)
        self.assertEqual(data, {"error": "Failed to fetch or parse release notes feed"})

    @patch("release_parser.fetch_and_parse_feed")
    def test_api_releases_ssrf_allowed(self, mock_fetch):
        """Test GET /api/releases with allowed feed_url hosts"""
        mock_fetch.return_value = []
        
        allowed_urls = [
            "http://127.0.0.1/feed",
            "http://localhost:8080/feed",
            "https://docs.cloud.google.com/feed",
            "https://cloud.google.com/feed",
            "https://anysubdomain.google.com/feed",
        ]
        for url in allowed_urls:
            response = self.app.get(f'/api/releases?feed_url={url}')
            self.assertEqual(response.status_code, 200, f"Failed for allowed URL: {url}")

    @patch("release_parser.fetch_and_parse_feed")
    def test_api_releases_ssrf_denied(self, mock_fetch):
        """Test GET /api/releases with unsafe feed_url hosts (rejected with 400)"""
        unsafe_urls = [
            "https://example.com/feed",
            "https://google.com.attacker.com/feed",
            "https://notgoogle.com/feed",
        ]
        for url in unsafe_urls:
            response = self.app.get(f'/api/releases?feed_url={url}')
            self.assertEqual(response.status_code, 400, f"Failed to reject unsafe URL: {url}")

if __name__ == "__main__":
    unittest.main()
