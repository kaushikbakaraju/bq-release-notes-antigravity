import http.server
import threading
import time
import urllib.parse

VALID_FEED = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>BigQuery release notes</title>
    <link>https://cloud.google.com/bigquery/docs/release-notes</link>
    <description>Release notes for BigQuery.</description>
    <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
    <item>
      <title>BigQuery feature update</title>
      <link>https://cloud.google.com/bigquery/docs/release-notes#June_20_2026</link>
      <description>&lt;p&gt;We have released a new feature.&lt;/p&gt;</description>
      <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
      <guid>https://cloud.google.com/bigquery/docs/release-notes#June_20_2026</guid>
    </item>
  </channel>
</rss>
"""

EMPTY_FEED = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>BigQuery release notes</title>
    <link>https://cloud.google.com/bigquery/docs/release-notes</link>
    <description>Release notes for BigQuery.</description>
    <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
  </channel>
</rss>
"""

MALFORMED_FEED = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>BigQuery release notes</title>
    <link>https://cloud.google.com/bigquery/docs/release-notes</link>
    <!-- Malformed: Missing closing tags -->
    <item>
      <title>Malformed item
      <description>Missing tags
  </channel>
</rss>
"""

EXTREME_FEED = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>BigQuery release notes</title>
    <link>https://cloud.google.com/bigquery/docs/release-notes</link>
    <description>Release notes for BigQuery.</description>
    <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
    <item>
      <title>""" + "A" * 1000 + """</title>
      <link>https://cloud.google.com/bigquery/docs/release-notes#extreme</link>
      <description>&lt;div&gt;&lt;p&gt;Heavy HTML content&lt;/p&gt;&lt;script&gt;alert('xss')&lt;/script&gt;&lt;iframe src="http://example.com"&gt;&lt;/iframe&gt;&lt;span&gt;Special characters: &amp;lt; &amp;gt; &amp;amp; &amp;quot; &amp;apos; ★ ⚡ 🚀&lt;/span&gt;&lt;/div&gt;</description>
      <pubDate>Sat, 20 Jun 2026 12:00:00 GMT</pubDate>
      <guid>https://cloud.google.com/bigquery/docs/release-notes#extreme</guid>
    </item>
  </channel>
</rss>
"""

class MockRSSRequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging to keep test output clean
        pass

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/feed/valid":
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
            self.end_headers()
            self.wfile.write(VALID_FEED.encode("utf-8"))
        elif path == "/feed/empty":
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
            self.end_headers()
            self.wfile.write(EMPTY_FEED.encode("utf-8"))
        elif path == "/feed/malformed":
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
            self.end_headers()
            self.wfile.write(MALFORMED_FEED.encode("utf-8"))
        elif path == "/feed/extreme":
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
            self.end_headers()
            self.wfile.write(EXTREME_FEED.encode("utf-8"))
        elif path == "/feed/delay":
            # Simulate latency
            time.sleep(2.0)
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
            self.end_headers()
            self.wfile.write(VALID_FEED.encode("utf-8"))
        elif path == "/error/500":
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Internal Server Error")
        elif path == "/error/502":
            self.send_response(502)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bad Gateway")
        elif path == "/error/404":
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")

class MockRSSServer:
    def __init__(self, host="127.0.0.1", port=0):
        self.server = http.server.HTTPServer((host, port), MockRSSRequestHandler)
        self.host = self.server.server_name
        self.port = self.server.server_port
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            if self.thread:
                self.thread.join()

    @property
    def url(self):
        return f"http://{self.host}:{self.port}"
