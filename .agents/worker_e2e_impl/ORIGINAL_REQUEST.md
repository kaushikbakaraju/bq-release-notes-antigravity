## 2026-06-20T16:19:15Z

You are the worker responsible for Milestones 2, 3, 4, and 5 (E2E Test Suites and Verification) of the E2E Testing Track for the BigQuery Release Notes Web Application.

Your tasks are:
1. Fix bugs in the existing stub web application and configuration:
   - In `app.py`, implement a `create_app()` factory function that initializes and returns the Flask `app` object. The `/api/releases` route must check `request.args.get('feed_url')` first, then fall back to `os.environ.get("RELEASE_NOTES_FEED_URL")`, then fall back to `parser.DEFAULT_FEED_URL`. Pass the determined feed_url to `parser.fetch_and_parse_feed(feed_url=feed_url)`.
   - In `tests/conftest.py`, fix the environment variable configuration by setting `os.environ["RELEASE_NOTES_FEED_URL"]` (not `FEED_URL`), and ensure that it correctly imports `create_app` from `app`.
   - In `templates/index.html`, replace the placeholder with a proper index template that links to `/static/styles.css` and `/static/app.js`, and contains all the required elements used by JavaScript (`refresh-btn`, `spinner-container`, `releases-list`, `error-container`).

2. Implement Tier 1 Feature Coverage E2E Tests in `tests/test_tier1_feature.py` (at least 30 test cases, >=5 per feature):
   - Feature 1: Serve Frontend (5 tests, checking index rendering, CSS/JS link elements, H1 text, refresh button presence, spinner presence).
   - Feature 2: Retrieve Release API (5 tests, checking status 200, JSON schema/list type, release object properties keys, non-empty content).
   - Feature 3: Parse Feed Content (5 tests, checking date conversion to ISO 8601 UTC, parsing title, parsing description, parsing link, handling published/updated dates).
   - Feature 4: Refresh Feed & Spinner (5 tests, checking refresh button triggers updates, caching headers, client endpoints rendering state updates).
   - Feature 5: Tweet Share Intent (5 tests, checking presence of Tweet Share button on card, Twitter Web Intent link format, correct URL-encoding of title/link, target="_blank", correct parameters).
   - Feature 6: API Error Handling (5 tests, checking response code 500/502 on parser failures, correct JSON error schema, graceful recovery).

3. Implement Tier 2 Boundary & Corner Cases in `tests/test_tier2_boundary.py` (at least 30 test cases, >=5 per feature):
   - Feature 1 Frontend boundaries: 5 tests (handling missing templates, special request headers, trailing slashes, duplicate slashes, etc.).
   - Feature 2 API boundaries: 5 tests (very large feed with 1000+ entries, long title/content strings, unicode/emoji contents, content with Javascript/XSS tags to verify safety).
   - Feature 3 Parse boundaries: 5 tests (malformed XML structure, missing optional fields in feed, empty feed entries list, diverse RFC 2822/ISO 8601 dates, invalid dates causing parser exceptions).
   - Feature 4 Refresh boundaries: 5 tests (latency/slow server responses, mock server crash mid-request, rate limit headers, rapid sequential requests).
   - Feature 5 Tweet Share boundaries: 5 tests (empty fields in sharing, very long URLs, special symbols in tweet text like double quotes or ampersands).
   - Feature 6 API Error boundaries: 5 tests (zero byte responses, invalid content types, redirect loops in feed URL, DNS resolution/network timeout simulation).

4. Implement Tier 3 Cross-Feature Combinations in `tests/test_tier3_pairwise.py` (at least 6 tests):
   - Combinations of frontend load/refresh with various feed server states (down, empty, slow, updated, XSS payload).

5. Implement Tier 4 Real-World Application Scenarios in `tests/test_tier4_workloads.py` (at least 5 workloads):
   - Standard user flow, sharing flow, failure/recovery flow, no updates flow, and content-rich feed flow.

6. Run the full test suite using `.venv/bin/pytest` (use BypassSandbox: true if executing shell command to run tests, to ensure proper environment access, but try running normally first). Ensure all tests pass.
7. Generate and write `TEST_READY.md` in the workspace root, summarizing the tests, showing the test runner command, and providing a coverage checklist of all 4 tiers (with counts matching or exceeding 30, 30, 6, 5 respectively, total >= 71).

**MANDATORY INTEGRITY WARNING:**
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

**Output Requirements:**
- Write a report in `.agents/worker_e2e_impl/handoff.md` detailing:
  - Created files and descriptions
  - Test run output showing number of tests passed (must be >= 71)
  - Layout of the tests and how mock RSS server integration was verified.
