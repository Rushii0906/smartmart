"""ETL Blueprint for SmartMart Analytics.

Handles ETL pipeline execution, cleaning statistics presentation,
and live warehouse dimensional inventory monitoring.
"""

import os
from flask import Blueprint, render_template, request, flash, redirect, url_for
from etl.pipeline import run_etl_pipeline
from database.db_connection import get_pymysql_connection
from routes.data_routes import find_default_raw_file

etl_bp = Blueprint('etl', __name__)


def get_warehouse_table_counts():
    """Queries live record counts for all 5 Star Schema tables."""
    counts = {
        'fact_sales': 0,
        'dim_product': 0,
        'dim_customer': 0,
        'dim_date': 0,
        'dim_country': 0
    }
    conn = get_pymysql_connection(include_db=True)
    try:
        with conn.cursor() as cursor:
            for tbl, key in [
                ('Fact_Sales', 'fact_sales'),
                ('Dim_Product', 'dim_product'),
                ('Dim_Customer', 'dim_customer'),
                ('Dim_Date', 'dim_date'),
                ('Dim_Country', 'dim_country')
            ]:
                try:
                    cursor.execute(f"SELECT COUNT(*) AS total FROM {tbl};")
                    counts[key] = cursor.fetchone()['total']
                except Exception:
                    counts[key] = 0
    finally:
        conn.close()

    return counts


@etl_bp.route('/etl', methods=['GET'])
def etl_view():
    """Renders the ETL execution workspace and dimensional inventory."""
    counts = get_warehouse_table_counts()
    return render_template('etl.html', counts=counts, report=None)


@etl_bp.route('/etl/run', methods=['POST'])
def run_etl():
    """Executes the complete ETL pipeline and displays cleaning summary."""
    sample_val = request.form.get('sample_size', '1000')
    reset_dw = request.form.get('reset_dw') == 'true'

    sample_invoices = None if sample_val == 'all' else int(sample_val)

    # Locate source dataset
    raw_file = find_default_raw_file()
    if not raw_file or not os.path.exists(raw_file):
        flash('No dataset file found in data/raw/. Please upload an Excel or CSV file first.', 'error')
        return redirect(url_for('data.upload'))

    report = run_etl_pipeline(raw_file, sample_invoices=sample_invoices, reset_dw=reset_dw)

    counts = get_warehouse_table_counts()

    if report.get('status') == 'SUCCESS':
        flash(report['message'], 'success')
    else:
        flash(f"ETL Execution Failed: {report.get('error', 'Unknown error')}", 'error')

    return render_template('etl.html', counts=counts, report=report)
