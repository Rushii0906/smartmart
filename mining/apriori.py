"""Data Mining Module A: Apriori Association Rule Mining (Market Basket Analysis).

Implements Market Basket Analysis using:
- mlxtend.preprocessing.TransactionEncoder
- mlxtend.frequent_patterns.apriori
- mlxtend.frequent_patterns.association_rules

Features:
- Configurable minimum support, confidence, and lift thresholds
- Top-N frequent items filtering to optimize matrix density and performance
- Full metric derivations: Support, Confidence, Lift, Leverage, Conviction
- Educational metric explanations for viva and mini-project evaluation
"""

import time
import pandas as pd
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, association_rules
from database.db_connection import get_pymysql_connection


def get_metric_explanations():
    """Returns educational explanations of Market Basket Analysis metrics

    aligned with the Data Mining (DM&DW) syllabus.
    """
    return {
        'support': {
            'name': 'Support',
            'formula': 'Support(A -> B) = P(A ∩ B) = Count(A ∪ B) / Total_Transactions',
            'description': 'The proportion of all shopping baskets that contain both itemset A and itemset B. '
                           'Measures how frequently items appear together.'
        },
        'confidence': {
            'name': 'Confidence',
            'formula': 'Confidence(A -> B) = P(B | A) = Support(A ∪ B) / Support(A)',
            'description': 'The conditional probability that a customer purchases item B given that they purchased item A. '
                           'Measures the reliability of the inference rule.'
        },
        'lift': {
            'name': 'Lift',
            'formula': 'Lift(A -> B) = Confidence(A -> B) / Support(B)',
            'description': 'The ratio of the observed joint occurrence to the expected occurrence if A and B were independent. '
                           'Lift > 1 indicates a positive association; Lift = 1 indicates independence; Lift < 1 indicates negative association.'
        }
    }


def get_transaction_baskets(country=None, top_n_products=300):
    """Retrieves transactions grouped by invoice into item baskets from the warehouse.

    Args:
        country (str, optional): Country filter.
        top_n_products (int): Restricts item universe to top N most frequent items to optimize memory.

    Returns:
        tuple: (baskets: list of lists, total_invoices: int)
    """
    where_sql = "WHERE p.Description IS NOT NULL AND p.Description != '' AND p.Description != 'UNKNOWN DESCRIPTION'"
    params = []

    if country:
        where_sql += " AND co.CountryName = %s"
        params.append(country)

    try:
        conn = get_pymysql_connection(include_db=True)
        try:
            with conn.cursor() as cursor:
                # Step 1: Identify top N most popular products to ensure dense itemset matrix
                top_prod_sql = f"""
                    SELECT p.Product_ID
                    FROM Fact_Sales f
                    JOIN Dim_Product p ON f.Product_ID = p.Product_ID
                    JOIN Dim_Country co ON f.Country_ID = co.Country_ID
                    {where_sql}
                    GROUP BY p.Product_ID
                    ORDER BY COUNT(*) DESC
                    LIMIT %s;
                """
                cursor.execute(top_prod_sql, params + [int(top_n_products)])
                top_prod_ids = [row['Product_ID'] for row in cursor.fetchall()]

                if not top_prod_ids:
                    return [], 0

                # Step 2: Fetch invoice lines belonging to these top products
                placeholders = ', '.join(['%s'] * len(top_prod_ids))
                query = f"""
                    SELECT f.InvoiceNo, p.Description AS item
                    FROM Fact_Sales f
                    JOIN Dim_Product p ON f.Product_ID = p.Product_ID
                    JOIN Dim_Country co ON f.Country_ID = co.Country_ID
                    {where_sql} AND f.Product_ID IN ({placeholders})
                    ORDER BY f.InvoiceNo;
                """
                cursor.execute(query, params + top_prod_ids)
                rows = cursor.fetchall()
        finally:
            conn.close()

        if not rows:
            return [], 0

        df = pd.DataFrame(rows)
        total_distinct_invoices = df['InvoiceNo'].nunique()

        # Group into unique item sets per invoice
        baskets = df.groupby('InvoiceNo')['item'].apply(lambda x: sorted(list(set(x)))).tolist()

        # Retain only multi-item transactions (baskets with >= 2 distinct items)
        multi_item_baskets = [b for b in baskets if len(b) >= 2]

        return multi_item_baskets, total_distinct_invoices
    except Exception as e:
        print(f"[Apriori Warning] Unable to extract baskets (tables may be uninitialized): {e}")
        return [], 0


def run_apriori(min_support=0.02, min_confidence=0.3, min_lift=1.0, country=None, top_n_products=150, max_rules=100, max_len=3):
    """Executes the complete Apriori association rule mining workflow.

    Args:
        min_support (float): Minimum support threshold (0.001 to 1.0).
        min_confidence (float): Minimum confidence threshold (0.01 to 1.0).
        min_lift (float): Minimum lift threshold (typically >= 1.0).
        country (str, optional): Geographic filter.
        top_n_products (int): Limit universe to top N products to avoid combinatorial explosion.
        max_rules (int): Maximum rules to return.
        max_len (int): Maximum itemset length for Apriori (default 3 for performance).

    Returns:
        dict: Mining results, summary statistics, and formatted association rules.
    """
    start_time = time.time()
    min_support = float(min_support)
    min_confidence = float(min_confidence)
    min_lift = float(min_lift)

    # 1. Fetch transaction baskets
    baskets, total_invoices = get_transaction_baskets(country=country, top_n_products=top_n_products)

    if not baskets or len(baskets) < 5:
        return {
            'status': 'NO_DATA',
            'message': 'Insufficient multi-item transaction baskets found in warehouse.',
            'summary': {
                'total_invoices': total_invoices,
                'multi_item_baskets': len(baskets) if baskets else 0,
                'frequent_itemsets_count': 0,
                'rules_generated': 0,
                'execution_time_seconds': round(time.time() - start_time, 2)
            },
            'rules': [],
            'metric_explanations': get_metric_explanations()
        }

    # 2. One-hot encode transactions
    te = TransactionEncoder()
    te_ary = te.fit(baskets).transform(baskets)
    df_encoded = pd.DataFrame(te_ary, columns=te.columns_)

    # 3. Mine frequent itemsets (max_len bounds combinatorial explosion)
    frequent_itemsets = apriori(df_encoded, min_support=min_support, max_len=max_len, use_colnames=True)

    if frequent_itemsets.empty:
        return {
            'status': 'NO_RULES',
            'message': f'No frequent itemsets found with minimum support >= {min_support}. Try lowering the support threshold (e.g., 0.01).',
            'summary': {
                'total_invoices': total_invoices,
                'multi_item_baskets': len(baskets),
                'frequent_itemsets_count': 0,
                'rules_generated': 0,
                'execution_time_seconds': round(time.time() - start_time, 2)
            },
            'rules': [],
            'metric_explanations': get_metric_explanations()
        }

    frequent_itemsets_count = len(frequent_itemsets)

    # 4. Generate association rules
    try:
        rules_df = association_rules(frequent_itemsets, metric="confidence", min_threshold=min_confidence)
    except Exception as e:
        rules_df = pd.DataFrame()

    if rules_df.empty:
        return {
            'status': 'NO_RULES',
            'message': f'Found {frequent_itemsets_count} frequent itemsets, but zero rules met confidence >= {min_confidence}. Try lowering confidence.',
            'summary': {
                'total_invoices': total_invoices,
                'multi_item_baskets': len(baskets),
                'frequent_itemsets_count': frequent_itemsets_count,
                'rules_generated': 0,
                'execution_time_seconds': round(time.time() - start_time, 2)
            },
            'rules': [],
            'metric_explanations': get_metric_explanations()
        }

    # 5. Filter by minimum lift and sort
    if min_lift > 0:
        rules_df = rules_df[rules_df['lift'] >= min_lift].copy()

    # Sort primarily by lift, secondarily by confidence descending
    rules_df = rules_df.sort_values(by=['lift', 'confidence'], ascending=[False, False])

    # Limit rules
    if max_rules and len(rules_df) > max_rules:
        rules_df = rules_df.head(max_rules)

    # Format rules for JSON / HTML display
    formatted_rules = []
    for _, row in rules_df.iterrows():
        antecedents_list = list(row['antecedents'])
        consequents_list = list(row['consequents'])
        formatted_rules.append({
            'antecedents': ', '.join(antecedents_list),
            'consequents': ', '.join(consequents_list),
            'antecedent_count': len(antecedents_list),
            'consequent_count': len(consequents_list),
            'support': round(float(row['support']), 4),
            'confidence': round(float(row['confidence']), 4),
            'confidence_pct': round(float(row['confidence']) * 100, 1),
            'lift': round(float(row['lift']), 4),
            'leverage': round(float(row.get('leverage', 0)), 4),
            'conviction': round(float(row.get('conviction', 0)), 4) if pd.notna(row.get('conviction')) and row.get('conviction') != float('inf') else 'inf'
        })

    duration = round(time.time() - start_time, 2)

    return {
        'status': 'SUCCESS',
        'parameters': {
            'min_support': min_support,
            'min_confidence': min_confidence,
            'min_lift': min_lift,
            'country': country or 'All Countries',
            'top_n_products': top_n_products
        },
        'summary': {
            'total_invoices': total_invoices,
            'multi_item_baskets': len(baskets),
            'frequent_itemsets_count': frequent_itemsets_count,
            'rules_generated': len(formatted_rules),
            'execution_time_seconds': duration
        },
        'rules': formatted_rules,
        'metric_explanations': get_metric_explanations()
    }


if __name__ == '__main__':
    print("=" * 65)
    print(" SmartMart Analytics - Apriori Association Rule Mining Demo")
    print("=" * 65)
    res = run_apriori(min_support=0.02, min_confidence=0.3, min_lift=1.2, top_n_products=100)
    print("Status:           ", res['status'])
    print("Total Baskets:    ", res['summary']['multi_item_baskets'])
    print("Frequent Itemsets:", res['summary']['frequent_itemsets_count'])
    print("Rules Generated:  ", res['summary']['rules_generated'])
    print("Execution Time:   ", res['summary']['execution_time_seconds'], "s")
    print("-" * 65)
    print("Top Mined Association Rules:")
    for i, r in enumerate(res['rules'][:5], 1):
        print(f"[{i}] IF {{{r['antecedents']}}}")
        print(f"    THEN {{{r['consequents']}}}")
        print(f"    Support={r['support']} | Confidence={r['confidence_pct']}% | Lift={r['lift']}")
    print("=" * 65)
