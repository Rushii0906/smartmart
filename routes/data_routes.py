"""Dataset Management Blueprint for SmartMart Analytics.

Handles dataset uploading (.xlsx, .xls, .csv), schema verification,
and interactive data previewing.
"""

import os
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from werkzeug.utils import secure_filename
from etl.extract import allowed_file, extract_data, get_dataset_preview, ExtractionError
from config import Config

data_bp = Blueprint('data', __name__)


def find_default_raw_file():
    """Locates an existing dataset file for immediate previewing."""
    # Check processed folder first for quick loading
    processed_file = os.path.join(Config.PROCESSED_FOLDER, 'cleaned_online_retail.csv')
    if os.path.exists(processed_file):
        return processed_file

    raw_dir = Config.UPLOAD_FOLDER
    if not os.path.exists(raw_dir):
        return None

    # Check for Online Retail.xlsx or any .xlsx/.csv
    candidates = ['online_retail.csv', 'Online Retail.csv', 'Online Retail.xlsx']
    for cand in candidates:
        full_path = os.path.join(raw_dir, cand)
        if os.path.exists(full_path):
            return full_path

    # Otherwise return first valid file found
    for f in os.listdir(raw_dir):
        if allowed_file(f):
            return os.path.join(raw_dir, f)

    return None


@data_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    """Handles raw dataset upload and shows preview."""
    preview = None

    if request.method == 'POST':
        # Check if file part exists
        if 'dataset_file' not in request.files:
            flash('No file part provided in upload request.', 'error')
            return redirect(request.url)

        file = request.files['dataset_file']
        if file.filename == '':
            flash('No file was selected for upload.', 'error')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Invalid file extension. Please upload a .xlsx, .xls, or .csv file.', 'error')
            return redirect(request.url)

        try:
            filename = secure_filename(file.filename)
            os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
            saved_path = os.path.join(Config.UPLOAD_FOLDER, filename)
            file.save(saved_path)

            # Validate columns & generate preview
            raw_df, summary = extract_data(saved_path, sample_invoices=20)
            preview = get_dataset_preview(raw_df, n_rows=10)

            flash(f"Successfully uploaded '{filename}'! Found {summary['raw_record_count']:,} total transaction records.", 'success')
            return render_template('upload.html', preview=preview)

        except ExtractionError as ext_err:
            flash(f"Dataset Validation Error: {str(ext_err)}", 'error')
        except Exception as e:
            flash(f"An unexpected error occurred while processing upload: {str(e)}", 'error')

    # GET request: load default preview if dataset exists
    default_file = find_default_raw_file()
    if default_file and os.path.exists(default_file):
        try:
            raw_df, _ = extract_data(default_file, nrows=100)
            preview = get_dataset_preview(raw_df, n_rows=10)
        except Exception:
            preview = None

    return render_template('upload.html', preview=preview)


@data_bp.route('/setup-db')
@data_bp.route('/init-db')
def setup_db():
    """Explicit web endpoint to run schema.sql and seed sample data."""
    import traceback
    from database.init_db import run_schema_file, auto_seed_if_empty
    from database.db_connection import get_pymysql_connection

    logs = []
    success = False
    table_counts = {}

    try:
        logs.append("[Step 1] Applying Star Schema database/schema.sql...")
        run_schema_file()
        logs.append("[Step 1] Star Schema tables created or verified!")

        logs.append("[Step 2] Checking Fact_Sales and auto-seeding if empty...")
        auto_seed_if_empty()
        logs.append("[Step 2] Auto-seeding check completed!")

        # Query all table counts
        conn = get_pymysql_connection(include_db=True)
        try:
            with conn.cursor() as cursor:
                for tbl in ['Dim_Product', 'Dim_Customer', 'Dim_Date', 'Dim_Country', 'Fact_Sales']:
                    try:
                        cursor.execute(f"SELECT COUNT(*) AS cnt FROM {tbl};")
                        table_counts[tbl] = cursor.fetchone()['cnt']
                    except Exception as err:
                        table_counts[tbl] = f"Error: {err}"
        finally:
            conn.close()

        logs.append(f"[Step 3] Table verification complete: {table_counts}")
        success = True
        return render_template('setup_db.html', success=success, logs=logs, table_counts=table_counts, error=None)

    except Exception as e:
        err_tb = traceback.format_exc()
        logs.append(f"[Error] Initialization encountered: {str(e)}")
        return render_template('setup_db.html', success=False, logs=logs, table_counts=table_counts, error=str(e), traceback=err_tb), 500
