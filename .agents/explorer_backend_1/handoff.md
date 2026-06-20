# Handoff Report - Backend Flask Parser Design

## 1. Observation
The following facts were observed directly during the read-only exploration:
- **Workspace Layout**: Listing the root directory `/Users/kaushikbakaraju/KB Mac workspace /Antigravity CLI Workspace/agy-cli-projects/bq-release-notes-antigravity` revealed that the repository is completely greenfield, containing only documentation files:
  - `PROJECT.md`
  - `TEST_INFRA.md`
  - `.agents/` folder (with agent subfolders)
- **Interface Contract**: `PROJECT.md` lines 28–41 specify that:
  - The API endpoint `/api/releases` must return a JSON list of objects with the schema:
    ```json
    {
      "title": "string",
      "link": "string",
      "date": "string (ISO 8601 format, e.g. YYYY-MM-DDTHH:MM:SSZ)",
      "content": "string (HTML or plain text content of the release notes)"
    }
    ```
  - Upon network or parsing error, the endpoint must return HTTP status `500` or `502` with body:
    ```json
    {"error": "Failed to fetch or parse release notes feed"}
    ```
- **Dependencies**: `PROJECT.md` line 14 highlights `Flask`, `feedparser`, and `requests` as expected project requirements.
- **E2E Infrastructure**: `TEST_INFRA.md` lines 18-27 and lines 28-36 list a mock RSS server setup and test suites. Crucially, the feed parser must be capable of receiving a dynamically-configured URL (for pointing to the local mock RSS server) to facilitate E2E opaque-box validation.
- **Network Mode**: The agent is restricted to `CODE_ONLY` mode, preventing real-time connection to `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml`.

---

## 2. Logic Chain
Based on these observations, the design was structured step-by-step:
1. **Configurable Feed URL**: Since `TEST_INFRA.md` details testing with a local mock RSS server, hardcoding the feed URL is a design risk. Therefore, the parser checks the environment variable `RELEASE_NOTES_FEED_URL` first, falling back to the standard Google Cloud URL.
2. **Network Robustness**: Since the external feed could be down or slow (as defined in Tier 4 Failure/Recovery scenarios in `TEST_INFRA.md`), `requests.get` is configured with `timeout=10.0` and `verify=True` to prevent hanging threads and enforce SSL validation.
3. **Lenient XML & Parser Isolation**: `feedparser` was selected because it naturally isolates structural XML warnings (lenient parsing) while providing `feed_data.bozo = 1` for detecting malformed XML. The parser raises a `ValueError` if the XML is fundamentally corrupt or if essential fields like title/date are missing, prompting `app.py` to return the standard JSON error.
4. **Timezone Standardization**: Google release notes feeds utilize timezone offsets (e.g. Pacific Time `-07:00`). To guarantee the ISO 8601 format `YYYY-MM-DDTHH:MM:SSZ` (always UTC), raw date strings are parsed and converted using `datetime.datetime.astimezone(datetime.timezone.utc)` and formatted with `strftime('%Y-%m-%dT%H:%M:%SZ')`.
5. **Separation of Concerns**: Splitting the logic into `app.py` (Flask routes and error handling) and `parser.py` (data fetching/sanitization) isolates the web logic from XML feed quirks, ensuring cleaner testing and maintenance.

---

## 3. Caveats
- **XML Structure Verification**: Due to the `CODE_ONLY` network restriction, we could not fetch the live feed from `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml` to examine it. We assume it follows standard Atom/RSS feed formats.
- **Mock Dependencies**: The design assumes `feedparser`, `requests`, and `Flask` are available in the runtime environment. If they are not installed, the environment setup step must run first.
- **Python Version**: Standard date parser methods like `datetime.fromisoformat` require Python 3.7+, which we assume is available.

---

## 4. Conclusion
The proposed design is robust, complies with the interface contract, and handles edge cases (e.g., timezone differences, network timeouts, bad SSL, and malformed XML). Blueprint files have been written directly to this agent's directory to allow the implementing agent to copy and adapt them directly.

---

## 5. Verification Method
To verify the correctness of the design:
1. Inspect the written blueprint files in this agent folder:
   - `proposed_parser.py`: Feed fetching and XML parsing logic.
   - `proposed_app.py`: Flask web router routing GET `/` and GET `/api/releases`.
   - `proposed_test_parser.py`: Complete mock-based unit tests.
2. The unit test suite can be run using the following command once the environment is set up (assuming the user installs the dependencies in a virtual environment as per `managing-python-dependencies` rules):
   ```bash
   python -m unittest proposed_test_parser.py
   ```
3. Test failures are simulated for timeouts, SSL errors, malformed XML, and invalid date formats, confirming that all failure branches raise the correct exceptions.

---

## 6. Remaining Work
For the implementing agent:
1. Initialize the Python virtual environment and install dependencies (`Flask`, `feedparser`, `requests`, `pytest`, etc.).
2. Write the final production codebase files to the project root:
   - Copy `proposed_parser.py` to `parser.py`.
   - Copy `proposed_app.py` to `app.py`.
   - Copy `proposed_test_parser.py` to `tests/test_parser.py`.
3. Set up the frontend templates folder and create `templates/index.html`.
4. Run the unit tests locally to verify success.
