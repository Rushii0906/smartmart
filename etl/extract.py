"""ETL Stage 1: Extraction Module for SmartMart Analytics.

Responsible for:
- Validating file extensions (.xlsx, .xls, .csv)
- Ingesting raw retail datasets with Pandas
- Verifying required schema columns
- Returning structured dataset metadata and raw DataFrames
"""

import os
import pandas as pd

# Expected columns in the UCI Online Retail dataset
REQUIRED_COLUMNS = [
    'InvoiceNo',
    'StockCode',
    'Description',
    'Quantity',
    'InvoiceDate',
    'UnitPrice',
    'CustomerID',
    'Country'
]

ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}


class ExtractionError(Exception):
    """Custom exception raised for dataset extraction and validation failures."""
    pass


def allowed_file(filename):
    """Checks if the uploaded file has a supported extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_extension(filepath):
    """Returns the lowercase file extension without the leading dot."""
    return filepath.rsplit('.', 1)[-1].lower() if '.' in filepath else ''


def extract_data(file_path, sample_invoices=None, nrows=None):
    """Extracts retail dataset from Excel or CSV file into a pandas DataFrame.

    Args:
        file_path (str): Absolute or relative path to the data file.
        sample_invoices (int, optional): If specified, samples a subset of complete invoices.
        nrows (int, optional): If specified, limits number of rows read from file.

    Returns:
        tuple: (df: pd.DataFrame, summary: dict)
    """
    if not os.path.exists(file_path):
        raise ExtractionError(f"File not found at path: {file_path}")

    ext = get_file_extension(file_path)
    if ext not in ALLOWED_EXTENSIONS:
        raise ExtractionError(
            f"Unsupported file format '.{ext}'. Supported formats are: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    file_size_bytes = os.path.getsize(file_path)
    file_size_mb = round(file_size_bytes / (1024 * 1024), 2)

    try:
        if ext == 'csv':
            # Try reading with utf-8 or latin-1 encoding
            try:
                df = pd.read_csv(file_path, encoding='utf-8', nrows=nrows)
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='latin1', nrows=nrows)
        elif ext in ['xlsx', 'xls']:
            df = pd.read_excel(file_path, engine='openpyxl' if ext == 'xlsx' else None, nrows=nrows)
        else:
            raise ExtractionError(f"Unsupported extension: {ext}")
    except Exception as e:
        raise ExtractionError(f"Failed to read file '{os.path.basename(file_path)}': {str(e)}")

    # Standardize column names (strip whitespace)
    df.columns = [str(c).strip() for c in df.columns]

    # Validate required columns
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ExtractionError(
            f"Dataset is missing required column(s): {', '.join(missing_cols)}. "
            f"Expected columns: {', '.join(REQUIRED_COLUMNS)}"
        )

    raw_total_records = len(df)
    unique_invoices_count = df['InvoiceNo'].nunique()

    # If sampling by complete invoices is requested (e.g. for development or large datasets)
    if sample_invoices and sample_invoices < unique_invoices_count:
        unique_invoices = df['InvoiceNo'].unique()[:sample_invoices]
        df = df[df['InvoiceNo'].isin(unique_invoices)].copy()

    extracted_records = len(df)

    summary = {
        'filename': os.path.basename(file_path),
        'file_format': ext.upper(),
        'file_size_mb': file_size_mb,
        'raw_record_count': raw_total_records,
        'extracted_record_count': extracted_records,
        'total_invoices': df['InvoiceNo'].nunique(),
        'columns': list(df.columns),
        'status': 'SUCCESS'
    }

    return df, summary


def get_dataset_preview(df, n_rows=10):
    """Returns a JSON-serializable preview of the dataset."""
    preview_df = df.head(n_rows).copy()
    
    # Convert dates to ISO string for clean serialization
    if 'InvoiceDate' in preview_df.columns:
        preview_df['InvoiceDate'] = preview_df['InvoiceDate'].astype(str)

    # Fill NaN for preview display
    preview_df = preview_df.fillna({'CustomerID': 'UNKNOWN', 'Description': '(No Description)'})

    return {
        'columns': list(preview_df.columns),
        'rows': preview_df.to_dict(orient='records'),
        'total_rows': len(df),
        'total_columns': len(df.columns),
        'memory_usage_mb': round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2)
    }
