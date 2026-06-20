# Challenge Report

## Challenge Summary

**Overall risk assessment**: MEDIUM

While the logic for date parsing, XML parsing, and error propagation in both `parser.py` and `app.py` is highly robust and successfully handles empty feeds, malformed tags, timeouts, network downtime, and invalid characters, there is a significant design/security risk concerning the exposed `feed_url` query parameter.

---

## Challenges

### [Medium] Challenge 1: Server-Side Request Forgery (SSRF) via `feed_url` Parameter

- **Assumption challenged**: Exposing the `feed_url` query parameter to client requests is safe.
- **Attack scenario**: A malicious client invokes the endpoint with a custom `feed_url` targeting sensitive internal infrastructure:
  ```
  GET /api/releases?feed_url=http://169.254.169.254/computeMetadata/v1/
  ```
  or targets internal services (e.g., databases, admin panels) that are only accessible from the Flask backend.
- **Blast radius**: SSRF, information disclosure, internal network mapping.
- **Mitigation**: 
  - Restrict the `feed_url` query parameter to testing environments only (e.g., check `app.config.get('TESTING')` before accepting it).
  - Alternatively, validate that the query parameter URL belongs to an allowed list or domain (e.g., only `docs.cloud.google.com`).

### [Medium] Challenge 2: Resource Exhaustion / Denial of Service (DoS) via `feed_url`

- **Assumption challenged**: The server has sufficient resources to process any response returned from the `feed_url`.
- **Attack scenario**: A client passes a URL to a massive file (e.g., 500MB XML or infinite stream) as the `feed_url` parameter. Because `requests.get` loads the full response text into memory and `xml.etree`/`feedparser` parse the whole structure, this will cause memory spike and OOM crash.
- **Blast radius**: Denial of Service (DoS) for all users of the web application.
- **Mitigation**: 
  - Restrict the maximum size of the response read from requests (e.g. using streaming chunk reading with byte limit).
  - Limit the accepted URLs or disable client-supplied URLs entirely in production.

---

## Stress Test Results

The Flask backend and parser were subjected to 23 distinct adversarial test cases covering date normalization, XML payload stress, and network exception handling.

| Scenario | Expected Behavior | Actual Behavior | Pass/Fail |
|---|---|---|---|
| **ISO 8601 with Z** | Correctly parsed to standard ISO 8601 UTC Z format | `2026-06-15T18:00:00Z` | **PASS** |
| **ISO 8601 offset** | Normalized to UTC (e.g., PDT/EDT/etc.) | `2026-06-15T17:00:00Z` | **PASS** |
| **RFC 2822 GMT** | Parsed successfully | `2026-06-15T18:00:00Z` | **PASS** |
| **Date-only YYYY-MM-DD** | Parsed and timestamp set to midnight UTC | `2026-06-15T00:00:00Z` | **PASS** |
| **ISO 8601 subseconds** | Truncated subseconds and returned Z format | `2026-06-15T18:00:00Z` | **PASS** |
| **Space separator** | Standardized space to 'T' | `2026-06-15T18:00:00Z` | **PASS** |
| **RFC 2822 offset** | Normalized from timezone offset to UTC Z | `2026-06-15T12:30:00Z` | **PASS** |
| **RFC 2822 2-digit year** | Resolved 2-digit year correctly | `2026-06-15T18:00:00Z` | **PASS** |
| **Naive local date** | Defaults to UTC Z | `2026-06-15T18:00:00Z` | **PASS** |
| **Invalid date formats** | Throws `ValueError` | Raised `ValueError` | **PASS** |
| **Extreme field lengths** | Processed 100K char title and 1MB content safely | Processed and returned | **PASS** |
| **Malformed XML tags** | Detected malformed structure and raised `ValueError` | Raised `ValueError` | **PASS** |
| **Completely empty XML** | Detected empty body and raised `ValueError` | Raised `ValueError` | **PASS** |
| **Empty feed (no entries)**| Returns empty list `[]` | Returned `[]` | **PASS** |
| **Invalid XML chars** | Control chars like `\x00` fail parsing | Raised `ValueError` | **PASS** |
| **Special Unicode & Emojis**| Emits high Unicode and HTML entities correctly | Rendered `★ ⚡ 🚀` | **PASS** |
| **Flask index route** | Serves frontend template | Served index.html | **PASS** |
| **Flask API success** | Calls feed and returns release note list | Returned release array | **PASS** |
| **Flask API DNS failure** | Catch connection error and return 502 JSON | Returned 502 with error JSON | **PASS** |
| **Flask API timeout** | Catch request timeout and return 502 JSON | Returned 502 with error JSON | **PASS** |
| **Flask API HTTP errors** | Catch 404, 500, 503 from feed and return 502 JSON | Returned 502 with error JSON | **PASS** |
| **Flask API non-XML resp**| Catch bad content type (JSON) and return 502 JSON | Returned 502 with error JSON | **PASS** |
| **Flask API unexpected exc**| Catch system error (MemoryError) and return 502 JSON| Returned 502 with error JSON | **PASS** |

---

## Unchallenged Areas

- **Frontend JS/UI Integration**: Client-side UI layout and JavaScript browser behavior (AJAX triggers, spinner rendering, Twitter intent generation) are out of scope for backend parser/server validation.
- **Concurrent Request Load**: Multithreaded stress testing (e.g. 1000 concurrent requests to `/api/releases`) was not performed as it requires a multi-user environment setup.
