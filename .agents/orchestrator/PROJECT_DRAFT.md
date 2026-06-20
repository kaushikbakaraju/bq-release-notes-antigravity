# Project: BigQuery Release Notes Web Application

## Architecture
- **Backend (Flask)**: Fetches `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml` using `requests` (or `urllib`), parses it using `feedparser` (or `xml.etree.ElementTree` / `BeautifulSoup`), and exposes `GET /api/releases` returning a JSON list of structured release objects. Serves frontend on `GET /`.
- **Frontend (Vanilla HTML/CSS/JS)**: Clean single-page interface with CSS theme, showing updates in reverse chronological order. A refresh button triggers AJAX fetch, displaying a spinner. Each update card features a Twitter Web Intent share button.
- **Git/GitHub**: Git repo initialized locally, remote created using `gh repo create` or git push, and main branch pushed.

## Code Layout
- `app.py`: Flask application serving index and API endpoints.
- `parser.py`: Feed parser module to fetch and parse BigQuery release notes.
- `templates/index.html`: Vanilla HTML frontend template.
- `static/styles.css`: CSS styling for premium layout and transitions.
- `static/app.js`: JavaScript logic (AJAX refresh, spinner, Twitter Web Intent integration).
- `requirements.txt`: Project dependencies (e.g., `Flask`, `feedparser`, `requests`, `gunicorn` / `pytest` for testing).
- `run.sh`: Startup bash script for easy local running.
- `tests/`: Directory containing tests (E2E and unit).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | E2E Test Suite | E2E Testing Track: Design/implement test cases, runner, mock feed server, `TEST_INFRA.md`, and publish `TEST_READY.md` | None | PLANNED |
| 2 | Backend Flask Parser | Implementation Track: Implement Flask server, RSS feed parser, API endpoint `/api/releases` with error handling | M1 | PLANNED |
| 3 | Frontend UI & Sharing | Implementation Track: Implement HTML layout, premium styles, JS refresh, dynamic update with spinner, Twitter sharing | M1, M2 | PLANNED |
| 4 | GitHub Setup & Push | Implementation Track: Initialize Git repo, commit code, create remote GitHub repository, and push main branch | M2, M3 | PLANNED |
| 5 | E2E & Hardening | Implementation Track: Verify 100% E2E test suite passes, perform Tier 5 white-box adversarial coverage hardening | M4 | PLANNED |

## Interface Contracts
### `/api/releases`
- **Method**: `GET`
- **Response**: JSON array of release notes.
- **Release Object Schema**:
  ```json
  {
    "title": "string",
    "link": "string",
    "date": "string (ISO 8601 format, e.g. YYYY-MM-DDTHH:MM:SSZ)",
    "content": "string (HTML or plain text content of the release notes)"
  }
  ```
- **Error Behavior**: If RSS feed is unavailable or parsing fails, returns status code `500` or `502` with a JSON body: `{"error": "Failed to fetch or parse release notes feed"}`.
