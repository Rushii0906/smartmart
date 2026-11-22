"""ETL Stage 3: Loading Module for SmartMart Analytics.

Implements database loading for the Star Schema:
- Dimension loading with surrogate key resolution
- Deduplication of dimension members
- Fact table insertion with transaction safety and rollback on failure
- Partial load prevention
"""

import sys
import os
import pymysql
from database.db_connection import get_pymysql_connection


class LoadError(Exception):
    """Custom exception raised when database loading fails."""
    pass


def load_dimensions(cleaned_df, cursor):
    """Loads all dimension tables first and returns lookup dictionaries

    mapping source keys to dimension surrogate primary keys.

    Args:
        cleaned_df (pd.DataFrame): Cleaned transaction DataFrame.
        cursor (pymysql.cursors.DictCursor): Active database cursor.

    Returns:
        tuple: (product_map, customer_map, country_map, date_map, dim_counts)
    """
    dim_counts = {}

    # -------------------------------------------------------------
    # 1. Dim_Country
    # -------------------------------------------------------------
    unique_countries = cleaned_df['Country'].unique()
    insert_country_sql = """
        INSERT INTO Dim_Country (CountryName)
        VALUES (%s)
        ON DUPLICATE KEY UPDATE CountryName = VALUES(CountryName);
    """
    cursor.executemany(insert_country_sql, [(c,) for c in unique_countries])
    
    # Retrieve all Country mappings
    cursor.execute("SELECT Country_ID, CountryName FROM Dim_Country;")
    country_map = {row['CountryName']: row['Country_ID'] for row in cursor.fetchall()}
    dim_counts['countries'] = len(country_map)

    # -------------------------------------------------------------
    # 2. Dim_Customer
    # -------------------------------------------------------------
    # Exclude 'UNKNOWN' since it is already seeded with Customer_ID = 1
    unique_customers = [c for c in cleaned_df['CustomerID'].unique() if c != 'UNKNOWN']
    if unique_customers:
        insert_customer_sql = """
            INSERT INTO Dim_Customer (CustomerCode)
            VALUES (%s)
            ON DUPLICATE KEY UPDATE CustomerCode = VALUES(CustomerCode);
        """
        cursor.executemany(insert_customer_sql, [(c,) for c in unique_customers])

    # Retrieve all Customer mappings
    cursor.execute("SELECT Customer_ID, CustomerCode FROM Dim_Customer;")
    customer_map = {row['CustomerCode']: row['Customer_ID'] for row in cursor.fetchall()}
    dim_counts['customers'] = len(customer_map)

    # -------------------------------------------------------------
    # 3. Dim_Product
    # -------------------------------------------------------------
    # Keep the most complete (or first non-empty) description for each unique StockCode
    prod_df = cleaned_df[['StockCode', 'Description']].drop_duplicates(subset=['StockCode']).copy()
    insert_product_sql = """
        INSERT INTO Dim_Product (StockCode, Description)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE Description = VALUES(Description);
    """
    prod_data = [(row['StockCode'], row['Description']) for _, row in prod_df.iterrows()]
    cursor.executemany(insert_product_sql, prod_data)

    # Retrieve all Product mappings
    cursor.execute("SELECT Product_ID, StockCode FROM Dim_Product;")
    product_map = {row['StockCode']: row['Product_ID'] for row in cursor.fetchall()}
    dim_counts['products'] = len(product_map)

    # -------------------------------------------------------------
    # 4. Dim_Date
    # -------------------------------------------------------------
    date_cols = ['Date_ID', 'FullDate', 'DayNumber', 'MonthNumber', 'MonthName', 'QuarterNumber', 'YearNumber']
    unique_dates = cleaned_df[date_cols].drop_duplicates(subset=['Date_ID']).copy()
    insert_date_sql = """
        INSERT INTO Dim_Date (Date_ID, FullDate, DayNumber, MonthNumber, MonthName, QuarterNumber, YearNumber)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE FullDate = VALUES(FullDate);
    """
    date_data = [
        (
            int(row['Date_ID']),
            row['FullDate'],
            int(row['DayNumber']),
            int(row['MonthNumber']),
            str(row['MonthName']),
            int(row['QuarterNumber']),
            int(row['YearNumber'])
        )
        for _, row in unique_dates.iterrows()
    ]
    cursor.executemany(insert_date_sql, date_data)
    cursor.execute("SELECT COUNT(*) AS cnt FROM Dim_Date;")
    dim_counts['dates'] = cursor.fetchone()['cnt']

    return product_map, customer_map, country_map, dim_counts


def load_to_warehouse(cleaned_df, reset_dw=False, batch_size=2000):
    """Loads cleaned retail transactions into the MySQL Star Schema with

    full ACID transaction support and automatic rollback on failure.

    Args:
        cleaned_df (pd.DataFrame): Transformed DataFrame.
        reset_dw (bool): If True, clears existing fact & dimension rows first (preserving UNKNOWN customer).
        batch_size (int): Number of fact records per batch insertion.

    Returns:
        dict: Load summary metrics.
    """
    if cleaned_df is None or cleaned_df.empty:
        raise LoadError("Cannot load empty DataFrame to warehouse.")

    conn = get_pymysql_connection(include_db=True)
    conn.autocommit = False  # Enable explicit transaction control

    try:
        with conn.cursor() as cursor:
            if reset_dw:
                # Reset tables safely adhering to FK constraints
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
                cursor.execute("TRUNCATE TABLE Fact_Sales;")
                cursor.execute("TRUNCATE TABLE Dim_Product;")
                cursor.execute("TRUNCATE TABLE Dim_Country;")
                cursor.execute("TRUNCATE TABLE Dim_Date;")
                cursor.execute("DELETE FROM Dim_Customer WHERE Customer_ID > 1;")
                cursor.execute("ALTER TABLE Dim_Customer AUTO_INCREMENT = 2;")
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

            # Step 1: Load Dimension tables
            product_map, customer_map, country_map, dim_counts = load_dimensions(cleaned_df, cursor)

            # Step 2: Map dimension foreign keys onto facts
            fact_df = cleaned_df.copy()
            fact_df['Product_ID'] = fact_df['StockCode'].map(product_map)
            fact_df['Customer_ID'] = fact_df['CustomerID'].map(customer_map)
            fact_df['Country_ID'] = fact_df['Country'].map(country_map)

            # Validate that all foreign keys resolved
            unresolved_products = int(fact_df['Product_ID'].isna().sum())
            unresolved_customers = int(fact_df['Customer_ID'].isna().sum())
            unresolved_countries = int(fact_df['Country_ID'].isna().sum())

            if unresolved_products > 0 or unresolved_customers > 0 or unresolved_countries > 0:
                raise LoadError(
                    f"Foreign key resolution failed: "
                    f"Product FK missing: {unresolved_products}, "
                    f"Customer FK missing: {unresolved_customers}, "
                    f"Country FK missing: {unresolved_countries}."
                )

            # Step 3: Insert Fact_Sales in batches
            insert_fact_sql = """
                INSERT INTO Fact_Sales (
                    InvoiceNo, Product_ID, Customer_ID, Date_ID, Country_ID,
                    Quantity, UnitPrice, TotalAmount
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            fact_rows = [
                (
                    str(row['InvoiceNo']),
                    int(row['Product_ID']),
                    int(row['Customer_ID']),
                    int(row['Date_ID']),
                    int(row['Country_ID']),
                    int(row['Quantity']),
                    float(row['UnitPrice']),
                    float(row['TotalAmount'])
                )
                for _, row in fact_df.iterrows()
            ]

            total_facts_to_load = len(fact_rows)
            for i in range(0, total_facts_to_load, batch_size):
                chunk = fact_rows[i:i + batch_size]
                cursor.executemany(insert_fact_sql, chunk)

            # Verify total loaded fact records
            cursor.execute("SELECT COUNT(*) AS total_facts FROM Fact_Sales;")
            total_facts_in_dw = cursor.fetchone()['total_facts']

        # Commit all dimension and fact changes as one atomic unit
        conn.commit()

        return {
            'status': 'SUCCESS',
            'dimensions_loaded': dim_counts,
            'loaded_fact_records': total_facts_to_load,
            'total_facts_in_dw': total_facts_in_dw,
            'message': f"Successfully loaded {total_facts_to_load:,} fact records into Fact_Sales."
        }

    except Exception as e:
        # Atomic rollback prevents partial/corrupted loads
        conn.rollback()
        raise LoadError(f"Database load transaction failed and was rolled back: {str(e)}")

    finally:
        conn.close()
