"""Simple HTTP server for local development of the Signal Dashboard."""

import http.server
import os
import socketserver

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that serves files from the dashboard directory."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)


if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Signal Dashboard serving at http://localhost:{PORT}")
        httpd.serve_forever()
