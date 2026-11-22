"""Database connection helper module for SmartMart Analytics.

Provides connectivity functions using both PyMySQL (raw connections) and
SQLAlchemy (ORM / engine), with connection diagnostics and automatic
database creation helper.
"""

import os
import sys
from urllib.parse import quote_plus

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pymysql
from sqlalchemy import create_engine, text
from config import Config


def get_pymysql_connection(include_db=True):
    """Establishes a raw PyMySQL connection with automated SSL for cloud databases.

    Args:
        include_db (bool): If True, connects directly to the smartmart_dw database.
                           If False, connects to the MySQL server without selecting a DB.

    Returns:
        pymysql.connections.Connection
    """
    params = {
        'host': Config.DB_HOST,
        'port': int(Config.DB_PORT),
        'user': Config.DB_USER,
        'password': Config.DB_PASSWORD,
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
        'autocommit': True
    }
    if include_db:
        params['database'] = Config.DB_NAME

    # Enable SSL for remote cloud databases (e.g. Aiven, AWS RDS, Railway, TiDB Cloud)
    is_remote = Config.DB_HOST not in ('localhost', '127.0.0.1') and not Config.DB_HOST.startswith(('192.168.', '10.', '172.'))
    raw_url = getattr(Config, 'raw_db_url', '') or ''
    has_ssl = 'ssl' in raw_url.lower()

    if is_remote or has_ssl:
        params['ssl'] = {'check_hostname': False}

    return pymysql.connect(**params)


def get_engine(include_db=True):
    """Creates a SQLAlchemy engine.

    Args:
        include_db (bool): Whether to include the database name in the URI.

    Returns:
        sqlalchemy.engine.Engine
    """
    if include_db:
        uri = Config.SQLALCHEMY_DATABASE_URI
    else:
        uri = (
            f"mysql+pymysql://{Config.DB_USER}:{quote_plus(Config.DB_PASSWORD)}"
            f"@{Config.DB_HOST}:{Config.DB_PORT}/?charset=utf8mb4"
        )
    return create_engine(uri, **Config.SQLALCHEMY_ENGINE_OPTIONS)


def create_database_if_not_exists():
    """Connects to the MySQL server and creates the `smartmart_dw` database

    if it does not already exist.
    """
    try:
        conn = get_pymysql_connection(include_db=False)
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            )
        conn.close()
        return True, f"Database '{Config.DB_NAME}' is ready."
    except Exception as e:
        return False, str(e)


def test_connection_diagnostics():
    """Runs step-by-step diagnostics on the MySQL connection.

    Returns a dict with detailed status of:
    - Server reachability
    - Authentication
    - Database existence
    """
    results = {
        'host': Config.DB_HOST,
        'port': Config.DB_PORT,
        'user': Config.DB_USER,
        'database': Config.DB_NAME,
        'server_connected': False,
        'database_exists': False,
        'server_version': None,
        'error': None
    }

    # Step 1: Connect to server without DB
    try:
        conn = get_pymysql_connection(include_db=False)
        with conn.cursor() as cursor:
            cursor.execute("SELECT VERSION() AS version;")
            row = cursor.fetchone()
            results['server_version'] = row['version'] if row else 'Unknown'
            results['server_connected'] = True

            # Step 2: Check if database exists
            cursor.execute(
                "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                "WHERE SCHEMA_NAME = %s;",
                (Config.DB_NAME,)
            )
            results['database_exists'] = cursor.fetchone() is not None
        conn.close()
    except pymysql.MySQLError as err:
        results['error'] = f"MySQL Error [{err.args[0]}]: {err.args[1] if len(err.args) > 1 else str(err)}"
    except Exception as e:
        results['error'] = str(e)

    return results


if __name__ == '__main__':
    print("=" * 60)
    print(" SmartMart Analytics - MySQL Database Diagnostics")
    print("=" * 60)
    diag = test_connection_diagnostics()
    print(f"Host:       {diag['host']}:{diag['port']}")
    print(f"User:       {diag['user']}")
    print(f"Target DB:  {diag['database']}")
    print("-" * 60)

    if diag['server_connected']:
        print(f"[OK] MySQL Server is reachable! Version: {diag['server_version']}")
        if diag['database_exists']:
            print(f"[OK] Database '{diag['database']}' exists and is ready.")
        else:
            print(f"[INFO] Database '{diag['database']}' does not exist yet.")
            print("       Attempting automatic creation...")
            success, msg = create_database_if_not_exists()
            if success:
                print(f"[OK] {msg}")
            else:
                print(f"[ERROR] Failed to create database: {msg}")
    else:
        print("[FAIL] Could not connect to MySQL server.")
        print(f"Error Details: {diag['error']}")
        print("\nTroubleshooting tips:")
        print("1. Ensure MySQL service is running (e.g. MySQL80).")
        print("2. Check DB_USER, DB_PASSWORD, DB_HOST, DB_PORT in .env file.")
    print("=" * 60)
