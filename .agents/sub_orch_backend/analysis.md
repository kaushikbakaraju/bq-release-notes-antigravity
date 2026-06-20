# Backend Flask Parser Synthesis & Implementation Plan

## Consensus Findings
1. **Flask API Structure**: Expose `GET /api/releases` returning a JSON array of release notes matching the schema:
   ```json
   {
     "title": "string",
     "link": "string",
     "date": "string (ISO 8601 UTC, e.g. YYYY-MM-DDTHH:MM:SSZ)",
     "content": "string"
   }
   ```
2. **Endpoint `GET /`**: Renders and serves `templates/index.html`.
3. **Target Files**:
   - `app.py` (Flask routes, error handling)
   - `parser.py` (fetching, parsing, date normalization)
   - `requirements.txt` (dependencies: Flask, feedparser, requests, pytest)
   - `tests/test_parser.py` (unit tests mocking network/parser failures)
4. **Resiliency**: Must handle network timeouts (e.g. 10s timeout), SSL verification errors, empty feeds, and malformed XML. Under error conditions, return a `500` or `502` status code with JSON `{"error": "Failed to fetch or parse release notes feed"}`.
5. **Feed URL Overridability**: Check `RELEASE_NOTES_FEED_URL` environment variable first (defaulting to the Google Cloud RSS feed url) to allow testing with local mock servers in E2E tests.

## Resolved Conflicts / Design Decisions
- **Parser Library**: Use `requests` and `feedparser` as they are standard, robust, handle encoding anomalies, and parse Atom/RSS tags natively.
- **Date Normalization**: Convert all parsed times to UTC aware datetimes using standard library methods (`datetime.fromisoformat` and `email.utils.parsedate_to_datetime` with timezone offsets) and format to `%Y-%m-%dT%H:%M:%SZ`.
- **Caching**: To prevent E2E test failures (e.g. Failure/Recovery flow requiring immediate updates), we will use fetch-on-demand as the default. If caching is implemented, it must have a very short TTL or be easily bypassable. Fetch-on-demand is simpler and less error-prone.

## Implementation Steps for Worker
1. Create `requirements.txt` with required libraries (`Flask`, `feedparser`, `requests`, `pytest`, `pytest-cov`).
2. Implement `parser.py` with:
   - `parse_date_to_iso8601(date_str)`: normalizes ISO 8601/RFC 2822 to UTC ISO 8601.
   - `fetch_and_parse_feed(feed_url=None)`: fetches via `requests`, parses via `feedparser`, maps to output schema, raises appropriate errors.
3. Implement `app.py` with:
   - Route `GET /` rendering template `templates/index.html`.
   - Route `GET /api/releases` calling `parser.py`, returning JSON, catching exceptions to return `502`/`500` with the specified JSON payload.
4. Implement `templates/index.html` as a basic placeholder so that `GET /` does not fail (Milestone 3 will implement the actual UI).
5. Implement unit tests in `tests/test_parser.py` using `unittest.mock` to mock `requests.get` for standard success, empty feeds, malformed XML, connection timeouts, SSL errors, and date parsing edge cases.
6. Verify local tests pass successfully.
