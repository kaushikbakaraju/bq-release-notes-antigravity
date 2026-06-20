## 2026-06-20T16:15:21Z
You are worker_backend.
Your working directory is: /Users/kaushikbakaraju/KB Mac workspace /Antigravity CLI Workspace/agy-cli-projects/bq-release-notes-antigravity/.agents/worker_backend
Your parent is 49ba918d-1e3b-48ec-a5ae-484ce485acb4.

Your objective is to implement the backend Flask server and feed parser for the Backend Flask Parser milestone (M2).
Specifically, you must write the following files to the project root directory (/Users/kaushikbakaraju/KB Mac workspace /Antigravity CLI Workspace/agy-cli-projects/bq-release-notes-antigravity/):
1. `requirements.txt`: List of dependencies including Flask, feedparser, requests, pytest, and pytest-cov.
2. `parser.py`: Fetch the feed from `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml` (but check RELEASE_NOTES_FEED_URL environment variable first to support testing). Parse XML using feedparser, format dates to ISO 8601 UTC format (YYYY-MM-DDTHH:MM:SSZ), handle connection/SSL/timeout errors, and propagate them.
3. `app.py`: Flask app serving index.html on GET / and exposing GET /api/releases returning JSON. Catch errors from parser and return 500/502 with JSON payload {"error": "Failed to fetch or parse release notes feed"}.
4. `templates/index.html`: A basic placeholder HTML template so that rendering it does not fail.
5. `tests/test_parser.py`: Unit tests using pytest and unittest.mock to mock network/parser failures (timeouts, SSL errors, malformed XML, empty XML, invalid dates, valid Atom/RSS).

You can read and copy/adapt the proposed blueprint implementations designed by our explorer in:
- /Users/kaushikbakaraju/KB Mac workspace /Antigravity CLI Workspace/agy-cli-projects/bq-release-notes-antigravity/.agents/explorer_backend_1/proposed_parser.py
- /Users/kaushikbakaraju/KB Mac workspace /Antigravity CLI Workspace/agy-cli-projects/bq-release-notes-antigravity/.agents/explorer_backend_1/proposed_app.py
- /Users/kaushikbakaraju/KB Mac workspace /Antigravity CLI Workspace/agy-cli-projects/bq-release-notes-antigravity/.agents/explorer_backend_1/proposed_test_parser.py

Make sure to initialize a Python virtual environment to install dependencies and run unit tests.
Use `python -m pytest tests/test_parser.py -v --cov` to run the test suite and verify test execution.

DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

When completed, write `handoff.md` with:
1. Command run to execute tests and the test output.
2. Code layout compliance.
3. Notify the parent via send_message.
