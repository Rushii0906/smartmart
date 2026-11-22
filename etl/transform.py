"""ETL Stage 2: Transformation Module for SmartMart Analytics.

Implements all syllabus data cleaning, validation, and feature derivation rules:
1. Duplicate removal
2. Cancellation removal (InvoiceNo starting with 'C')
3. Non-positive quantity removal (Quantity <= 0)
4. Non-positive price removal (UnitPrice <= 0)
5. Missing product description imputation
6. Missing CustomerID mapping to 'UNKNOWN'
7. InvoiceDate parsing and calendar attribute extraction
8. Additive measure calculation: TotalAmount = Quantity * UnitPrice
9. Detailed cleaning summary generation
"""

import pandas as pd
import numpy as np


class TransformationError(Exception):
    """Custom exception raised for data transformation errors."""
    pass


def clean_retail_data(df):
    """Transforms raw retail transaction data into cleaned, dimensionally compliant data.

    Preserves the original DataFrame and returns a cleaned DataFrame along with
    a comprehensive cleaning statistics summary.

    Args:
        df (pd.DataFrame): Raw DataFrame with retail columns.

    Returns:
        tuple: (cleaned_df: pd.DataFrame, cleaning_report: dict)
    """
    if df is None or df.empty:
        raise TransformationError("Cannot transform an empty or None DataFrame.")

    # Work on a fresh copy to preserve original dataset
    data = df.copy()
    initial_count = len(data)

    cleaning_rules_applied = []

    # -------------------------------------------------------------
    # Rule 1: Remove Duplicate Transaction Lines
    # -------------------------------------------------------------
    duplicate_mask = data.duplicated()
    duplicate_count = int(duplicate_mask.sum())
    data = data[~duplicate_mask].copy()

    cleaning_rules_applied.append({
        'rule': 'Duplicate Row Removal',
        'description': 'Removed identical transaction records appearing multiple times in the dataset.',
        'records_removed': duplicate_count,
        'records_modified': 0,
        'records_retained': len(data)
    })

    # -------------------------------------------------------------
    # Rule 2: Remove Cancelled Invoices (InvoiceNo starting with 'C' or 'c')
    # -------------------------------------------------------------
    data['InvoiceNo'] = data['InvoiceNo'].astype(str).str.strip()
    cancellation_mask = data['InvoiceNo'].str.upper().str.startswith('C')
    cancelled_count = int(cancellation_mask.sum())
    data = data[~cancellation_mask].copy()

    cleaning_rules_applied.append({
        'rule': 'Cancelled Transactions Removal',
        'description': 'Filtered out cancelled or refunded orders where InvoiceNo begins with "C".',
        'records_removed': cancelled_count,
        'records_modified': 0,
        'records_retained': len(data)
    })

    # -------------------------------------------------------------
    # Rule 3: Remove Non-Positive Quantities (Quantity <= 0)
    # -------------------------------------------------------------
    data['Quantity'] = pd.to_numeric(data['Quantity'], errors='coerce')
    invalid_qty_mask = data['Quantity'].isna() | (data['Quantity'] <= 0)
    invalid_qty_count = int(invalid_qty_mask.sum())
    data = data[~invalid_qty_mask].copy()
    data['Quantity'] = data['Quantity'].astype(int)

    cleaning_rules_applied.append({
        'rule': 'Non-Positive Quantity Removal',
        'description': 'Filtered out damaged goods, write-offs, or transactions with Quantity <= 0.',
        'records_removed': invalid_qty_count,
        'records_modified': 0,
        'records_retained': len(data)
    })

    # -------------------------------------------------------------
    # Rule 4: Remove Non-Positive Unit Prices (UnitPrice <= 0)
    # -------------------------------------------------------------
    data['UnitPrice'] = pd.to_numeric(data['UnitPrice'], errors='coerce')
    invalid_price_mask = data['UnitPrice'].isna() | (data['UnitPrice'] <= 0)
    invalid_price_count = int(invalid_price_mask.sum())
    data = data[~invalid_price_mask].copy()
    data['UnitPrice'] = data['UnitPrice'].round(2)

    cleaning_rules_applied.append({
        'rule': 'Non-Positive Price Removal',
        'description': 'Filtered out zero-price promotional adjustments, sample items, or gifts (UnitPrice <= 0).',
        'records_removed': invalid_price_count,
        'records_modified': 0,
        'records_retained': len(data)
    })

    # -------------------------------------------------------------
    # Rule 5: Handle Missing Product Descriptions
    # -------------------------------------------------------------
    data['StockCode'] = data['StockCode'].astype(str).str.strip().str.upper()
    missing_desc_mask = data['Description'].isna() | (data['Description'].astype(str).str.strip() == '')
    missing_desc_count = int(missing_desc_mask.sum())
    data['Description'] = data['Description'].fillna('UNKNOWN DESCRIPTION').astype(str).str.strip()

    cleaning_rules_applied.append({
        'rule': 'Product Description Imputation',
        'description': 'Standardized text and imputed missing descriptions with "UNKNOWN DESCRIPTION".',
        'records_removed': 0,
        'records_modified': missing_desc_count,
        'records_retained': len(data)
    })

    # -------------------------------------------------------------
    # Rule 6: Map Missing Customer IDs to 'UNKNOWN' Member
    # -------------------------------------------------------------
    missing_cust_mask = data['CustomerID'].isna() | (data['CustomerID'].astype(str).str.strip() == '')
    missing_cust_count = int(missing_cust_mask.sum())

    def format_customer_id(val):
        if pd.isna(val) or str(val).strip() == '' or str(val).lower() == 'nan':
            return 'UNKNOWN'
        # Format integer values cleanly without trailing decimal point (e.g. 17850.0 -> 17850)
        try:
            val_float = float(val)
            if val_float.is_integer():
                return str(int(val_float))
            return str(val).strip()
        except (ValueError, TypeError):
            return str(val).strip()

    data['CustomerID'] = data['CustomerID'].apply(format_customer_id)

    cleaning_rules_applied.append({
        'rule': 'Customer Identifier Normalization',
        'description': 'Mapped guest checkouts and missing CustomerIDs to the dimension member "UNKNOWN".',
        'records_removed': 0,
        'records_modified': missing_cust_count,
        'records_retained': len(data)
    })

    # -------------------------------------------------------------
    # Rule 7: Parse InvoiceDate & Derive Calendar Dimension Attributes
    # -------------------------------------------------------------
    data['InvoiceDate'] = pd.to_datetime(data['InvoiceDate'], errors='coerce')
    invalid_date_mask = data['InvoiceDate'].isna()
    invalid_date_count = int(invalid_date_mask.sum())
    if invalid_date_count > 0:
        data = data[~invalid_date_mask].copy()
        cleaning_rules_applied.append({
            'rule': 'Invalid Date Removal',
            'description': 'Removed rows with unparseable InvoiceDate timestamps.',
            'records_removed': invalid_date_count,
            'records_modified': 0,
            'records_retained': len(data)
        })

    # Derive Date attributes for Dim_Date
    data['FullDate'] = data['InvoiceDate'].dt.date
    data['Date_ID'] = data['InvoiceDate'].dt.strftime('%Y%m%d').astype(int)
    data['DayNumber'] = data['InvoiceDate'].dt.day.astype(int)
    data['MonthNumber'] = data['InvoiceDate'].dt.month.astype(int)
    data['MonthName'] = data['InvoiceDate'].dt.strftime('%B')
    data['QuarterNumber'] = data['InvoiceDate'].dt.quarter.astype(int)
    data['YearNumber'] = data['InvoiceDate'].dt.year.astype(int)

    # -------------------------------------------------------------
    # Rule 8: Normalize Country Name
    # -------------------------------------------------------------
    data['Country'] = data['Country'].fillna('Unspecified').astype(str).str.strip()

    # -------------------------------------------------------------
    # Rule 9: Calculate Measure TotalAmount = Quantity * UnitPrice
    # -------------------------------------------------------------
    data['TotalAmount'] = (data['Quantity'] * data['UnitPrice']).round(2)

    # Final summary statistics
    final_count = len(data)
    total_rejected = initial_count - final_count
    retention_rate = round((final_count / initial_count) * 100, 2) if initial_count > 0 else 0

    cleaning_report = {
        'initial_raw_count': initial_count,
        'final_cleaned_count': final_count,
        'total_rejected_count': total_rejected,
        'retention_rate_pct': retention_rate,
        'rejection_rate_pct': round(100 - retention_rate, 2),
        'unique_invoices': data['InvoiceNo'].nunique(),
        'unique_products': data['StockCode'].nunique(),
        'unique_customers': data['CustomerID'].nunique(),
        'total_quantity_sold': int(data['Quantity'].sum()),
        'total_revenue': round(float(data['TotalAmount'].sum()), 2),
        'cleaning_rules': cleaning_rules_applied
    }

    return data, cleaning_report
