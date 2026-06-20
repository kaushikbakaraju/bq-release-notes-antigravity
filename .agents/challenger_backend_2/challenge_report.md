## Challenge Summary

**Overall risk assessment**: CRITICAL

The BigQuery Release Notes Web Application backend contains a critical SSRF vulnerability due to unvalidated `feed_url` query parameters passed directly to `requests.get()`. Additionally, XML parsing is vulnerable to DoS/XXE attacks, character encoding issues (mojibake) due to improper requests response decoding, and crash-sensitivity when encountering a single malformed entry in the feed.

---

## Challenges

### [Critical] Challenge 1: Server-Side Request Forgery (SSRF)

- **Assumption challenged**: The client-provided `feed_url` query parameter is safe to query and always points to a public, benign feed.
- **Attack scenario**: A malicious actor queries the `/api/releases` endpoint with a `feed_url` parameter pointing to:
  - Internal metadata services, e.g., `/api/releases?feed_url=http://169.254.169.254/latest/meta-data/`
  - Internal network ports, e.g., `/api/releases?feed_url=http://localhost:8080/`
  - Non-HTTP protocols, e.g., `/api/releases?feed_url=file:///etc/passwd` (which requests handles differently or fails on, but can probe local schemes).
- **Blast radius**: Critical. Attackers can map internal networks, query local cloud metadata (retrieving sensitive credentials/tokens), or cause local loop requests (denial of service).
- **Mitigation**: Enforce scheme validation (`https` only) and restrict target domains using a strict whitelist (e.g., only allowing `docs.cloud.google.com` or `cloud.google.com`).

### [High] Challenge 2: XML External Entity (XXE) and Entity Expansion (Billion Laughs)

- **Assumption challenged**: The XML payload from the remote feed is well-behaved and does not contain recursive or external entity definitions.
- **Attack scenario**: An attacker specifies a custom `feed_url` pointing to an XML payload containing:
  - Nested entities (Billion Laughs) designed to consume CPU and memory during parsing:
    ```xml
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
      <!-- ... -->
      <!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">
    ]>
    <feed>&lol9;</feed>
    ```
  - External entities referencing local system files.
- **Blast radius**: High. Direct Denial of Service (OOM/CPU exhaustion) of the web server, or potential leakage of internal files.
- **Mitigation**: Disable external entity resolution (DTD resolution) and restrict entity expansion sizes in the underlying XML SAX parser used by `feedparser`.

### [Medium] Challenge 3: Fatal Parser Crash on Single Malformed Entry

- **Assumption challenged**: Feeds will always have perfectly formatted dates and structures for all entries.
- **Attack scenario**: An external feed contains 100 entries. A single entry has a malformed or invalid date. `parser.py` raises `ValueError`, propagating all the way out of `fetch_and_parse_feed`.
- **Blast radius**: Medium. The entire API fails with a `502` error, preventing users from seeing *any* release notes simply because one entry has a bad date string.
- **Mitigation**: Catch parsing exceptions inside the loop. Log a warning for malformed entries, discard/skip them, and continue parsing the other valid entries.

### [Medium] Challenge 4: Encoding Scrambling (Mojibake) via `response.text`

- **Assumption challenged**: `requests` automatically decodes the XML payload using the correct encoding from the XML declaration.
- **Attack scenario**: The feed server responds with `Content-Type: text/xml` or `application/xml` without a charset parameter in the HTTP headers. `requests` defaults to decoding via `ISO-8859-1`. This ignores the XML declaration (`<?xml version="1.0" encoding="utf-8"?>`), causing UTF-8 characters (like emoji or non-ASCII characters) to be scrambled (mojibake) in the output.
- **Blast radius**: Medium. Garbled content display on the frontend.
- **Mitigation**: Pass the raw bytes `response.content` to `feedparser.parse()` instead of `response.text`. `feedparser` is designed to auto-detect XML encoding from the byte declaration directly.

### [Medium] Challenge 5: DoS via Synchronous Resource Exhaustion

- **Assumption challenged**: The external RSS feed host is highly available and responds immediately.
- **Attack scenario**: If the feed server is extremely slow or hangs, a series of concurrent requests will block Flask's synchronous worker threads for the full 10-second timeout.
- **Blast radius**: Medium. Connection/thread pool starvation, making the application unresponsive to all users.
- **Mitigation**: Reduce the HTTP timeout to a lower threshold (e.g., 3 seconds) and implement a background cron worker or local caching layer (e.g., cache-aside or background polling) to serve release notes instantly without block-fetching.

### [Low] Challenge 6: Unhandled Type/Attribute Errors in Date Extraction

- **Assumption challenged**: The parsed properties returned by `feedparser` are always of string type.
- **Attack scenario**: A maliciously constructed XML payload uses attributes or structures that cause `feedparser` to return parsed dates as non-string objects (e.g. dictionaries).
- **Blast radius**: Low. Parser crash due to unhandled `AttributeError` (e.g., `list.strip()`).
- **Mitigation**: Catch `AttributeError` and `TypeError` in the date-parsing block of `parser.py`.

---

## Stress Test Results

A standalone date parsing suite was executed to test the date normalization logic of `parser.py` under various standard and non-standard inputs:

| # | Test Case / Scenario | Expected Behavior | Actual Behavior | Pass/Fail |
|---|----------------------|-------------------|-----------------|-----------|
| 1 | Standard UTC `Z` suffix | Normalizes to `YYYY-MM-DDTHH:MM:SSZ` | Normalised | PASS |
| 2 | Timezone Offsets (+/- hours) | Normalizes and converts to UTC | Normalised | PASS |
| 3 | RFC 2822 standard | Normalizes and converts to UTC | Normalised | PASS |
| 4 | Date-only (`YYYY-MM-DD`) | Normalizes to UTC midnight | Normalised | PASS |
| 5 | Millisecond resolution (`.123Z`) | Truncates subseconds correctly | Truncated | PASS |
| 6 | Milliseconds + timezone offset | Converts to UTC, truncating subseconds | Converted | PASS |
| 7 | Space separator instead of `T` | Normalizes to `T` format | Normalised | PASS |
| 8 | RFC 2822 with numeric offset | Normalizes to UTC correctly | Normalised | PASS |
| 9 | RFC 2822 with 2-digit year | Normalizes correctly to 2026 | Normalised | PASS |
| 10 | Naive local datetime | Normalizes, defaulting to UTC | Normalised | PASS |
| 11 | Out-of-bounds/invalid date strings | Raises `ValueError` | Raised `ValueError` | PASS |
| 12 | `None` and empty string | Raises `ValueError` | Raised `ValueError` | PASS |

---

## Unchallenged Areas

- **Frontend Browser Execution (JS/CSS)**: The Javascript interaction and Twitter sharing integration were not stress-tested via browser E2E (e.g. Selenium/Playwright) because running GUI tests requires a graphical environment and sandbox bypass, which timed out. 
- **Production Server Workload**: Heavy concurrency tests (e.g. running `locust` or `ab` with 1000+ connections) were not run because it would require starting Gunicorn outside the workspace and potential network access.
