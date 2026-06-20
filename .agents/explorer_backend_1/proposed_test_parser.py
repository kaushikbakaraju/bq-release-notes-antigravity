import unittest
from unittest.mock import patch, MagicMock
import requests
import feedparser

# Import the parser under test
import proposed_parser as parser

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
        mock_get.return_value = mock_response
        
        with self.assertRaises(ValueError) as context:
            parser.fetch_and_parse_feed("http://mock-url.xml")
        self.assertIn("Entry missing date", str(context.exception))

if __name__ == "__main__":
    unittest.main()
