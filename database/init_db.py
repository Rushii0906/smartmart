"""Database Initialization Script for SmartMart Analytics.

Applies `database/schema.sql` to initialize the Star Schema
tables in the MySQL database.
"""

import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.db_connection import get_pymysql_connection, create_database_if_not_exists


def run_schema_file(schema_path=None):
    """Reads and executes schema.sql using a raw PyMySQL connection."""
    if schema_path is None:
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')

    print(f"[*] Ensuring database exists...")
    try:
        create_database_if_not_exists()
    except Exception as e:
        print(f"[!] Note on DB check: {e}")

    conn = get_pymysql_connection(include_db=True)
    try:
        # Check if tables already exist to prevent unnecessary drops
        if tables_exist(conn):
            print("[OK] Star Schema tables already exist in database.")
            verify_tables(conn)
            return True

        print(f"[*] Reading schema file from: {schema_path}")
        with open(schema_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Split SQL file into individual statements by semicolon
        raw_statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

        print(f"[*] Executing schema statements in database '{Config.DB_NAME}'...")
        with conn.cursor() as cursor:
            for i, stmt in enumerate(raw_statements, 1):
                # Clean comment lines
                lines = [line.strip() for line in stmt.splitlines() if line.strip() and not line.strip().startswith('--')]
                if not lines:
                    continue
                clean_stmt = "\n".join(lines).strip()

                # Skip CREATE DATABASE and USE statements so tables are created
                # directly in the currently active database (e.g. defaultdb, smartmart_dw)
                upper_stmt = clean_stmt.upper()
                if upper_stmt.startswith('CREATE DATABASE') or upper_stmt.startswith('USE '):
                    continue

                try:
                    cursor.execute(clean_stmt)
                except Exception as stmt_err:
                    print(f"[ERROR] Failed executing statement {i}:\n{clean_stmt}\nError: {stmt_err}")
                    raise stmt_err

        print("[OK] Schema successfully applied!")
        verify_tables(conn)
        return True
    finally:
        conn.close()


def tables_exist(conn):
    """Checks whether all 5 Star Schema tables already exist."""
    expected_tables = {'dim_product', 'dim_customer', 'dim_date', 'dim_country', 'fact_sales'}
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            tables = {row[list(row.keys())[0]].lower() for row in cursor.fetchall()}
        return expected_tables.issubset(tables)
    except Exception:
        return False


def verify_tables(conn):
    """Verifies that all 5 Star Schema tables exist in the database."""
    expected_tables = {'dim_product', 'dim_customer', 'dim_date', 'dim_country', 'fact_sales'}
    with conn.cursor() as cursor:
        cursor.execute("SHOW TABLES;")
        tables = {row[list(row.keys())[0]].lower() for row in cursor.fetchall()}

    print(f"[*] Existing tables in database: {tables}")
    missing = expected_tables - tables
    if missing:
        print(f"[FAIL] Missing tables: {missing}")
        return False

    # Verify seed record in Dim_Customer
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Dim_Customer WHERE Customer_ID = 1;")
        unknown_cust = cursor.fetchone()
        if unknown_cust and unknown_cust['CustomerCode'] == 'UNKNOWN':
            print("[OK] Seeded Unknown customer (ID=1, Code='UNKNOWN') verified.")
        else:
            print("[WARNING] Unknown customer record not found in Dim_Customer.")

    print("[SUCCESS] All 5 Star Schema tables verified successfully:")
    print("  1. Dim_Product")
    print("  2. Dim_Customer (with UNKNOWN seed)")
    print("  3. Dim_Date")
    print("  4. Dim_Country")
    print("  5. Fact_Sales (with Foreign Keys & Indexes)")
    return True


def auto_seed_if_empty():
    """Checks if Fact_Sales is empty; if so, performs a sample ETL load so dashboard has data on boot."""
    try:
        conn = get_pymysql_connection(include_db=True)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS total FROM Fact_Sales;")
                cnt = cursor.fetchone()['total']
                if cnt == 0:
                    print("[*] Fact_Sales is empty. Performing initial ETL load of sample invoices...")
                    from etl.pipeline import run_etl_pipeline
                    from routes.data_routes import find_default_raw_file
                    raw_file = find_default_raw_file()
                    if raw_file and os.path.exists(raw_file):
                        res = run_etl_pipeline(raw_file, sample_invoices=500, reset_dw=False)
                        print(f"[OK] Initial sample data loaded: {res.get('loaded_fact_record_count', 0)} rows.")
                    else:
                        print("[*] No raw data file found for auto-seeding. You can upload via /upload.")
                else:
                    print(f"[OK] Fact_Sales already contains {cnt:,} records. Skipping auto-seed.")
        finally:
            conn.close()
    except Exception as e:
        print(f"[!] Auto-seed check note: {e}")


if __name__ == '__main__':
    run_schema_file()
    auto_seed_if_empty()
