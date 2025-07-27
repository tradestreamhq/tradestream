#!/usr/bin/env python3
"""
Simple HTTP server for Strategy Monitor UI
"""

import http.server
import socketserver
import os
import sys


def main():
    """Start the HTTP server."""
    # Find the UI files in the runfiles directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ui_dir = os.path.join(script_dir, "_main", "ui", "strategy-monitor")

    # If the UI files are not in the expected location, try alternative paths
    if not os.path.exists(ui_dir):
        # Try the current directory
        ui_dir = script_dir
        if not os.path.exists(os.path.join(ui_dir, "index.html")):
            # Try the parent directory
            ui_dir = os.path.dirname(script_dir)
            if not os.path.exists(os.path.join(ui_dir, "index.html")):
                # Try to find the files in the runfiles
                for root, dirs, files in os.walk(script_dir):
                    if "index.html" in files:
                        ui_dir = root
                        break

    print(f"Serving files from: {ui_dir}")
    print(
        f"Available files: {os.listdir(ui_dir) if os.path.exists(ui_dir) else 'Directory not found'}"
    )

    # Change to the directory containing the UI files
    os.chdir(ui_dir)

    # Set up the server
    port = 8080
    handler = http.server.SimpleHTTPRequestHandler

    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Server started at http://localhost:{port}")
        print(f"Serving files from: {os.getcwd()}")
        print("Available files:", os.listdir("."))
        httpd.serve_forever()


if __name__ == "__main__":
    main()
