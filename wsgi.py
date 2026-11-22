"""WSGI Entry Point for SmartMart Analytics.

Universal application entry point for production WSGI servers
(Gunicorn, Waitress, uWSGI, mod_wsgi, AWS Elastic Beanstalk, Render, etc.).
"""

import os
from app import create_app
from database.db_connection import create_database_if_not_exists

# Initialize database schema if not present on container boot
try:
    create_database_if_not_exists()
except Exception as e:
    print(f"[WSGI Init Warning] Database check skipped or deferred: {e}")

# Expose WSGI application object
app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
