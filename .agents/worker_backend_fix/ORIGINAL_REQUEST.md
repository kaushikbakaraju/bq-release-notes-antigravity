## 2026-06-20T16:29:25Z
You are worker_backend_fix.
Your working directory is: /Users/kaushikbakaraju/KB Mac workspace /Antigravity CLI Workspace/agy-cli-projects/bq-release-notes-antigravity/.agents/worker_backend_fix
Your parent is 49ba918d-1e3b-48ec-a5ae-484ce485acb4.

Your objective is to fix and refactor the backend Flask server and feed parser to address the regressions and issues identified by the reviewers and auditors.
Specifically, you must make the following modifications:
1. Rename `parser.py` to `release_parser.py`. To prevent any import errors elsewhere, create a tiny `parser.py` stub that redirects to it:
   ```python
   from release_parser import *
   ```
2. Update `release_parser.py` to:
   - Check both environment variables `RELEASE_NOTES_FEED_URL` and `FEED_URL` if no feed_url is provided.
   - Use `response.content` (bytes) instead of `response.text` inside `feedparser.parse` to avoid UTF-8 encoding scrambling (mojibake).
   - In `parse_date_to_iso8601(date_str)`, normalize timezone offsets without colons (e.g. converting `-0700` to `-07:00` or `+0200` to `+02:00` at the end of the string using a regex match/replace) before calling `fromisoformat`.
   - Retain ValueError exception propagation for empty/missing dates and malformed feeds as required by unit tests.
3. Update `app.py` to:
   - Implement `create_app()` factory function that returns the Flask app. Ensure `app` is still defined globally so both `from app import app` and `from app import create_app` work.
   - In the `GET /api/releases` route, extract the `feed_url` parameter from request arguments: `feed_url = request.args.get("feed_url")`.
   - Implement SSRF validation on `feed_url` using `urllib.parse.urlparse`. Allow only loopback addresses (`127.0.0.1`, `localhost` with any port) and Google domains (`docs.cloud.google.com`, `cloud.google.com` or domains ending in `.google.com`). If an unsafe URL is passed, return 400 Bad Request.
   - Pass the validated `feed_url` to `parser.fetch_and_parse_feed(feed_url=feed_url)`.
4. Update `requirements.txt` to include `python-dateutil>=2.8.2`.
5. Update the placeholder `templates/index.html` to include the expected M3 elements with exact IDs and text to satisfy the test suite (`tests/test_infra_check.py`):
   - `<h1>BigQuery Release Notes</h1>` (matching exact text)
   - `<button id="refresh-btn">Refresh</button>`
   - `<div id="spinner-container"></div>`
   - `<div id="releases-list"></div>`
6. Rename `tests/test_parser.py` to `tests/test_release_parser.py` (delete `tests/test_parser.py`). Update imports inside it to use `release_parser as parser` and verify it runs successfully.

Make sure to run the unit test suite locally to verify that all tests pass.
You can execute:
`python -m pytest tests/test_release_parser.py -v --cov`
and:
`python -m pytest tests/test_infra_check.py -v`

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

When completed, write `handoff.md` with:
1. Command run to execute tests and the test output.
2. Code layout compliance.
3. Notify the parent via send_message.
