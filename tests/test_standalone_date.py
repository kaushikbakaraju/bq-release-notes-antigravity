import datetime
import email.utils
import unittest

def parse_date_to_iso8601(date_str):
    if not date_str:
        raise ValueError("Empty date string provided")
        
    date_str = date_str.strip()
    
    # 1. Try parsing as RFC 2822 (common in RSS feeds)
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        dt_utc = dt.astimezone(datetime.timezone.utc)
        return dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    except (ValueError, TypeError, IndexError):
        pass

    # 2. Try parsing as ISO 8601 (Atom standard)
    normalized = date_str
    if normalized.endswith('Z'):
        # Normalize trailing Z to +00:00 for Python datetime parser compatibility
        normalized = normalized[:-1] + '+00:00'
        
    try:
        if len(normalized) == 10:  # YYYY-MM-DD
            normalized += 'T00:00:00+00:00'
        dt = datetime.datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        dt_utc = dt.astimezone(datetime.timezone.utc)
        return dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        pass

    # 3. Fallback: Parse using dateutil if installed (provides extra resilience)
    try:
        import dateutil.parser
        dt = dateutil.parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        dt_utc = dt.astimezone(datetime.timezone.utc)
        return dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
    except (ImportError, ValueError, TypeError):
        pass

    raise ValueError(f"Unable to parse date string: {date_str}")

class TestStandaloneDateParser(unittest.TestCase):
    def test_parse_date_to_iso8601_utc_z(self):
        """Test parsing dates with Z suffix (standard UTC)"""
        raw_date = "2026-06-15T18:00:00Z"
        expected = "2026-06-15T18:00:00Z"
        self.assertEqual(parse_date_to_iso8601(raw_date), expected)

    def test_parse_date_to_iso8601_offset(self):
        """Test parsing dates with negative or positive offsets, normalizing to UTC"""
        # PDT offset (UTC-7)
        raw_date = "2026-06-15T10:00:00-07:00"
        expected = "2026-06-15T17:00:00Z"
        self.assertEqual(parse_date_to_iso8601(raw_date), expected)

        # EDT offset (UTC-4)
        raw_date = "2026-06-15T13:00:00-04:00"
        expected = "2026-06-15T17:00:00Z"
        self.assertEqual(parse_date_to_iso8601(raw_date), expected)

    def test_parse_date_to_iso8601_rfc2822(self):
        """Test parsing RFC 2822 format date strings"""
        raw_date = "Mon, 15 Jun 2026 18:00:00 GMT"
        expected = "2026-06-15T18:00:00Z"
        self.assertEqual(parse_date_to_iso8601(raw_date), expected)

    def test_parse_date_to_iso8601_date_only(self):
        """Test parsing date-only string"""
        raw_date = "2026-06-15"
        expected = "2026-06-15T00:00:00Z"
        self.assertEqual(parse_date_to_iso8601(raw_date), expected)

    def test_date_iso_with_subseconds(self):
        """Test ISO 8601 with subsecond resolution and Z suffix."""
        raw_date = "2026-06-15T18:00:00.123456Z"
        expected = "2026-06-15T18:00:00Z"
        self.assertEqual(parse_date_to_iso8601(raw_date), expected)

    def test_date_iso_with_subseconds_and_offset(self):
        """Test ISO 8601 with subsecond resolution and timezone offset."""
        raw_date = "2026-06-15T10:00:00.123-07:00"
        expected = "2026-06-15T17:00:00Z"
        self.assertEqual(parse_date_to_iso8601(raw_date), expected)

    def test_date_space_separator(self):
        """Test date string with space instead of 'T' separator."""
        raw_date = "2026-06-15 18:00:00Z"
        expected = "2026-06-15T18:00:00Z"
        self.assertEqual(parse_date_to_iso8601(raw_date), expected)

    def test_date_rfc2822_with_offset(self):
        """Test RFC 2822 date string with numeric timezone offset (e.g. +0530)."""
        raw_date = "Mon, 15 Jun 2026 18:00:00 +0530"
        expected = "2026-06-15T12:30:00Z"
        self.assertEqual(parse_date_to_iso8601(raw_date), expected)

    def test_date_rfc2822_2digit_year(self):
        """Test RFC 2822 date string with 2-digit year format."""
        raw_date = "Mon, 15 Jun 26 18:00:00 GMT"
        expected = "2026-06-15T18:00:00Z"
        self.assertEqual(parse_date_to_iso8601(raw_date), expected)

    def test_date_naive_local(self):
        """Test naive datetime string (no timezone). It should fall back to UTC."""
        raw_date = "2026-06-15T18:00:00"
        expected = "2026-06-15T18:00:00Z"
        self.assertEqual(parse_date_to_iso8601(raw_date), expected)

    def test_date_invalid_formats(self):
        """Test behavior with out-of-bounds/invalid date strings."""
        invalid_dates = [
            "2026-13-40T18:00:00Z",  # out-of-bounds month/day
            "not-a-date",            # random text
            "   ",                   # spaces
        ]
        for val in invalid_dates:
            with self.assertRaises(ValueError):
                parse_date_to_iso8601(val)

    def test_date_none_and_empty(self):
        """Test that None and empty string raise ValueError."""
        with self.assertRaises(ValueError):
            parse_date_to_iso8601(None)
        with self.assertRaises(ValueError):
            parse_date_to_iso8601("")

if __name__ == "__main__":
    unittest.main()
