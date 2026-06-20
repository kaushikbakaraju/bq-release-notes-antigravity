# Original User Request

## Initial Request — 2026-06-20T19:53:38Z

A Python Flask web application with a vanilla HTML/JS/CSS frontend that fetches, parses, and displays BigQuery release notes from the Google Cloud XML feed. It allows refreshing the feed dynamically with a spinner, sharing selected updates to Twitter/X, and is pushed to GitHub.

Working directory: `/Users/kaushikbakaraju/KB Mac workspace /Antigravity CLI Workspace/agy-cli-projects/bq-release-notes-antigravity`
Integrity mode: `development`

## Requirements

### R1. Backend Release Parser (Flask)
A backend service built with Flask that fetches the BigQuery release notes XML feed from `https://docs.cloud.google.com/feeds/bigquery-release-notes.xml` and parses it into structured JSON. It should expose:
*   `GET /`: Serves the frontend web app.
*   `GET /api/releases`: Fetches the live feed, parses entries (title, link, publication date, and description/content), and returns them as a JSON list. It must handle connection errors gracefully.

### R2. Frontend UI & Styling
A clean, responsive, and modern single-page interface using vanilla HTML, CSS, and JS:
*   Display notes in reverse chronological order (newest first).
*   Use a premium color palette (sleek dark/light theme, modern typography like Inter/Outfit, card-based layout for release updates).

### R3. Refresh Action with Loading Spinner
An interactive refresh button:
*   Clicking it triggers an asynchronous request to the backend.
*   A spinner or loading animation must show while the request is pending and hide when completed.
*   The UI must update dynamically with any new/updated notes without reloading the entire page.

### R4. Tweet Selection & Sharing
A "Tweet Update" or share button for each release note:
*   Clicking it constructs an appropriate tweet text (e.g., "[BigQuery Update] <Title> - <Link>") and opens a new browser tab/window to the Twitter Web Intent URL (`https://twitter.com/intent/tweet?text=<encoded_text>`).

### R5. Dependencies & Local Setup
A clean Python environment configuration:
*   A `requirements.txt` listing all necessary packages (e.g., `Flask`, `feedparser` or `requests` + `beautifulsoup4`, `xml.etree.ElementTree`).
*   A startup script or simple guide on how to launch the server locally.

### R6. GitHub Repository Setup and Push
Initialize a local Git repository in the working directory, commit the codebase, and push it to a new remote GitHub repository:
*   Create a public remote GitHub repository named `bq-release-notes-antigravity` (using `gh repo create` or standard git methods).
*   Push the main branch to the remote repository.

## Acceptance Criteria

### Backend Verification
- [ ] Flask server starts up and serves the landing page on port 5000 (or other standard port).
- [ ] `GET /api/releases` returns an HTTP 200 status and a valid JSON list of notes.
- [ ] Each release note object in the JSON list contains `title`, `link`, `date`, and `content`.

### UI & Interaction Verification
- [ ] Landing page loads successfully without CSS/JS errors.
- [ ] Clicking the refresh button shows a visible loading spinner, fires a network request, and updates the list.
- [ ] Each release card has a "Tweet" button.
- [ ] Clicking the "Tweet" button opens a new window pointing to `https://twitter.com/intent/tweet` with the URL-encoded tweet text containing the release title and link.

### GitHub Push Verification
- [ ] A local Git repository exists in the working directory with at least one commit containing the project code.
- [ ] The repository is pushed to a remote GitHub repository named `bq-release-notes-antigravity`.
