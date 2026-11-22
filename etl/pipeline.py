"""ETL Pipeline Coordinator for SmartMart Analytics.

Orchestrates the entire Extract -> Transform -> Load lifecycle.
Provides programmatic access for Flask routes and CLI execution.
"""

import os
import sys
import time

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import Config
from etl.extract import extract_data, ExtractionError
from etl.transform import clean_retail_data, TransformationError
from etl.load import load_to_warehouse, LoadError


def run_etl_pipeline(file_path, sample_invoices=None, reset_dw=True, save_processed=True):
    """Executes the complete end-to-end ETL pipeline.

    Args:
        file_path (str): Path to raw Excel or CSV dataset.
        sample_invoices (int, optional): Number of complete invoices to sample.
        reset_dw (bool): Whether to reset the warehouse before loading (default True).
        save_processed (bool): Whether to save cleaned data to data/processed/.

    Returns:
        dict: Consolidated ETL execution summary report.
    """
    start_time = time.time()
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'input_file': os.path.basename(file_path),
        'status': 'STARTED',
        'stages': {}
    }

    try:
        # -------------------------------------------------------------
        # Stage 1: EXTRACT
        # -------------------------------------------------------------
        raw_df, extract_summary = extract_data(file_path, sample_invoices=sample_invoices)
        report['stages']['extract'] = extract_summary
        report['raw_record_count'] = extract_summary['raw_record_count']

        # -------------------------------------------------------------
        # Stage 2: TRANSFORM
        # -------------------------------------------------------------
        cleaned_df, cleaning_summary = clean_retail_data(raw_df)
        report['stages']['transform'] = cleaning_summary
        report['cleaned_record_count'] = cleaning_summary['final_cleaned_count']
        report['rejected_record_count'] = cleaning_summary['total_rejected_count']

        # Optionally save processed dataset
        if save_processed:
            os.makedirs(Config.PROCESSED_FOLDER, exist_ok=True)
            processed_path = os.path.join(Config.PROCESSED_FOLDER, 'cleaned_online_retail.csv')
            cleaned_df.to_csv(processed_path, index=False)
            report['processed_file_path'] = processed_path

        # -------------------------------------------------------------
        # Stage 3: LOAD
        # -------------------------------------------------------------
        load_summary = load_to_warehouse(cleaned_df, reset_dw=reset_dw)
        report['stages']['load'] = load_summary
        report['loaded_fact_record_count'] = load_summary['loaded_fact_records']
        report['total_facts_in_dw'] = load_summary['total_facts_in_dw']

        # Consolidated status
        duration = round(time.time() - start_time, 2)
        report['status'] = 'SUCCESS'
        report['execution_time_seconds'] = duration
        report['message'] = (
            f"ETL completed successfully in {duration}s! "
            f"Extracted {report['raw_record_count']:,} raw records, "
            f"cleaned {report['cleaned_record_count']:,} valid records "
            f"({report['rejected_record_count']:,} rejected), "
            f"and loaded {report['loaded_fact_record_count']:,} rows into Fact_Sales."
        )

        return report

    except (ExtractionError, TransformationError, LoadError) as etl_err:
        report['status'] = 'FAILED'
        report['error'] = str(etl_err)
        report['execution_time_seconds'] = round(time.time() - start_time, 2)
        return report

    except Exception as general_err:
        report['status'] = 'FAILED'
        report['error'] = f"Unexpected error during ETL pipeline: {str(general_err)}"
        report['execution_time_seconds'] = round(time.time() - start_time, 2)
        return report


if __name__ == '__main__':
    default_dataset = os.path.join(Config.BASE_DIR, 'data', 'raw', 'Online Retail.xlsx')
    if not os.path.exists(default_dataset):
        print(f"[!] File not found: {default_dataset}")
        sys.exit(1)

    print("=" * 65)
    print(" SmartMart Analytics - Running ETL Pipeline")
    print("=" * 65)
    # For development, sample complete invoices to produce ~10,000-20,000 transaction lines
    res = run_etl_pipeline(default_dataset, sample_invoices=1000, reset_dw=True)
    print(f"Status:       {res['status']}")
    print(f"Message:      {res.get('message', res.get('error'))}")
    if res['status'] == 'SUCCESS':
        print(f"Time Taken:   {res['execution_time_seconds']} seconds")
        print("\nCleaning Rules Summary:")
        for r in res['stages']['transform']['cleaning_rules']:
            removed = r.get('records_removed', 0)
            modified = r.get('records_modified', 0)
            print(f" - {r['rule']}: removed {removed}, modified {modified}")
    print("=" * 65)
