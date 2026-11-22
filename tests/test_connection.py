"""Test suite for Stage 1: Configuration, Directory Setup, and Database Connectivity."""

import os
import pytest
from config import Config
from app import create_app
from database.db_connection import test_connection_diagnostics as run_db_diagnostics


def test_config_loading():
    """Verify that configuration constants and environment defaults load properly."""
    assert Config.DB_HOST is not None
    assert Config.DB_PORT == '3306' or int(Config.DB_PORT) > 0
    assert Config.DB_NAME == 'smartmart_dw'
    assert Config.SQLALCHEMY_DATABASE_URI.startswith('mysql+pymysql://')
    assert Config.MAX_CONTENT_LENGTH == 32 * 1024 * 1024
    assert 'xlsx' in Config.ALLOWED_EXTENSIONS
    assert 'csv' in Config.ALLOWED_EXTENSIONS


def test_flask_app_creation():
    """Verify that the Flask application initializes correctly with Config."""
    app = create_app()
    assert app is not None
    assert app.config['DB_NAME'] == 'smartmart_dw'
    assert app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] is False


def test_upload_folders_created():
    """Verify that data/raw and data/processed directories are created."""
    assert os.path.exists(Config.UPLOAD_FOLDER)
    assert os.path.exists(Config.PROCESSED_FOLDER)


def test_db_connection_diagnostic_structure():
    """Verify that test_connection_diagnostics returns the expected dictionary format."""
    diag = run_db_diagnostics()
    assert isinstance(diag, dict)
    assert 'host' in diag
    assert 'port' in diag
    assert 'user' in diag
    assert 'database' in diag
    assert 'server_connected' in diag
    assert 'database_exists' in diag
    assert isinstance(diag['server_connected'], bool)
    assert isinstance(diag['database_exists'], bool)


def test_health_endpoint():
    """Verify that the Flask test client can request the root and health endpoints."""
    app = create_app()
    with app.test_client() as client:
        # Root now serves the executive dashboard HTML
        response = client.get('/')
        assert response.status_code == 200
        assert b'SmartMart' in response.data

        # Health endpoint returns JSON diagnostics
        health_resp = client.get('/health')
        assert health_resp.status_code in [200, 503]
        json_data = health_resp.get_json()
        assert 'host' in json_data
        assert 'database' in json_data
