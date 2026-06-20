# Scope: Backend Flask Parser Milestone (M2)

## Architecture
- **Backend (Flask)**:
  - `app.py`: Standard Flask application. Exposes `GET /api/releases` returning a JSON list of structured release objects. Serves frontend template `templates/index.html` on `GET /`.
  - `parser.py`: Fetch RSS feed from `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml` and parse the XML to extract title, link, date (ISO 8601), and content.
  - Gracefully handles connection failures / feed parse errors (e.g. returns 500/502 with JSON `{"error": "Failed to fetch or parse release notes feed"}`).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Explore & Design | Design `app.py`, `parser.py` structure and error handling | None | PLANNED |
| 2 | Implementation | Implement Flask server and parser modules | 1 | PLANNED |
| 3 | Review | Verify correctness, completeness, robustness, and API contract | 2 | PLANNED |
| 4 | Challenge | Adversarially test with mock feeds, edge cases, and empty feeds | 3 | PLANNED |
| 5 | Forensic Audit | Verify authentic logic and run static/dynamic integrity checks | 4 | PLANNED |

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

### `/`
- **Method**: `GET`
- **Response**: HTML (renders `templates/index.html`).
