"""Test suite for Data Mining Algorithms (Stage 5: Apriori, Stage 6: K-Means, Stage 7: Decision Tree)."""

import pytest
from mining.apriori import (
    run_apriori,
    get_metric_explanations,
    get_transaction_baskets
)
from mining.clustering import (
    extract_rfm_features,
    run_kmeans_clustering,
    get_rfm_explanations
)
from mining.decision_tree import (
    train_decision_tree,
    extract_invoice_dataset,
    get_classification_explanations,
    EDUCATIONAL_DISCLAIMER
)


def test_get_metric_explanations():
    """Verify that syllabus metric explanations for Support, Confidence, and Lift are present."""
    explanations = get_metric_explanations()
    assert 'support' in explanations
    assert 'confidence' in explanations
    assert 'lift' in explanations

    for metric in ['support', 'confidence', 'lift']:
        assert 'name' in explanations[metric]
        assert 'formula' in explanations[metric]
        assert 'description' in explanations[metric]
        assert len(explanations[metric]['description']) > 10


def test_get_transaction_baskets():
    """Verify that transaction baskets are extracted from Fact_Sales and Dim_Product."""
    baskets, total_invoices = get_transaction_baskets(top_n_products=200)
    assert isinstance(baskets, list)
    assert total_invoices > 0
    assert len(baskets) > 0

    # Ensure all returned baskets are multi-item
    for b in baskets:
        assert isinstance(b, list)
        assert len(b) >= 2


def test_run_apriori_success():
    """Verify end-to-end Apriori execution produces valid frequent itemsets and association rules."""
    result = run_apriori(min_support=0.02, min_confidence=0.25, min_lift=1.0, top_n_products=100, max_len=3)
    assert result['status'] == 'SUCCESS'
    assert result['summary']['multi_item_baskets'] > 0
    assert result['summary']['frequent_itemsets_count'] > 0
    assert result['summary']['rules_generated'] > 0
    assert len(result['rules']) > 0

    first_rule = result['rules'][0]
    assert 'antecedents' in first_rule
    assert 'consequents' in first_rule
    assert 'support' in first_rule
    assert 'confidence' in first_rule
    assert 'lift' in first_rule
    assert first_rule['support'] > 0
    assert first_rule['confidence'] >= 0.25
    assert first_rule['lift'] >= 1.0


def test_run_apriori_high_support_edge_case():
    """Verify graceful handling when minimum support threshold is too high."""
    result = run_apriori(min_support=0.99, min_confidence=0.99)
    assert result['status'] in ['NO_RULES', 'NO_DATA']
    assert 'message' in result
    assert result['rules'] == []


def test_apriori_rule_metrics_validity():
    """Verify that generated rules conform to association rule mathematical bounds."""
    result = run_apriori(min_support=0.02, min_confidence=0.25, min_lift=1.0, top_n_products=100, max_len=3)
    if result['status'] == 'SUCCESS':
        for rule in result['rules']:
            # Support and Confidence must be in (0, 1]
            assert 0 < rule['support'] <= 1.0
            assert 0 < rule['confidence'] <= 1.0
            # Lift must be positive
            assert rule['lift'] > 0


# -------------------------------------------------------------
# Stage 6: K-Means Customer Segmentation Tests
# -------------------------------------------------------------

def test_get_rfm_explanations():
    """Verify educational explanations for Recency, Frequency, Monetary, and StandardScaler."""
    rfm_exp = get_rfm_explanations()
    assert 'recency' in rfm_exp
    assert 'frequency' in rfm_exp
    assert 'monetary' in rfm_exp
    assert 'scaling' in rfm_exp


def test_extract_rfm_features():
    """Verify RFM feature calculation from Fact_Sales and Dim_Customer."""
    df = extract_rfm_features()
    assert not df.empty
    assert 'Customer_ID' in df.columns
    assert 'CustomerCode' in df.columns
    assert 'recency' in df.columns
    assert 'frequency' in df.columns
    assert 'monetary' in df.columns

    # Verify UNKNOWN customer is excluded
    assert 1 not in df['Customer_ID'].values
    assert 'UNKNOWN' not in df['CustomerCode'].values

    # Value checks
    assert (df['recency'] > 0).all()
    assert (df['frequency'] > 0).all()
    assert (df['monetary'] > 0).all()


def test_run_kmeans_clustering_default_k3():
    """Verify K-Means clustering with default k=3."""
    res = run_kmeans_clustering(n_clusters=3)
    assert res['status'] == 'SUCCESS'
    assert res['metrics']['total_customers_analyzed'] > 0
    assert res['metrics']['inertia_wcss'] > 0
    assert -1.0 <= res['metrics']['silhouette_score'] <= 1.0
    assert len(res['cluster_summary']) == 3

    # Check that labels are assigned based on cluster ranking
    labels = [c['label'] for c in res['cluster_summary']]
    assert any('Champions' in l for l in labels)
    assert any('Loyal' in l for l in labels)
    assert any('At-Risk' in l for l in labels)


def test_run_kmeans_clustering_k4():
    """Verify configurable clusters (k=4)."""
    res = run_kmeans_clustering(n_clusters=4)
    assert res['status'] == 'SUCCESS'
    assert len(res['cluster_summary']) == 4


def test_kmeans_charts_data():
    """Verify Chart.js datasets for distribution, comparison, and scatter plots."""
    res = run_kmeans_clustering(n_clusters=3)
    charts = res['charts']
    assert 'distribution' in charts
    assert 'comparison' in charts
    assert 'scatter_points' in charts

    # Distribution checks
    assert len(charts['distribution']['labels']) == 3
    assert len(charts['distribution']['counts']) == 3

    # Comparison checks
    assert len(charts['comparison']['avg_recency']) == 3
    assert len(charts['comparison']['avg_frequency']) == 3
    assert len(charts['comparison']['avg_monetary']) == 3

    # Scatter points check
    assert len(charts['scatter_points']) > 0
    first_pt = charts['scatter_points'][0]
    assert 'x' in first_pt
    assert 'y' in first_pt
    assert 'cluster' in first_pt
    assert 'label' in first_pt


# -------------------------------------------------------------
# Stage 7: Decision Tree Transaction Classification Tests
# -------------------------------------------------------------

def test_get_classification_explanations():
    """Verify educational explanations for accuracy, precision, recall, f1, and feature importance."""
    explanations = get_classification_explanations()
    assert 'accuracy' in explanations
    assert 'precision' in explanations
    assert 'recall' in explanations
    assert 'f1_score' in explanations
    assert 'feature_importance' in explanations


def test_extract_invoice_dataset():
    """Verify invoice-level feature dataset extraction from Fact_Sales."""
    df = extract_invoice_dataset()
    assert not df.empty
    assert 'InvoiceNo' in df.columns
    assert 'line_count' in df.columns
    assert 'total_quantity' in df.columns
    assert 'avg_unit_price' in df.columns
    assert 'distinct_products' in df.columns
    assert 'country' in df.columns
    assert 'invoice_total' in df.columns

    assert (df['line_count'] > 0).all()
    assert (df['total_quantity'] > 0).all()
    assert (df['invoice_total'] > 0).all()


def test_train_decision_tree_metrics():
    """Verify Decision Tree training produces valid evaluation metrics and confusion matrix."""
    res = train_decision_tree(max_depth=4, test_size=0.25)
    assert res['status'] == 'SUCCESS'

    metrics = res['metrics']
    assert 0.70 <= metrics['accuracy'] <= 1.0
    assert 0.70 <= metrics['precision'] <= 1.0
    assert 0.70 <= metrics['recall'] <= 1.0
    assert 0.70 <= metrics['f1_score'] <= 1.0

    cm = res['confusion_matrix']
    assert cm['tn'] >= 0
    assert cm['fp'] >= 0
    assert cm['fn'] >= 0
    assert cm['tp'] >= 0
    assert cm['tp'] + cm['tn'] + cm['fp'] + cm['fn'] == res['dataset_summary']['testing_samples']

    # Verify feature importance
    assert len(res['feature_importance']) > 0
    raw_feats = [f['raw_feature'] for f in res['feature_importance']]
    assert 'total_quantity' in raw_feats
    # Ensure invoice_total was strictly excluded from features
    assert 'invoice_total' not in raw_feats

    # Verify educational disclaimer
    assert 'Educational Disclaimer' in res['disclaimer']


def test_decision_tree_rules_and_tree_structure():
    """Verify decision tree text rules and JSON hierarchical tree representation."""
    res = train_decision_tree(max_depth=3)
    assert res['status'] == 'SUCCESS'
    assert len(res['tree_rules_text']) > 20
    assert 'tree_structure' in res
    assert res['tree_structure']['type'] in ['node', 'leaf']


