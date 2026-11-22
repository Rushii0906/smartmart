"""Test suite for Stage 2: Star Schema, Database Tables, Constraints, and ORM Models."""

import pytest
import pymysql
from database.db_connection import get_pymysql_connection, get_engine
from database.models import DimProduct, DimCustomer, DimDate, DimCountry, FactSales
from app import create_app
from database import db


@pytest.fixture(scope="module")
def db_conn():
    """Provides a raw database connection for schema assertions."""
    conn = get_pymysql_connection(include_db=True)
    yield conn
    conn.close()


def test_star_schema_tables_exist(db_conn):
    """Verify that all 5 Star Schema tables exist in smartmart_dw."""
    expected = {'dim_product', 'dim_customer', 'dim_date', 'dim_country', 'fact_sales'}
    with db_conn.cursor() as cursor:
        cursor.execute("SHOW TABLES;")
        found = {row[list(row.keys())[0]].lower() for row in cursor.fetchall()}
    assert expected.issubset(found), f"Missing tables: {expected - found}"


def test_dim_product_columns(db_conn):
    """Verify columns and types of Dim_Product."""
    with db_conn.cursor() as cursor:
        cursor.execute("DESCRIBE Dim_Product;")
        cols = {row['Field']: row for row in cursor.fetchall()}

    assert 'Product_ID' in cols
    assert 'StockCode' in cols
    assert 'Description' in cols
    assert cols['Product_ID']['Key'] == 'PRI'
    assert 'auto_increment' in cols['Product_ID']['Extra'].lower()


def test_dim_customer_unknown_seed(db_conn):
    """Verify Dim_Customer has the seeded Unknown customer (ID=1)."""
    with db_conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Dim_Customer WHERE Customer_ID = 1;")
        row = cursor.fetchone()

    assert row is not None
    assert row['Customer_ID'] == 1
    assert row['CustomerCode'] == 'UNKNOWN'


def test_dim_date_structure(db_conn):
    """Verify Dim_Date table columns."""
    with db_conn.cursor() as cursor:
        cursor.execute("DESCRIBE Dim_Date;")
        cols = {row['Field']: row for row in cursor.fetchall()}

    for expected_col in ['Date_ID', 'FullDate', 'DayNumber', 'MonthNumber', 'MonthName', 'QuarterNumber', 'YearNumber']:
        assert expected_col in cols


def test_dim_country_structure(db_conn):
    """Verify Dim_Country table structure."""
    with db_conn.cursor() as cursor:
        cursor.execute("DESCRIBE Dim_Country;")
        cols = {row['Field']: row for row in cursor.fetchall()}

    assert 'Country_ID' in cols
    assert 'CountryName' in cols
    assert cols['Country_ID']['Key'] == 'PRI'


def test_fact_sales_foreign_keys(db_conn):
    """Verify foreign key constraints on Fact_Sales."""
    query = """
        SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE() 
          AND TABLE_NAME = 'Fact_Sales' 
          AND REFERENCED_TABLE_NAME IS NOT NULL;
    """
    with db_conn.cursor() as cursor:
        cursor.execute(query)
        fks = cursor.fetchall()

    referenced_tables = {fk['REFERENCED_TABLE_NAME'].lower() for fk in fks}
    assert 'dim_product' in referenced_tables
    assert 'dim_customer' in referenced_tables
    assert 'dim_date' in referenced_tables
    assert 'dim_country' in referenced_tables


def test_orm_models_query():
    """Verify SQLAlchemy ORM models can query the tables within application context."""
    app = create_app()
    with app.app_context():
        # Query Unknown Customer through ORM
        unknown = DimCustomer.query.filter_by(Customer_ID=1).first()
        assert unknown is not None
        assert unknown.CustomerCode == 'UNKNOWN'
        assert unknown.to_dict()['CustomerCode'] == 'UNKNOWN'

        # Count tables
        assert DimProduct.query.count() >= 0
        assert DimDate.query.count() >= 0
        assert DimCountry.query.count() >= 0
        assert FactSales.query.count() >= 0
