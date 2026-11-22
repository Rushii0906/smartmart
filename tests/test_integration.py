"""Integration and End-to-End Test Suite for SmartMart Analytics.

Validates:
- Complete user navigation journeys across all application screens
- Form submissions and algorithm executions via HTTP POST
- Edge-case handling (empty results, extreme thresholds, non-existent slices)
- Custom error pages (404 Not Found)
- Data export generation and content types
"""

import pytest
from app import create_app


@pytest.fixture
def client():
    """Provides a configured test client."""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_end_to_end_journey(client):
    """Smoke test simulating an end-to-end user journey across all application screens."""
    # 1. Executive Dashboard
    r_dash = client.get('/')
    assert r_dash.status_code == 200
    assert b'Executive Retail Dashboard' in r_dash.data
    assert b'Total Revenue' in r_dash.data

    # 2. Dataset Management
    r_upload = client.get('/upload')
    assert r_upload.status_code == 200
    assert b'Dataset Preview' in r_upload.data or b'Upload Retail Dataset' in r_upload.data

    # 3. ETL Pipeline Status
    r_etl = client.get('/etl')
    assert r_etl.status_code == 200
    assert b'Run ETL Pipeline' in r_etl.data
    assert b'Fact_Sales' in r_etl.data

    # 4. OLAP Operations (Roll-Up, Drill-Down, Slice, Dice)
    r_olap = client.get('/olap')
    assert r_olap.status_code == 200
    assert b'Multidimensional OLAP Cube Operations' in r_olap.data

    # 5. Apriori Market Basket Mining
    r_apriori = client.get('/mining/apriori')
    assert r_apriori.status_code == 200
    assert b'Mined Retail Association Rules' in r_apriori.data

    # 6. Customer Clustering
    r_clustering = client.get('/mining/clustering')
    assert r_clustering.status_code == 200
    assert b'Derived Customer Segments' in r_clustering.data

    # 7. Decision Tree Classification
    r_dtree = client.get('/mining/decision-tree')
    assert r_dtree.status_code == 200
    assert b'Decision Tree Transaction Classification' in r_dtree.data

    # 8. Analytical Reports & Insights
    r_rep = client.get('/reports')
    assert r_rep.status_code == 200
    assert b'Key Analytical Discoveries' in r_rep.data


def test_apriori_form_submission(client):
    """Test Apriori parameter submission with realistic and extreme parameters."""
    # Standard POST
    r_post = client.post('/mining/apriori', data={
        'min_support': '0.03',
        'min_confidence': '0.40',
        'min_lift': '1.5',
        'country': ''
    })
    assert r_post.status_code == 200
    assert b'Mined Retail Association Rules' in r_post.data

    # Extreme edge case: Support so high that no rules match
    r_empty = client.post('/mining/apriori', data={
        'min_support': '0.99',
        'min_confidence': '0.99',
        'min_lift': '5.0',
        'country': ''
    })
    assert r_empty.status_code == 200
    assert b'No frequent itemsets found' in r_empty.data or b'No association rules' in r_empty.data


def test_clustering_form_submission(client):
    """Test K-Means clustering with different k values."""
    r_k4 = client.post('/mining/clustering', data={
        'n_clusters': '4',
        'country': ''
    })
    assert r_k4.status_code == 200
    assert b'Derived Customer Segments' in r_k4.data
    assert b'Silhouette Score' in r_k4.data


def test_decision_tree_form_submission(client):
    """Test Decision Tree training with custom max_depth and test_size."""
    r_dt = client.post('/mining/decision-tree', data={
        'max_depth': '3',
        'test_size': '0.30',
        'country': ''
    })
    assert r_dt.status_code == 200
    assert b'Confusion Matrix' in r_dt.data
    assert b'Model Accuracy' in r_dt.data


def test_olap_edge_cases(client):
    """Test OLAP slicing with a non-existent country or filter criteria."""
    # Non-existent country slice
    r_slice_empty = client.get('/olap?op=slice&slice_dim=country&slice_val_country=Atlantis')
    assert r_slice_empty.status_code == 200
    assert b'No data records match the specified OLAP parameters' in r_slice_empty.data

    # Empty Dice criteria (high min revenue threshold)
    r_dice_high = client.get('/olap?op=dice&dice_min_rev=99999999')
    assert r_dice_high.status_code == 200
    assert b'No data records match the specified OLAP parameters' in r_dice_high.data


def test_custom_404_error_page(client):
    """Verify that undefined URLs return a styled 404 page."""
    response = client.get('/some-nonexistent-endpoint-404')
    assert response.status_code == 404
    assert b'404' in response.data
    assert b'could not be found' in response.data


def test_csv_data_exports_integrity(client):
    """Verify that all CSV export endpoints return valid CSV headers and rows."""
    endpoints = [
        ('/reports/export/monthly', b'Year,Month,Month_Name,Total_Invoices'),
        ('/reports/export/country', b'Country,Total_Invoices'),
        ('/reports/export/products', b'Stock_Code,Description')
    ]
    for url, expected_header in endpoints:
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp.content_type == 'text/csv; charset=utf-8'
        assert expected_header in resp.data
