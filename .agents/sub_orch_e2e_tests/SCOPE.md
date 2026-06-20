# Scope: E2E Test Suite Design and Implementation

## Architecture
- **E2E Test Runner**: Pytest framework using Playwright (or standard Python request/BeautifulSoup/JSDOM request-based testing if headless browser is not required, but since it is E2E web application testing, Playwright is ideal for UI interactions like spinner, refresh click, and sharing intent). Let's use Playwright (`pytest-playwright`) for UI-level E2E tests, and `requests` for API-level E2E tests.
- **Mock RSS Server**: A local HTTP server (using Python's `http.server` or a lightweight `Flask` app dedicated to mocking) that serves custom RSS XML payloads to simulate various feed formats, pagination, large payloads, malformed data, and error statuses (e.g., 404, 500).
- **Stub Web Application**: A dummy implementation of the Flask app (`app.py`, `templates/index.html`, etc.) in the root workspace so that the E2E tests can run, click elements, and check integration. This dummy app will be configured to fetch release notes from the local Mock RSS Server.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Test Infrastructure Setup | Create `tests/conftest.py` containing fixtures for launching/stopping the Mock RSS server and starting the web app. Set up dependencies in `requirements.txt`. | None | DONE |
| 2 | Tier 1 Feature Coverage | Implement >=30 tests in `tests/test_tier1_feature.py` testing happy-paths of the 6 features. | M1 | IN_PROGRESS (b37977ec) |
| 3 | Tier 2 Boundary & Corner Cases | Implement >=30 tests in `tests/test_tier2_boundary.py` testing extreme inputs, malformed XML, empty lists, slow feed responses, and error handling. | M1, M2 | IN_PROGRESS (b37977ec) |
| 4 | Tier 3 & Tier 4 Integration | Implement >=6 pairwise tests in `tests/test_tier3_pairwise.py` and >=5 workloads in `tests/test_tier4_workloads.py`. | M1, M2, M3 | IN_PROGRESS (b37977ec) |
| 5 | Verification & Documentation | Implement a dummy/stub app in workspace root, run the test suite, ensure 100% pass rate, and publish `TEST_READY.md`. | M1, M2, M3, M4 | IN_PROGRESS (b37977ec) |

## Interface Contracts
### Mock RSS Server Endpoint
- **URL**: `http://localhost:5001/feed.xml` (or similar)
- **Behavior**: Returns dynamic RSS feed content based on query parameters or set headers to allow fine-grained test inputs.
- **Error Behavior**: Returns specified HTTP error codes on demand (e.g., `http://localhost:5001/feed.xml?status=500` or `status=404`).

### Web Application Endpoints
- `GET /`: Renders index page.
- `GET /api/releases`: Returns JSON array of parsed release notes.
