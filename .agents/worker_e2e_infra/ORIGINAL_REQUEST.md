## 2026-06-20T16:10:27Z

<USER_REQUEST>
You are the worker responsible for Milestone 1 (Test Infrastructure Setup) and Milestone 5 (Stub Implementation) of the E2E Testing Track for the BigQuery Release Notes Web Application.

**Your objectives:**
1. Check the environment. Detect if there is a virtual environment or create one (`.venv`) at the project root. Install pytest, requests, feedparser, Flask, and beautifulsoup4 in `.venv`. Run a check to see if `playwright` is installed and if it is possible to use it (run `playwright install chromium` if needed, but if it fails due to network restrictions, design the E2E tests using `Flask` test client and `BeautifulSoup` to parse HTML, simulating JS refresh by checking Flask endpoints, or using a lightweight JS/DOM mocking approach. Python's Flask test client + requests + BeautifulSoup is preferred as it is robust and network-safe).
2. Design and implement the mock RSS server in `tests/mock_rss_server.py`. It should start a local HTTP server on a background thread. It must support:
   - Serving standard valid RSS feeds.
   - Serving empty RSS feeds.
   - Serving malformed/invalid XML feeds.
   - Serving feeds with extreme values (long titles, heavy HTML, special characters).
   - Returning HTTP errors (500, 502, 404).
   - Simulating network latency (slow feed responses).
3. Create `tests/conftest.py` with fixtures to start/stop the mock RSS server and provide the Flask test client.
4. Implement a dummy/stub version of the web application in the project root:
   - `parser.py`: fetches the RSS feed from the mock server and parses it into the release notes schema.
   - `app.py`: Flask app serving `/` (index.html) and `/api/releases` (JSON response).
   - `templates/index.html`: minimal HTML with a refresh button, spinner container, and update cards with Twitter Web Intent links.
   - `static/app.js` and `static/styles.css` (empty or basic).
5. Verify the infrastructure works by running a simple test `tests/test_infra_check.py` to confirm the mock server responds, the stub app fetches from it, and pytest runs successfully.

**Scope boundaries:**
- Do not write the final production code for parser or frontend UI. Keep the stub implementation as simple as possible to pass the E2E tests.
- All code files must be placed in their correct locations (`app.py`, `parser.py`, `templates/index.html` in root, and tests in `tests/`).

**MANDATORY INTEGRITY WARNING:**
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

**Output Requirements:**
- Write a report in `.agents/worker_e2e_infra/handoff.md` detailing:
  - Steps taken
  - Created files and directories
  - Test runner command and outputs
  - How mock RSS server is structured
  - Stub app details

**Completion Criteria:**
- Virtual environment set up and requirements installed.
- `tests/conftest.py` and `tests/mock_rss_server.py` created and functional.
- Stub web application created.
- `tests/test_infra_check.py` passes and reports successful mock server and stub integration.
</USER_REQUEST>
