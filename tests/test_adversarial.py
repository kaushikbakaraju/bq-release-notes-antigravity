import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import requests
import feedparser
import datetime
from bs4 import BeautifulSoup
from flask import json

# Add project root to python path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import parser
from app import create_app

class TestAdversarialParser(unittest.TestCase):
    
    # -------------------------------------------------------------
    # 1. Date Format Normalization Tests
    # -------------------------------------------------------------
    
    def test_date_iso_with_subseconds(self):
        """Test ISO 8601 with subsecond resolution and Z suffix."""
        raw_date = "2026-06-15T18:00:00.123456Z"
        expected = "2026-06-15T18:00:00Z"
        self.assertEqual(parser.parse_date_to_iso8601(raw_date), expected)

    def test_date_iso_with_subseconds_and_offset(self):
        """Test ISO 8601 with subsecond resolution and timezone offset."""
        raw_date = "2026-06-15T10:00:00.123-07:00"
        expected = "2026-06-15T17:00:00Z"
        self.assertEqual(parser.parse_date_to_iso8601(raw_date), expected)

    def test_date_space_separator(self):
        """Test date string with space instead of 'T' separator."""
        raw_date = "2026-06-15 18:00:00Z"
        expected = "2026-06-15T18:00:00Z"
        self.assertEqual(parser.parse_date_to_iso8601(raw_date), expected)

    def test_date_rfc2822_with_offset(self):
        """Test RFC 2822 date string with numeric timezone offset (e.g. +0530)."""
        raw_date = "Mon, 15 Jun 2026 18:00:00 +0530"
        expected = "2026-06-15T12:30:00Z"
        self.assertEqual(parser.parse_date_to_iso8601(raw_date), expected)

    def test_date_rfc2822_2digit_year(self):
        """Test RFC 2822 date string with 2-digit year format."""
        raw_date = "Mon, 15 Jun 26 18:00:00 GMT"
        expected = "2026-06-15T18:00:00Z"
        self.assertEqual(parser.parse_date_to_iso8601(raw_date), expected)

    def test_date_naive_local(self):
        """Test naive datetime string (no timezone). It should fall back to UTC."""
        raw_date = "2026-06-15T18:00:00"
        expected = "2026-06-15T18:00:00Z"
        self.assertEqual(parser.parse_date_to_iso8601(raw_date), expected)

    def test_date_invalid_formats(self):
        """Test behavior with out-of-bounds/invalid date strings."""
        invalid_dates = [
            "2026-13-40T18:00:00Z",  # out-of-bounds month/day
            "2026/06/15",            # slashes (not ISO format)
            "June 15, 2026",         # human natural language
            "not-a-date",            # random text
            "   ",                   # spaces
        ]
        for val in invalid_dates:
            with self.assertRaises(ValueError):
                parser.parse_date_to_iso8601(val)

    def test_date_none_and_empty(self):
        """Test that None and empty string raise ValueError."""
        with self.assertRaises(ValueError):
            parser.parse_date_to_iso8601(None)
        with self.assertRaises(ValueError):
            parser.parse_date_to_iso8601("")

    # -------------------------------------------------------------
    # 2. XML Edge Cases and Adversarial Payloads
    # -------------------------------------------------------------

    @patch("requests.get")
    def test_feed_extreme_lengths(self, mock_get):
        """Test feed containing extremely long title and content fields."""
        long_title = "A" * 100000
        long_content = "B" * 1000000
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = f"""<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>BigQuery release notes</title>
            <entry>
                <title>{long_title}</title>
                <link href="https://example.com/long"/>
                <updated>2026-06-15T18:00:00Z</updated>
                <content type="html">{long_content}</content>
            </entry>
        </feed>
        """
        mock_get.return_value = mock_response

        releases = parser.fetch_and_parse_feed("http://mock-url.xml")
        self.assertEqual(len(releases), 1)
        self.assertEqual(releases[0]["title"], long_title)
        self.assertEqual(releases[0]["content"], long_content)

    @patch("requests.get")
    def test_feed_malformed_xml_tags(self, mock_get):
        """Test feed with mismatched, unclosed, or invalid XML tags."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # feedparser might try to repair minor tag nesting, but structural brokenness should trigger bozo.
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <title>Broken Entry</title>
                <link href="https://example.com/broken">
                <updated>2026-06-15T18:00:00Z
                <!-- Missing closing tags entirely -->
        """
        mock_get.return_value = mock_response

        with self.assertRaises(ValueError):
            parser.fetch_and_parse_feed("http://mock-url.xml")

    @patch("requests.get")
    def test_feed_completely_empty(self, mock_get):
        """Test completely empty payload or basic empty tags."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        # Scenario A: Completely empty string
        mock_response.text = ""
        mock_get.return_value = mock_response
        with self.assertRaises(ValueError):
            parser.fetch_and_parse_feed("http://mock-url.xml")

        # Scenario B: Atom with no entries
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>BigQuery release notes</title>
        </feed>
        """
        mock_get.return_value = mock_response
        releases = parser.fetch_and_parse_feed("http://mock-url.xml")
        self.assertEqual(releases, [])

    @patch("requests.get")
    def test_feed_invalid_characters(self, mock_get):
        """Test feed containing control characters and non-XML chars."""
        # Control characters like \x00 are invalid in standard XML 1.0
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <title>Control Char \x00 Title</title>
                <link href="https://example.com/control"/>
                <updated>2026-06-15T18:00:00Z</updated>
                <content>Normal Content</content>
            </entry>
        </feed>
        """
        mock_get.return_value = mock_response

        with self.assertRaises(ValueError):
            parser.fetch_and_parse_feed("http://mock-url.xml")

    @patch("requests.get")
    def test_feed_unexpected_xml_structures(self, mock_get):
        """Test feed with unexpected/custom namespaces and elements."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:custom="http://custom.namespace">
            <custom:metadata>Some metadata</custom:metadata>
            <entry>
                <title>Custom entry</title>
                <link rel="alternate" type="text/html" href="https://example.com/custom"/>
                <updated>2026-06-15T18:00:00Z</updated>
                <content type="xhtml">
                    <div xmlns="http://www.w3.org/1999/xhtml">
                        <custom:widget>widget content</custom:widget>
                        <p>Real content</p>
                    </div>
                </content>
            </entry>
        </feed>
        """
        mock_get.return_value = mock_response

        releases = parser.fetch_and_parse_feed("http://mock-url.xml")
        self.assertEqual(len(releases), 1)
        self.assertEqual(releases[0]["title"], "Custom entry")
        self.assertIn("Real content", releases[0]["content"])


class TestAdversarialFlaskServer(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    # -------------------------------------------------------------
    # 3. Network Failures, Timeouts, and Exceptions
    # -------------------------------------------------------------

    @patch("requests.get")
    def test_app_network_failure(self, mock_get):
        """Test app /api/releases behavior under DNS/Connection failures."""
        mock_get.side_effect = requests.exceptions.ConnectionError("DNS lookup failed")
        
        response = self.client.get("/api/releases")
        self.assertEqual(response.status_code, 502)
        
        data = json.loads(response.data)
        self.assertEqual(data, {"error": "Failed to fetch or parse release notes feed"})

    @patch("requests.get")
    def test_app_timeout(self, mock_get):
        """Test app /api/releases behavior when feed server times out."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        
        response = self.client.get("/api/releases")
        self.assertEqual(response.status_code, 502)
        
        data = json.loads(response.data)
        self.assertEqual(data, {"error": "Failed to fetch or parse release notes feed"})

    @patch("requests.get")
    def test_app_ssl_verification_error(self, mock_get):
        """Test app /api/releases behavior under SSL certificate errors."""
        mock_get.side_effect = requests.exceptions.SSLError("SSL verification failed")
        
        response = self.client.get("/api/releases")
        self.assertEqual(response.status_code, 502)
        
        data = json.loads(response.data)
        self.assertEqual(data, {"error": "Failed to fetch or parse release notes feed"})

    @patch("requests.get")
    def test_app_http_errors(self, mock_get):
        """Test app /api/releases behavior under various HTTP error codes."""
        error_codes = [400, 401, 403, 404, 500, 502, 503, 504]
        for code in error_codes:
            mock_response = MagicMock()
            mock_response.status_code = code
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                f"{code} Error", response=mock_response
            )
            mock_get.return_value = mock_response
            
            response = self.client.get("/api/releases")
            self.assertEqual(response.status_code, 502)
            
            data = json.loads(response.data)
            self.assertEqual(data, {"error": "Failed to fetch or parse release notes feed"})

    @patch("requests.get")
    def test_app_invalid_content_type(self, mock_get):
        """Test app /api/releases behavior when server returns JSON/HTML instead of XML."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "success", "data": []}'
        mock_get.return_value = mock_response

        response = self.client.get("/api/releases")
        # feedparser will bozo because JSON is not valid XML.
        # This will raise a ValueError in fetch_and_parse_feed, resulting in 502.
        self.assertEqual(response.status_code, 502)
        
        data = json.loads(response.data)
        self.assertEqual(data, {"error": "Failed to fetch or parse release notes feed"})

    @patch("parser.fetch_and_parse_feed")
    def test_app_unexpected_exception(self, mock_fetch):
        """Test app /api/releases behavior when parser raises a generic system exception."""
        mock_fetch.side_effect = RuntimeError("Catastrophic disk/memory failure")
        
        response = self.client.get("/api/releases")
        self.assertEqual(response.status_code, 502)
        
        data = json.loads(response.data)
        self.assertEqual(data, {"error": "Failed to fetch or parse release notes feed"})


if __name__ == "__main__":
    unittest.main()
