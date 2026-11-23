"""Data Mining and Reporting Blueprint for SmartMart Analytics.

Handles:
- Apriori Market Basket Analysis
- K-Means Customer Segmentation
- Decision Tree Transaction Classification
- Executive Reports and CSV Data Exports
"""

from flask import Blueprint, render_template, request, Response
from mining.apriori import run_apriori, get_metric_explanations
from mining.clustering import run_kmeans_clustering, get_rfm_explanations
from mining.decision_tree import train_decision_tree, get_classification_explanations
from analytics.olap import get_filter_options
from analytics.reports import (
    get_executive_insights,
    export_monthly_sales_csv,
    export_country_performance_csv,
    export_product_performance_csv
)

mining_bp = Blueprint('mining', __name__)


# -------------------------------------------------------------
# 1. Apriori Association Rule Mining
# -------------------------------------------------------------
@mining_bp.route('/mining/apriori', methods=['GET', 'POST'])
def apriori_view():
    """Handles Apriori parameter configuration and results display."""
    options = get_filter_options()
    countries = options.get('countries', [])

    min_support = float(request.form.get('min_support', 0.6)) if request.method == 'POST' else 0.6
    min_confidence = float(request.form.get('min_confidence', 0.30)) if request.method == 'POST' else 0.30
    min_lift = float(request.form.get('min_lift', 1.2)) if request.method == 'POST' else 1.2
    selected_country = request.form.get('country') if request.method == 'POST' else ''

    results = run_apriori(
        min_support=min_support,
        min_confidence=min_confidence,
        min_lift=min_lift,
        country=selected_country if selected_country else None,
        top_n_products=120
    )

    explanations = get_metric_explanations()

    return render_template(
        'apriori.html',
        results=results,
        explanations=explanations,
        countries=countries,
        min_support=min_support,
        min_confidence=min_confidence,
        min_lift=min_lift,
        selected_country=selected_country
    )


# -------------------------------------------------------------
# 2. K-Means Customer Segmentation
# -------------------------------------------------------------
@mining_bp.route('/mining/clustering', methods=['GET', 'POST'])
def clustering_view():
    """Handles K-Means customer RFM segmentation."""
    options = get_filter_options()
    countries = options.get('countries', [])

    k_clusters = int(request.form.get('n_clusters', 3)) if request.method == 'POST' else 3
    selected_country = request.form.get('country') if request.method == 'POST' else ''

    results = run_kmeans_clustering(
        n_clusters=k_clusters,
        country=selected_country if selected_country else None
    )

    explanations = get_rfm_explanations()

    return render_template(
        'clustering.html',
        results=results,
        explanations=explanations,
        countries=countries,
        k_clusters=k_clusters,
        selected_country=selected_country
    )


# -------------------------------------------------------------
# 3. Decision Tree Transaction Classification
# -------------------------------------------------------------
@mining_bp.route('/mining/decision-tree', methods=['GET', 'POST'])
def decision_tree_view():
    """Handles Decision Tree classification training and evaluation."""
    options = get_filter_options()
    countries = options.get('countries', [])

    max_depth = int(request.form.get('max_depth', 4)) if request.method == 'POST' else 4
    test_size = float(request.form.get('test_size', 0.25)) if request.method == 'POST' else 0.25
    selected_country = request.form.get('country') if request.method == 'POST' else ''

    results = train_decision_tree(
        max_depth=max_depth,
        test_size=test_size,
        country=selected_country if selected_country else None
    )

    explanations = get_classification_explanations()

    return render_template(
        'decision_tree.html',
        results=results,
        explanations=explanations,
        countries=countries,
        max_depth=max_depth,
        test_size=str(test_size),
        selected_country=selected_country
    )


# -------------------------------------------------------------
# 4. Reports & CSV Data Exports
# -------------------------------------------------------------
@mining_bp.route('/reports', methods=['GET'])
def reports_view():
    """Renders business intelligence analytical summaries and export links."""
    insights = get_executive_insights()
    return render_template('reports.html', insights=insights)


@mining_bp.route('/reports/export/monthly', methods=['GET'])
def export_monthly():
    """Downloads monthly sales roll-up CSV."""
    csv_data = export_monthly_sales_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=smartmart_monthly_sales_rollup.csv"}
    )


@mining_bp.route('/reports/export/country', methods=['GET'])
def export_country():
    """Downloads country performance report CSV."""
    csv_data = export_country_performance_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=smartmart_country_performance.csv"}
    )


@mining_bp.route('/reports/export/products', methods=['GET'])
def export_products():
    """Downloads product performance report CSV."""
    csv_data = export_product_performance_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=smartmart_product_performance.csv"}
    )
