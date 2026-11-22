"""Test suite for Stage 8: Flask Blueprints, Web Endpoints, and Template Rendering."""

import pytest
from app import create_app


@pytest.fixture
def client():
    """Provides a Flask test client."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_dashboard_route(client):
    """Verify that the dashboard view renders with status code 200."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Executive Retail Dashboard' in response.data
    assert b'Total Revenue' in response.data


def test_upload_route(client):
    """Verify that dataset upload page renders with status code 200."""
    response = client.get('/upload')
    assert response.status_code == 200
    assert b'Upload Retail Dataset' in response.data
    assert b'InvoiceNo' in response.data


def test_etl_route(client):
    """Verify that the ETL management page renders with status code 200."""
    response = client.get('/etl')
    assert response.status_code == 200
    assert b'Run ETL Pipeline' in response.data
    assert b'Fact_Sales' in response.data


def test_etl_run_route(client):
    """Verify that running the ETL pipeline via web POST renders cleaning report without error."""
    response = client.post('/etl/run', data={
        'sample_size': '50',
        'reset_dw': 'false'
    })
    assert response.status_code == 200
    assert b'ETL Cleaning Summary' in response.data
    assert b'Duplicate Row Removal' in response.data


def test_olap_routes(client):
    """Verify all 4 OLAP operations on the /olap endpoint."""
    # Default Roll-Up
    r_rollup = client.get('/olap?op=rollup&rollup_level=monthly')
    assert r_rollup.status_code == 200
    assert b'OLAP Aggregation Visualization' in r_rollup.data

    # Drill-down
    r_drill = client.get('/olap?op=drilldown&drill_year=2010')
    assert r_drill.status_code == 200

    # Slice
    r_slice = client.get('/olap?op=slice&slice_dim=country&slice_val_country=United+Kingdom')
    assert r_slice.status_code == 200

    # Dice
    r_dice = client.get('/olap?op=dice&dice_min_rev=10')
    assert r_dice.status_code == 200


def test_apriori_route(client):
    """Verify that the Apriori market basket analysis page renders."""
    response = client.get('/mining/apriori')
    assert response.status_code == 200
    assert b'Apriori Association Rule Mining' in response.data
    assert b'Min Support' in response.data


def test_clustering_route(client):
    """Verify that the customer segmentation page renders."""
    response = client.get('/mining/clustering')
    assert response.status_code == 200
    assert b'Customer Segmentation' in response.data
    assert b'Number of Clusters (k)' in response.data


def test_decision_tree_route(client):
    """Verify that the decision tree classifier page renders."""
    response = client.get('/mining/decision-tree')
    assert response.status_code == 200
    assert b'Decision Tree Transaction Classification' in response.data
    assert b'Educational Disclaimer' in response.data


def test_reports_and_export_routes(client):
    """Verify analytical reports page and CSV file export downloads."""
    # Reports Page
    r_rep = client.get('/reports')
    assert r_rep.status_code == 200
    assert b'Key Analytical Discoveries' in r_rep.data

    # Monthly CSV Export
    r_m = client.get('/reports/export/monthly')
    assert r_m.status_code == 200
    assert r_m.content_type == 'text/csv; charset=utf-8'
    assert b'Year,Month' in r_m.data

    # Country CSV Export
    r_c = client.get('/reports/export/country')
    assert r_c.status_code == 200
    assert r_c.content_type == 'text/csv; charset=utf-8'
    assert b'Country,Total_Invoices' in r_c.data

    # Products CSV Export
    r_p = client.get('/reports/export/products')
    assert r_p.status_code == 200
    assert r_p.content_type == 'text/csv; charset=utf-8'
    assert b'Stock_Code,Description' in r_p.data
