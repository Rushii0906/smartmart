"""Dashboard Blueprint for SmartMart Analytics.

Renders executive sales KPIs and dimensional charts.
All metric values are computed dynamically from the MySQL Star Schema warehouse.
"""

from flask import Blueprint, render_template
from analytics.olap import (
    get_warehouse_kpis,
    get_monthly_revenue_chart,
    get_country_revenue_chart,
    get_top_products_chart
)
from mining.clustering import run_kmeans_clustering

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
def index():
    """Renders main dashboard with live warehouse KPIs and dimensional charts."""
    # 1. Fetch top-level KPIs
    kpis = get_warehouse_kpis()

    # 2. Fetch Chart.js datasets
    monthly_chart = get_monthly_revenue_chart()
    country_chart = get_country_revenue_chart(limit=8)
    product_chart = get_top_products_chart(limit=10)

    # 3. Fetch Customer Segmentation chart data (k=3)
    try:
        clustering_res = run_kmeans_clustering(n_clusters=3)
        segment_chart = clustering_res.get('charts', {}).get('distribution', {'labels': [], 'counts': []})
    except Exception:
        segment_chart = {'labels': ['No Data'], 'counts': [0]}

    return render_template(
        'dashboard.html',
        kpis=kpis,
        monthly_chart=monthly_chart,
        country_chart=country_chart,
        product_chart=product_chart,
        segment_chart=segment_chart
    )
