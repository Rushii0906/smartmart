"""Test suite for Stage 3: ETL Pipeline, Cleaning Rules, and Database Loading."""

import pytest
import pandas as pd
import numpy as np
from etl.extract import allowed_file, extract_data, ExtractionError
from etl.transform import clean_retail_data, TransformationError
from etl.load import load_to_warehouse
from database.db_connection import get_pymysql_connection


@pytest.fixture
def sample_raw_dataframe():
    """Generates a synthetic DataFrame containing intentional dirty records

    to test each transformation rule.
    """
    data = [
        # 1. Valid record
        {'InvoiceNo': '536365', 'StockCode': '85123A', 'Description': 'WHITE HANGING HEART T-LIGHT HOLDER',
         'Quantity': 6, 'InvoiceDate': '2010-12-01 08:26:00', 'UnitPrice': 2.55, 'CustomerID': 17850, 'Country': 'United Kingdom'},
        # 2. Duplicate of record 1
        {'InvoiceNo': '536365', 'StockCode': '85123A', 'Description': 'WHITE HANGING HEART T-LIGHT HOLDER',
         'Quantity': 6, 'InvoiceDate': '2010-12-01 08:26:00', 'UnitPrice': 2.55, 'CustomerID': 17850, 'Country': 'United Kingdom'},
        # 3. Cancelled invoice (starts with C)
        {'InvoiceNo': 'C536379', 'StockCode': 'D', 'Description': 'Discount',
         'Quantity': -1, 'InvoiceDate': '2010-12-01 09:41:00', 'UnitPrice': 27.50, 'CustomerID': 14527, 'Country': 'United Kingdom'},
        # 4. Negative quantity without C
        {'InvoiceNo': '536380', 'StockCode': '84029G', 'Description': 'KNITTED UNION FLAG HOT WATER BOTTLE',
         'Quantity': -5, 'InvoiceDate': '2010-12-01 09:45:00', 'UnitPrice': 3.39, 'CustomerID': 17850, 'Country': 'United Kingdom'},
        # 5. Zero unit price
        {'InvoiceNo': '536381', 'StockCode': '22197', 'Description': 'POPCORN HOLDER',
         'Quantity': 10, 'InvoiceDate': '2010-12-01 09:50:00', 'UnitPrice': 0.00, 'CustomerID': 17850, 'Country': 'United Kingdom'},
        # 6. Negative unit price
        {'InvoiceNo': '536382', 'StockCode': 'B', 'Description': 'Adjust bad debt',
         'Quantity': 1, 'InvoiceDate': '2010-12-01 10:00:00', 'UnitPrice': -11062.06, 'CustomerID': 17850, 'Country': 'United Kingdom'},
        # 7. Missing CustomerID (should map to UNKNOWN)
        {'InvoiceNo': '536383', 'StockCode': '84879', 'Description': 'ASSORTED COLOUR BIRD ORNAMENT',
         'Quantity': 8, 'InvoiceDate': '2010-12-01 10:15:00', 'UnitPrice': 1.69, 'CustomerID': np.nan, 'Country': 'United Kingdom'},
        # 8. Missing Description (should impute)
        {'InvoiceNo': '536384', 'StockCode': '71053', 'Description': None,
         'Quantity': 12, 'InvoiceDate': '2010-12-01 10:30:00', 'UnitPrice': 3.39, 'CustomerID': 17850, 'Country': 'United Kingdom'},
        # 9. Another valid record
        {'InvoiceNo': '536385', 'StockCode': '84406B', 'Description': 'CREAM CUPID HEARTS COAT HANGER',
         'Quantity': 4, 'InvoiceDate': '2010-12-01 11:00:00', 'UnitPrice': 3.25, 'CustomerID': 17850, 'Country': 'United Kingdom'}
    ]
    return pd.DataFrame(data)


def test_allowed_file():
    """Verify that file extension check approves valid extensions and rejects invalid ones."""
    assert allowed_file('sales.xlsx') is True
    assert allowed_file('retail.xls') is True
    assert allowed_file('data.csv') is True
    assert allowed_file('data.CSV') is True
    assert allowed_file('script.py') is False
    assert allowed_file('document.pdf') is False


def test_duplicate_removal(sample_raw_dataframe):
    """Verify Rule 1: duplicate rows are removed."""
    cleaned, report = clean_retail_data(sample_raw_dataframe)
    dup_rule = next(r for r in report['cleaning_rules'] if r['rule'] == 'Duplicate Row Removal')
    assert dup_rule['records_removed'] == 1


def test_cancellation_removal(sample_raw_dataframe):
    """Verify Rule 2: Invoices starting with C are removed."""
    cleaned, report = clean_retail_data(sample_raw_dataframe)
    cancel_rule = next(r for r in report['cleaning_rules'] if r['rule'] == 'Cancelled Transactions Removal')
    assert cancel_rule['records_removed'] == 1
    assert not any(cleaned['InvoiceNo'].str.startswith('C'))


def test_negative_quantity_removal(sample_raw_dataframe):
    """Verify Rule 3: Quantity <= 0 records are removed."""
    cleaned, report = clean_retail_data(sample_raw_dataframe)
    assert (cleaned['Quantity'] > 0).all()


def test_negative_and_zero_price_removal(sample_raw_dataframe):
    """Verify Rule 4: UnitPrice <= 0 records are removed."""
    cleaned, report = clean_retail_data(sample_raw_dataframe)
    assert (cleaned['UnitPrice'] > 0).all()


def test_missing_customer_mapping(sample_raw_dataframe):
    """Verify Rule 6: Missing CustomerIDs map to 'UNKNOWN'."""
    cleaned, report = clean_retail_data(sample_raw_dataframe)
    unknown_cust_rows = cleaned[cleaned['CustomerID'] == 'UNKNOWN']
    assert len(unknown_cust_rows) == 1
    assert unknown_cust_rows.iloc[0]['InvoiceNo'] == '536383'


def test_total_amount_calculation(sample_raw_dataframe):
    """Verify Rule 9: TotalAmount = Quantity * UnitPrice."""
    cleaned, report = clean_retail_data(sample_raw_dataframe)
    expected_totals = (cleaned['Quantity'] * cleaned['UnitPrice']).round(2)
    pd.testing.assert_series_equal(cleaned['TotalAmount'], expected_totals, check_names=False)


def test_date_parsing_and_calendar_attributes(sample_raw_dataframe):
    """Verify Rule 7: Calendar attributes are extracted."""
    cleaned, report = clean_retail_data(sample_raw_dataframe)
    assert 'Date_ID' in cleaned.columns
    assert 'FullDate' in cleaned.columns
    assert 'DayNumber' in cleaned.columns
    assert 'MonthNumber' in cleaned.columns
    assert 'MonthName' in cleaned.columns
    assert 'QuarterNumber' in cleaned.columns
    assert 'YearNumber' in cleaned.columns

    first_row = cleaned.iloc[0]
    assert first_row['Date_ID'] == 20101201
    assert first_row['MonthName'] == 'December'
    assert first_row['QuarterNumber'] == 4
    assert first_row['YearNumber'] == 2010


def test_load_to_warehouse(sample_raw_dataframe):
    """Verify Stage 3 Load: Dimension & Fact tables are correctly loaded."""
    cleaned, _ = clean_retail_data(sample_raw_dataframe)
    load_result = load_to_warehouse(cleaned, reset_dw=False)

    assert load_result['status'] == 'SUCCESS'
    assert load_result['loaded_fact_records'] == len(cleaned)

    # Verify directly in MySQL
    conn = get_pymysql_connection(include_db=True)
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM Fact_Sales;")
        fact_count = cursor.fetchone()['total']
        assert fact_count >= len(cleaned)

        # Check that foreign key for Customer_ID maps to 1 for UNKNOWN
        cursor.execute("""
            SELECT f.Customer_ID, c.CustomerCode 
            FROM Fact_Sales f 
            JOIN Dim_Customer c ON f.Customer_ID = c.Customer_ID 
            WHERE f.InvoiceNo = '536383';
        """)
        unknown_fact = cursor.fetchone()
        assert unknown_fact is not None
        assert unknown_fact['Customer_ID'] == 1
        assert unknown_fact['CustomerCode'] == 'UNKNOWN'
    conn.close()
