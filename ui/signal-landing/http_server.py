"""Simple HTTP server for the Signal landing page (development only)."""

import http.server
import os
import socketserver

PORT = int(os.environ.get("PORT", "8090"))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)


if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Signal landing page serving at http://localhost:{PORT}")
        httpd.serve_forever()
