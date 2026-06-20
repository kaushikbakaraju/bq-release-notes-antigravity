import os
import sys
import datetime
import logging
import email
from types import ModuleType

# -----------------------------------------------------------------
# 1. Setup Mock Modules for Flask, Requests, Feedparser
# -----------------------------------------------------------------

# Mock requests module
requests_mock = ModuleType('requests')
requests_mock.exceptions = ModuleType('requests.exceptions')

class RequestException(Exception): pass
class ConnectionError(RequestException): pass
class Timeout(RequestException): pass
class SSLError(RequestException): pass
class HTTPError(RequestException): pass

requests_mock.exceptions.RequestException = RequestException
requests_mock.exceptions.ConnectionError = ConnectionError
requests_mock.exceptions.Timeout = Timeout
requests_mock.exceptions.SSLError = SSLError
requests_mock.exceptions.HTTPError = HTTPError

class MockResponse:
    def __init__(self, text, status_code=200, exception=None):
        self.text = text
        self.status_code = status_code
        self.exception = exception
        
    def raise_for_status(self):
        if self.exception:
            raise self.exception
        if self.status_code >= 400:
            raise HTTPError(f"HTTP Error {self.status_code}")

class MockRequestsClient:
    def __init__(self):
        self.response = None
        self.side_effect = None
        
    def get(self, url, timeout=10.0):
        if self.side_effect:
            if isinstance(self.side_effect, Exception):
                raise self.side_effect
            elif callable(self.side_effect):
                return self.side_effect(url, timeout)
        return self.response

requests_client = MockRequestsClient()
requests_mock.get = requests_client.get
sys.modules['requests'] = requests_mock


# Mock feedparser module
feedparser_mock = ModuleType('feedparser')

class CharacterEncodingOverride(Exception): pass
feedparser_mock.CharacterEncodingOverride = CharacterEncodingOverride

class FeedParserDict(dict):
    def __getattr__(self, name):
        return self.get(name)

class ContentObj:
    def __init__(self, value):
        self.value = value

import xml.etree.ElementTree as ET

def mock_feedparser_parse(xml_text):
    result = FeedParserDict()
    result.bozo = 0
    result.entries = []
    
    if not xml_text:
        result.bozo = 1
        result.bozo_exception = Exception("Empty document")
        return result
        
    try:
        root = ET.fromstring(xml_text)
        
        def get_tag_name(elem):
            if '}' in elem.tag:
                return elem.tag.split('}', 1)[1]
            return elem.tag

        # Find entries/items
        for elem in root.iter():
            tag = get_tag_name(elem)
            if tag == 'entry':
                entry = FeedParserDict()
                for child in elem:
                    ctag = get_tag_name(child)
                    if ctag == 'title':
                        entry['title'] = child.text or ""
                    elif ctag == 'link':
                        entry['link'] = {'href': child.attrib.get('href', '')}
                    elif ctag == 'updated':
                        entry['updated'] = child.text or ""
                    elif ctag == 'published':
                        entry['published'] = child.text or ""
                    elif ctag == 'content':
                        entry['content'] = [ContentObj(child.text or "")]
                    elif ctag == 'summary':
                        entry['summary'] = child.text or ""
                result.entries.append(entry)
                
            elif tag == 'item':
                entry = FeedParserDict()
                for child in elem:
                    ctag = get_tag_name(child)
                    if ctag == 'title':
                        entry['title'] = child.text or ""
                    elif ctag == 'link':
                        entry['link'] = child.text or ""
                    elif ctag == 'pubDate':
                        entry['updated'] = child.text or ""
                    elif ctag == 'date':
                        entry['date'] = child.text or ""
                    elif ctag == 'description':
                        entry['summary'] = child.text or ""
                result.entries.append(entry)
                
    except Exception as e:
        result.bozo = 1
        result.bozo_exception = e
        
    return result

feedparser_mock.parse = mock_feedparser_parse
sys.modules['feedparser'] = feedparser_mock


# Mock Flask module
flask_mock = ModuleType('flask')

class MockFlask:
    def __init__(self, name):
        self.config = {}
        self.routes = {}
        
    def route(self, rule, **options):
        def decorator(f):
            self.routes[rule] = f
            return f
        return decorator

class MockRequest:
    def __init__(self):
        self.args = {}

flask_mock.Flask = MockFlask
flask_mock.jsonify = lambda x: x
flask_mock.render_template = lambda t: f"Rendered {t}"
mock_request_instance = MockRequest()
flask_mock.request = mock_request_instance

sys.modules['flask'] = flask_mock


# -----------------------------------------------------------------
# 2. Dynamic Execution of parser.py and app.py (Bypassing Sandboxing)
# -----------------------------------------------------------------

# Exec parser.py
with open("parser.py", "r") as f:
    parser_code = f.read()
parser_code = parser_code.replace("import requests", "pass")
parser_code = parser_code.replace("import feedparser", "pass")

parser_module = ModuleType('parser')
parser_namespace = parser_module.__dict__
parser_namespace.update({
    '__name__': 'parser',
    'requests': requests_mock,
    'feedparser': feedparser_mock,
    'os': os,
    'logging': logging,
    'datetime': datetime,
    'email': email,
    'sys': sys,
})
exec(parser_code, parser_namespace)
sys.modules['parser'] = parser_module

# Exec app.py
with open("app.py", "r") as f:
    app_code = f.read()
app_code = app_code.replace("from flask import Flask, jsonify, render_template, request", "pass")
app_code = app_code.replace("import parser", "pass")

app_module = ModuleType('app')
app_namespace = app_module.__dict__
app_namespace.update({
    '__name__': 'app',
    'os': os,
    'logging': logging,
    'Flask': MockFlask,
    'jsonify': lambda x: x,
    'render_template': lambda t: f"Rendered {t}",
    'request': mock_request_instance,
    'parser': parser_module,
})
exec(app_code, app_namespace)
sys.modules['app'] = app_module


# -----------------------------------------------------------------
# 3. Test Runner Infrastructure
# -----------------------------------------------------------------
tests_run = 0
tests_failed = 0

def run_test(name, fn):
    global tests_run, tests_failed
    tests_run += 1
    print(f"Running test: {name} ...", end=" ")
    try:
        fn()
        print("PASSED")
    except AssertionError as e:
        tests_failed += 1
        print(f"FAILED\n  AssertionError: {str(e)}")
    except Exception as e:
        tests_failed += 1
        import traceback
        print(f"ERROR\n  Exception: {str(e)}")
        traceback.print_exc()

# Helper to assert values
def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"Expected {repr(expected)}, got {repr(actual)}. {msg}")

def assert_raises(exception_class, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exception_class:
        return
    except Exception as e:
        raise AssertionError(f"Expected {exception_class.__name__}, but raised {type(e).__name__}: {str(e)}")
    raise AssertionError(f"Expected {exception_class.__name__} but no exception was raised.")


# -----------------------------------------------------------------
# 4. Date Parsing Test Cases
# -----------------------------------------------------------------

def test_date_iso_z():
    assert_eq(parser_module.parse_date_to_iso8601("2026-06-15T18:00:00Z"), "2026-06-15T18:00:00Z")

def test_date_iso_offset():
    assert_eq(parser_module.parse_date_to_iso8601("2026-06-15T10:00:00-07:00"), "2026-06-15T17:00:00Z")

def test_date_rfc2822():
    assert_eq(parser_module.parse_date_to_iso8601("Mon, 15 Jun 2026 18:00:00 GMT"), "2026-06-15T18:00:00Z")

def test_date_only():
    assert_eq(parser_module.parse_date_to_iso8601("2026-06-15"), "2026-06-15T00:00:00Z")

def test_date_subseconds():
    assert_eq(parser_module.parse_date_to_iso8601("2026-06-15T18:00:00.123456Z"), "2026-06-15T18:00:00Z")

def test_date_space_sep():
    assert_eq(parser_module.parse_date_to_iso8601("2026-06-15 18:00:00Z"), "2026-06-15T18:00:00Z")

def test_date_rfc2822_offset():
    assert_eq(parser_module.parse_date_to_iso8601("Mon, 15 Jun 2026 18:00:00 +0530"), "2026-06-15T12:30:00Z")

def test_date_rfc2822_2digit_year():
    assert_eq(parser_module.parse_date_to_iso8601("Mon, 15 Jun 26 18:00:00 GMT"), "2026-06-15T18:00:00Z")

def test_date_naive():
    assert_eq(parser_module.parse_date_to_iso8601("2026-06-15T18:00:00"), "2026-06-15T18:00:00Z")

def test_date_invalid():
    assert_raises(ValueError, parser_module.parse_date_to_iso8601, "not-a-date")
    assert_raises(ValueError, parser_module.parse_date_to_iso8601, "")
    assert_raises(ValueError, parser_module.parse_date_to_iso8601, "2026-13-45T18:00:00Z")
    assert_raises(ValueError, parser_module.parse_date_to_iso8601, "   ")
    assert_raises(ValueError, parser_module.parse_date_to_iso8601, None)


# -----------------------------------------------------------------
# 5. XML Parser Edge Cases
# -----------------------------------------------------------------

def test_xml_extreme_lengths():
    long_title = "A" * 100000
    long_content = "B" * 1000000
    
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
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
    requests_client.response = MockResponse(xml)
    requests_client.side_effect = None
    
    releases = parser_module.fetch_and_parse_feed("http://mock-url.xml")
    assert_eq(len(releases), 1)
    assert_eq(releases[0]["title"], long_title)
    assert_eq(releases[0]["content"], long_content)

def test_xml_malformed_tags():
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <title>Broken Entry</title>
            <link href="https://example.com/broken">
            <updated>2026-06-15T18:00:00Z
    """
    requests_client.response = MockResponse(xml)
    
    assert_raises(ValueError, parser_module.fetch_and_parse_feed, "http://mock-url.xml")

def test_xml_completely_empty():
    requests_client.response = MockResponse("")
    assert_raises(ValueError, parser_module.fetch_and_parse_feed, "http://mock-url.xml")

def test_xml_no_entries():
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>BigQuery release notes</title>
    </feed>
    """
    requests_client.response = MockResponse(xml)
    releases = parser_module.fetch_and_parse_feed("http://mock-url.xml")
    assert_eq(releases, [])

def test_xml_invalid_chars():
    # ET.fromstring will fail on raw XML containing control character \x00
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <title>Control Char \x00 Title</title>
            <link href="https://example.com/control"/>
            <updated>2026-06-15T18:00:00Z</updated>
            <content>Normal Content</content>
        </entry>
    </feed>
    """
    requests_client.response = MockResponse(xml)
    assert_raises(ValueError, parser_module.fetch_and_parse_feed, "http://mock-url.xml")

def test_xml_special_unicode():
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <title>Unicode: ★ ⚡ 🚀</title>
            <link href="https://example.com/unicode"/>
            <updated>2026-06-15T18:00:00Z</updated>
            <content>HTML entities: &amp;lt;script&amp;gt; &amp;amp; &amp;quot;</content>
        </entry>
    </feed>
    """
    requests_client.response = MockResponse(xml)
    releases = parser_module.fetch_and_parse_feed("http://mock-url.xml")
    assert_eq(len(releases), 1)
    assert_eq(releases[0]["title"], "Unicode: ★ ⚡ 🚀")
    assert_eq(releases[0]["content"], "HTML entities: &lt;script&gt; &amp; &quot;")


# -----------------------------------------------------------------
# 6. Flask Server Network & Timeout Tests
# -----------------------------------------------------------------

def test_flask_index_route():
    flask_app = app_module.create_app()
    index_fn = flask_app.routes["/"]
    res = index_fn()
    assert_eq(res, "Rendered index.html")

def test_flask_api_success():
    flask_app = app_module.create_app()
    api_fn = flask_app.routes["/api/releases"]
    
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <entry>
            <title>Title A</title>
            <link href="https://example.com/a"/>
            <updated>2026-06-15T18:00:00Z</updated>
            <content>Content A</content>
        </entry>
    </feed>
    """
    requests_client.response = MockResponse(xml)
    requests_client.side_effect = None
    mock_request_instance.args = {"feed_url": "http://mock-url.xml"}
    
    res, status_code = api_fn()
    assert_eq(status_code, 200)
    assert_eq(len(res), 1)
    assert_eq(res[0]["title"], "Title A")

def test_flask_api_network_failure():
    flask_app = app_module.create_app()
    api_fn = flask_app.routes["/api/releases"]
    
    requests_client.side_effect = ConnectionError("Failed to connect")
    mock_request_instance.args = {"feed_url": "http://mock-url-fail.xml"}
    
    res, status_code = api_fn()
    assert_eq(status_code, 502)
    assert_eq(res, {"error": "Failed to fetch or parse release notes feed"})

def test_flask_api_timeout():
    flask_app = app_module.create_app()
    api_fn = flask_app.routes["/api/releases"]
    
    requests_client.side_effect = Timeout("Request timed out")
    mock_request_instance.args = {"feed_url": "http://mock-url-timeout.xml"}
    
    res, status_code = api_fn()
    assert_eq(status_code, 502)
    assert_eq(res, {"error": "Failed to fetch or parse release notes feed"})

def test_flask_api_http_errors():
    flask_app = app_module.create_app()
    api_fn = flask_app.routes["/api/releases"]
    
    for err_code in [404, 500, 503]:
        requests_client.side_effect = None
        requests_client.response = MockResponse("", status_code=err_code)
        mock_request_instance.args = {"feed_url": f"http://mock-url-err-{err_code}.xml"}
        
        res, status_code = api_fn()
        assert_eq(status_code, 502)
        assert_eq(res, {"error": "Failed to fetch or parse release notes feed"})

def test_flask_api_invalid_content_type():
    flask_app = app_module.create_app()
    api_fn = flask_app.routes["/api/releases"]
    
    requests_client.side_effect = None
    requests_client.response = MockResponse('{"status": "error"}')
    mock_request_instance.args = {"feed_url": "http://mock-url-json.xml"}
    
    res, status_code = api_fn()
    assert_eq(status_code, 502)
    assert_eq(res, {"error": "Failed to fetch or parse release notes feed"})

def test_flask_api_unexpected_exception():
    flask_app = app_module.create_app()
    api_fn = flask_app.routes["/api/releases"]
    
    # Temporarily override fetch_and_parse_feed in the parsed module
    original_fetch = parser_module.fetch_and_parse_feed
    try:
        parser_module.fetch_and_parse_feed = lambda **kwargs: exec("raise(MemoryError('Out of memory'))")
        mock_request_instance.args = {"feed_url": "http://mock-url.xml"}
        
        res, status_code = api_fn()
        assert_eq(status_code, 502)
        assert_eq(res, {"error": "Failed to fetch or parse release notes feed"})
    finally:
        parser_module.fetch_and_parse_feed = original_fetch


# -----------------------------------------------------------------
# 7. Main Execution block
# -----------------------------------------------------------------
if __name__ == "__main__":
    print("=== STARTING ADVERSARIAL SANDBOX TESTS ===")
    
    # Date tests
    run_test("ISO 8601 with Z", test_date_iso_z)
    run_test("ISO 8601 with timezone offset", test_date_iso_offset)
    run_test("RFC 2822 GMT", test_date_rfc2822)
    run_test("Date-only YYYY-MM-DD", test_date_only)
    run_test("ISO 8601 with subseconds", test_date_subseconds)
    run_test("Space separator date", test_date_space_sep)
    run_test("RFC 2822 numeric offset", test_date_rfc2822_offset)
    run_test("RFC 2822 2-digit year", test_date_rfc2822_2digit_year)
    run_test("Naive local date (assumed UTC)", test_date_naive)
    run_test("Invalid date formats", test_date_invalid)
    
    # XML tests
    run_test("Extreme field lengths (stress test)", test_xml_extreme_lengths)
    run_test("Malformed XML tags", test_xml_malformed_tags)
    run_test("Completely empty XML payload", test_xml_completely_empty)
    run_test("Empty feed (no entries)", test_xml_no_entries)
    run_test("Invalid XML chars (control chars)", test_xml_invalid_chars)
    run_test("Special unicode & escaped html entities", test_xml_special_unicode)
    
    # Flask app tests
    run_test("Flask index page rendering", test_flask_index_route)
    run_test("Flask API success flow", test_flask_api_success)
    run_test("Flask API network DNS failure handling", test_flask_api_network_failure)
    run_test("Flask API timeout handling", test_flask_api_timeout)
    run_test("Flask API HTTP error code handling", test_flask_api_http_errors)
    run_test("Flask API invalid non-XML response handling", test_flask_api_invalid_content_type)
    run_test("Flask API unexpected system exception handling", test_flask_api_unexpected_exception)
    
    print("\n=== TEST RUN COMPLETE ===")
    print(f"Total run: {tests_run}")
    print(f"Total failed: {tests_failed}")
    
    if tests_failed > 0:
        print("Some tests FAILED!")
        sys.exit(1)
    else:
        print("All tests PASSED successfully!")
        sys.exit(0)
