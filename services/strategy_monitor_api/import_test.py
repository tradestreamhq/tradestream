#!/usr/bin/env python3
"""
Quick import test for Strategy Monitor API
This test catches missing imports and dependencies early in the CI pipeline.
"""

import sys
import os

def test_imports():
    """Test all required imports for the strategy monitor API."""
    errors = []
    
    # Test basic Python imports
    try:
        import json
        print("✅ json imported successfully")
    except ImportError as e:
        errors.append(f"json import failed: {e}")
    
    try:
        import logging
        print("✅ logging imported successfully")
    except ImportError as e:
        errors.append(f"logging import failed: {e}")
    
    try:
        import base64
        print("✅ base64 imported successfully")
    except ImportError as e:
        errors.append(f"base64 import failed: {e}")
    
    try:
        from datetime import datetime, timedelta
        print("✅ datetime imported successfully")
    except ImportError as e:
        errors.append(f"datetime import failed: {e}")
    
    try:
        from typing import List, Dict, Optional
        print("✅ typing imported successfully")
    except ImportError as e:
        errors.append(f"typing import failed: {e}")
    
    # Test database imports
    try:
        import psycopg2
        print("✅ psycopg2 imported successfully")
    except ImportError as e:
        errors.append(f"psycopg2 import failed: {e}")
    
    try:
        import psycopg2.extras
        print("✅ psycopg2.extras imported successfully")
    except ImportError as e:
        errors.append(f"psycopg2.extras import failed: {e}")
    
    # Test HTTP server imports
    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler
        print("✅ http.server imported successfully")
    except ImportError as e:
        errors.append(f"http.server import failed: {e}")
    
    try:
        import urllib.parse
        print("✅ urllib.parse imported successfully")
    except ImportError as e:
        errors.append(f"urllib.parse import failed: {e}")
    
    # Test Flask imports
    try:
        from flask import Flask, request, jsonify
        print("✅ Flask imported successfully")
    except ImportError as e:
        errors.append(f"Flask import failed: {e}")
    
    try:
        from flask_cors import CORS
        print("✅ Flask-CORS imported successfully")
    except ImportError as e:
        errors.append(f"Flask-CORS import failed: {e}")
    
    # Test absl imports
    try:
        from absl import flags
        print("✅ absl.flags imported successfully")
    except ImportError as e:
        errors.append(f"absl.flags import failed: {e}")
    
    try:
        from absl import app as absl_app
        print("✅ absl.app imported successfully")
    except ImportError as e:
        errors.append(f"absl.app import failed: {e}")
    
    # Test main module import
    try:
        # Add the current directory to the path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from main import app, FLAGS
        print("✅ main module imported successfully")
    except ImportError as e:
        errors.append(f"main module import failed: {e}")
    except Exception as e:
        errors.append(f"main module initialization failed: {e}")
    
    return errors

def main():
    """Run the import tests."""
    print("🔍 Testing Strategy Monitor API imports...")
    print("=" * 50)
    
    errors = test_imports()
    
    print("=" * 50)
    if errors:
        print("❌ Import test failed!")
        print("\nErrors found:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("✅ All imports successful!")
        sys.exit(0)

if __name__ == "__main__":
    main() 