import os
import sys
import pytest

# Ensure project root and tests directory are in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from mock_rss_server import MockRSSServer
from app import create_app

@pytest.fixture(scope="session")
def mock_rss_server():
    server = MockRSSServer()
    server.start()
    yield server
    server.stop()

@pytest.fixture
def app(mock_rss_server):
    # Use the mock server for testing by default
    os.environ["RELEASE_NOTES_FEED_URL"] = f"{mock_rss_server.url}/feed/valid"
    app = create_app()
    app.config.update({
        "TESTING": True,
    })
    yield app

@pytest.fixture
def client(app):
    return app.test_client()
