"""Production WSGI Server for SmartMart Analytics using Waitress.

Waitress is a production-quality pure-Python WSGI server with native support
for both Windows and Linux, multi-threaded request processing, and zero external
C-extension dependencies.

Usage:
    python waitress_server.py
"""

import os
from waitress import serve
from wsgi import app

if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    threads = int(os.getenv('WSGI_THREADS', 6))

    print("=" * 65)
    print(" SmartMart Analytics - Production Waitress WSGI Server")
    print(f" Serving on http://{host}:{port} with {threads} worker threads")
    print(" Press Ctrl+C to terminate.")
    print("=" * 65)

    serve(app, host=host, port=port, threads=threads)
