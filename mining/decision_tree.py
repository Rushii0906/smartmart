"""Data Mining Module C: Decision Tree Transaction Classification.

Builds an invoice-level classification model:
Features:
- line_count (number of product lines)
- total_quantity (total units sold in invoice)
- avg_unit_price (average unit price of purchased products)
- distinct_products (count of unique products in invoice)
- country (one-hot encoded categorical country)

Target:
- Binary: 1 = "High Value", 0 = "Low Value"
- Defined using the MEDIAN invoice total value in the dataset.
- NOTE: Actual invoice total amount is strictly EXCLUDED from features
  to prevent target leakage.

Provides:
- DecisionTreeClassifier with configurable max_depth
- Evaluation metrics: Accuracy, Precision, Recall, F1-Score, Confusion Matrix
- Feature Importance ranking
- Text and structured JSON tree visualization representations
- Clear academic disclaimer for DM&DW syllabus
"""

import time
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from database.db_connection import get_pymysql_connection

EDUCATIONAL_DISCLAIMER = (
    "Educational Disclaimer: This classification model is an educational laboratory demonstration "
    "designed to illustrate decision tree splitting criteria (Gini impurity / Information Gain), "
    "feature importances, and evaluation metrics in the Data Mining & Data Warehousing (DM&DW) syllabus. "
    "It is not an enterprise validated predictive model for future sales forecasts."
)


def get_classification_explanations():
    """Returns educational explanations of classification metrics for DM&DW examination."""
    return {
        'target_definition': {
            'name': 'Median Split Target',
            'description': 'The target variable (High Value vs Low Value) is defined by splitting transactions at the '
                           'median invoice value. This produces balanced classes without artificial bias.'
        },
        'accuracy': {
            'name': 'Accuracy',
            'formula': 'Accuracy = (TP + TN) / (TP + TN + FP + FN)',
            'description': 'The overall proportion of correct invoice value classifications made by the tree.'
        },
        'precision': {
            'name': 'Precision (Positive Predictive Value)',
            'formula': 'Precision = TP / (TP + FP)',
            'description': 'The percentage of invoices predicted as "High Value" that were truly high value. '
                           'Measures false positive rate.'
        },
        'recall': {
            'name': 'Recall (Sensitivity)',
            'formula': 'Recall = TP / (TP + FN)',
            'description': 'The percentage of all actual high-value invoices correctly captured by the model. '
                           'Measures false negative rate.'
        },
        'f1_score': {
            'name': 'F1-Score',
            'formula': 'F1 = 2 * (Precision * Recall) / (Precision + Recall)',
            'description': 'Harmonic mean of Precision and Recall, providing a single metric that balances both.'
        },
        'feature_importance': {
            'name': 'Gini Importance (Mean Decrease in Impurity)',
            'formula': 'Normalized total reduction of Gini impurity brought by that feature across all splits.',
            'description': 'Higher importance indicates the feature provides the greatest statistical power in separating '
                           'high-value invoices from low-value ones.'
        }
    }


def extract_invoice_dataset(country=None):
    """Extracts invoice-level aggregate dataset from Fact_Sales and Dim_Country.

    Args:
        country (str, optional): Geographic filter.

    Returns:
        pd.DataFrame: Invoice-level feature DataFrame.
    """
    where_sql = "WHERE 1=1"
    params = []

    if country:
        where_sql += " AND co.CountryName = %s"
        params.append(country)

    query = f"""
        SELECT 
            f.InvoiceNo,
            COUNT(*) AS line_count,
            SUM(f.Quantity) AS total_quantity,
            ROUND(AVG(f.UnitPrice), 2) AS avg_unit_price,
            COUNT(DISTINCT f.Product_ID) AS distinct_products,
            co.CountryName AS country,
            ROUND(SUM(f.TotalAmount), 2) AS invoice_total
        FROM Fact_Sales f
        JOIN Dim_Country co ON f.Country_ID = co.Country_ID
        {where_sql}
        GROUP BY f.InvoiceNo, co.CountryName;
    """

    try:
        conn = get_pymysql_connection(include_db=True)
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
        finally:
            conn.close()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df['line_count'] = df['line_count'].astype(int)
        df['total_quantity'] = df['total_quantity'].astype(int)
        df['avg_unit_price'] = df['avg_unit_price'].astype(float)
        df['distinct_products'] = df['distinct_products'].astype(int)
        df['invoice_total'] = df['invoice_total'].astype(float)

        return df
    except Exception as e:
        print(f"[Decision Tree Warning] Unable to extract invoices (tables may be uninitialized): {e}")
        return pd.DataFrame()


def build_tree_structure(tree, feature_names, node_id=0, depth=0, max_depth=3):
    """Recursively converts a scikit-learn DecisionTreeClassifier tree object

    into a hierarchical JSON dictionary for visualization.
    """
    if depth > max_depth or tree.children_left[node_id] == tree.children_right[node_id]:
        # Leaf node
        values = tree.value[node_id][0].tolist()
        predicted_class = "High Value" if values[1] > values[0] else "Low Value"
        return {
            'type': 'leaf',
            'samples': int(tree.n_node_samples[node_id]),
            'values': [int(v) for v in values],
            'class': predicted_class
        }

    # Decision node
    feat_idx = tree.feature[node_id]
    feat_name = feature_names[feat_idx] if feat_idx < len(feature_names) else f"Feature {feat_idx}"
    thresh = round(float(tree.threshold[node_id]), 2)
    values = tree.value[node_id][0].tolist()

    return {
        'type': 'node',
        'feature': feat_name,
        'threshold': thresh,
        'samples': int(tree.n_node_samples[node_id]),
        'values': [int(v) for v in values],
        'left': build_tree_structure(tree, feature_names, tree.children_left[node_id], depth + 1, max_depth),
        'right': build_tree_structure(tree, feature_names, tree.children_right[node_id], depth + 1, max_depth)
    }


def train_decision_tree(max_depth=4, test_size=0.25, min_samples_split=5, country=None, random_state=42):
    """Trains and evaluates a Decision Tree classifier for invoice value classification.

    Args:
        max_depth (int): Maximum depth of the decision tree (default 4, range 2-7).
        test_size (float): Fraction of data for testing (default 0.25).
        min_samples_split (int): Minimum samples required to split a node (default 5).
        country (str, optional): Geographic filter.
        random_state (int): Seed for reproducibility.

    Returns:
        dict: Training results, evaluation metrics, confusion matrix, feature importance, and tree rules.
    """
    start_time = time.time()
    max_depth = max(2, min(int(max_depth), 7))
    test_size = float(test_size)

    # Step 1: Feature Extraction
    df = extract_invoice_dataset(country=country)

    if df.empty or len(df) < 25:
        return {
            'status': 'INSUFFICIENT_DATA',
            'message': f'Insufficient invoice records ({len(df)}) in warehouse for training. At least 25 invoices are required.',
            'metrics': {},
            'disclaimer': EDUCATIONAL_DISCLAIMER
        }

    # Step 2: Target Variable Formulation (Median Split)
    median_invoice_val = float(df['invoice_total'].median())
    df['target'] = (df['invoice_total'] >= median_invoice_val).astype(int)

    # Class balance check
    class_counts = df['target'].value_counts().to_dict()
    if len(class_counts) < 2:
        return {
            'status': 'SINGLE_CLASS',
            'message': 'The extracted dataset contains only one target class. Cannot train classifier.',
            'metrics': {},
            'disclaimer': EDUCATIONAL_DISCLAIMER
        }

    # Step 3: Feature Matrix Assembly
    # IMPORTANT: invoice_total is strictly excluded
    numeric_features = ['line_count', 'total_quantity', 'avg_unit_price', 'distinct_products']
    X_num = df[numeric_features].copy()

    # One-hot encode Country categorically
    X_country = pd.get_dummies(df['country'], prefix='country', drop_first=True)
    X = pd.concat([X_num, X_country], axis=1)
    y = df['target']
    feature_names = list(X.columns)

    # Step 4: Train / Test Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    # Step 5: Decision Tree Classifier Training
    clf = DecisionTreeClassifier(
        max_depth=max_depth,
        min_samples_split=int(min_samples_split),
        random_state=random_state
    )
    clf.fit(X_train, y_train)

    # Step 6: Model Evaluation on Hold-Out Test Set
    y_pred = clf.predict(X_test)

    acc = round(float(accuracy_score(y_test, y_pred)), 4)
    prec = round(float(precision_score(y_test, y_pred, zero_division=0)), 4)
    rec = round(float(recall_score(y_test, y_pred, zero_division=0)), 4)
    f1 = round(float(f1_score(y_test, y_pred, zero_division=0)), 4)

    # Confusion Matrix: [[TN, FP], [FN, TP]]
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = [int(v) for v in cm.ravel()]

    # Step 7: Feature Importance Ranking
    importances = clf.feature_importances_
    feat_imp = []
    for name, imp in zip(feature_names, importances):
        # Human-friendly feature names
        display_name = name.replace('country_', 'Country: ').replace('_', ' ').title()
        feat_imp.append({
            'raw_feature': name,
            'feature': display_name,
            'importance': round(float(imp), 4),
            'importance_pct': round(float(imp) * 100, 2)
        })
    feat_imp = sorted(feat_imp, key=lambda x: x['importance'], reverse=True)

    # Step 8: Tree Rules and Structure
    tree_rules_text = export_text(clf, feature_names=feature_names)
    tree_structure = build_tree_structure(clf.tree_, feature_names, max_depth=max_depth)

    duration = round(time.time() - start_time, 2)

    return {
        'status': 'SUCCESS',
        'parameters': {
            'max_depth': max_depth,
            'min_samples_split': min_samples_split,
            'test_size': test_size,
            'random_state': random_state,
            'country': country or 'All Countries'
        },
        'dataset_summary': {
            'total_invoices': len(df),
            'training_samples': len(X_train),
            'testing_samples': len(X_test),
            'median_threshold': round(median_invoice_val, 2),
            'class_distribution': {
                'low_value_count': int(class_counts.get(0, 0)),
                'high_value_count': int(class_counts.get(1, 0))
            }
        },
        'metrics': {
            'accuracy': acc,
            'accuracy_pct': round(acc * 100, 2),
            'precision': prec,
            'precision_pct': round(prec * 100, 2),
            'recall': rec,
            'recall_pct': round(rec * 100, 2),
            'f1_score': f1,
            'f1_score_pct': round(f1 * 100, 2),
            'execution_time_seconds': duration
        },
        'confusion_matrix': {
            'matrix': [[tn, fp], [fn, tp]],
            'tn': tn,
            'fp': fp,
            'fn': fn,
            'tp': tp
        },
        'feature_importance': feat_imp,
        'tree_rules_text': tree_rules_text,
        'tree_structure': tree_structure,
        'classification_explanations': get_classification_explanations(),
        'disclaimer': EDUCATIONAL_DISCLAIMER
    }


if __name__ == '__main__':
    print("=" * 65)
    print(" SmartMart Analytics - Decision Tree Classification Demo")
    print("=" * 65)
    res = train_decision_tree(max_depth=4)
    print(f"Status:            {res['status']}")
    print(f"Total Invoices:    {res['dataset_summary']['total_invoices']}")
    print(f"Median Threshold:  ${res['dataset_summary']['median_threshold']:,.2f}")
    print(f"Train/Test Samples: {res['dataset_summary']['training_samples']} / {res['dataset_summary']['testing_samples']}")
    print("-" * 65)
    print("Evaluation Metrics:")
    print(f"  Accuracy:   {res['metrics']['accuracy_pct']}%")
    print(f"  Precision:  {res['metrics']['precision_pct']}%")
    print(f"  Recall:     {res['metrics']['recall_pct']}%")
    print(f"  F1-Score:   {res['metrics']['f1_score_pct']}%")
    print(f"Confusion Matrix: [[TN={res['confusion_matrix']['tn']}, FP={res['confusion_matrix']['fp']}], [FN={res['confusion_matrix']['fn']}, TP={res['confusion_matrix']['tp']}]]")
    print("-" * 65)
    print("Top Feature Importances:")
    for f in res['feature_importance'][:4]:
        print(f"  - {f['feature']:25}: {f['importance_pct']}%")
    print("=" * 65)
