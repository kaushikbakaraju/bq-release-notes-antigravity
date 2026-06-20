import os
import logging
from urllib.parse import urlparse
from flask import Flask, jsonify, render_template, request
import release_parser

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app(test_config=None):
    app = Flask(__name__)
    if test_config:
        app.config.update(test_config)

    @app.route("/")
    def index():
        """
        Renders and serves the main frontend template (index.html).
        Flask looks for this template in the 'templates/' folder.
        """
        try:
            return render_template("index.html")
        except Exception as e:
            logger.error(f"Failed to render index template: {str(e)}")
            # Under catastrophic UI failure, return a clean error message to the client
            return "Internal Server Error: Frontend template index.html not found.", 500


    @app.route("/api/releases", methods=["GET"])
    def get_releases():
        """
        Exposes GET /api/releases.
        Fetches the BigQuery release notes and parses them into a JSON array.
        Gracefully handles downtime, timeouts, network issues, and XML parser failures
        by returning 502 (Bad Gateway) or 500 (Internal Server Error) with a contract-compliant error message.
        """
        try:
            feed_url = request.args.get("feed_url")
            if feed_url:
                parsed = urlparse(feed_url)
                hostname = parsed.hostname
                if not hostname:
                    return jsonify({"error": "Invalid URL"}), 400
                hostname = hostname.lower()
                
                is_allowed = False
                if hostname in ("127.0.0.1", "localhost"):
                    is_allowed = True
                elif hostname in ("docs.cloud.google.com", "cloud.google.com") or hostname.endswith(".google.com"):
                    is_allowed = True
                    
                if not is_allowed:
                    return jsonify({"error": "Unsafe URL"}), 400

            # Fetch and parse using the parser module
            releases = release_parser.fetch_and_parse_feed(feed_url=feed_url)
            return jsonify(releases), 200
            
        except (ValueError, Exception) as e:
            # log the exact traceback/message for debugging
            logger.error(f"Error serving release notes API: {str(e)}", exc_info=True)
            
            # Contract: If RSS feed is unavailable or parsing fails, return status code 500 or 502
            # with JSON body: {"error": "Failed to fetch or parse release notes feed"}
            # Returning 502 Bad Gateway is appropriate for external resource failure (downtime/network).
            return jsonify({"error": "Failed to fetch or parse release notes feed"}), 502

    return app


# Define app globally to support: from app import app
app = create_app()


if __name__ == "__main__":
    # Allow port/host overrides via environment variables for testing/deployment flexibility
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    
    app.run(host=host, port=port, debug=debug)
