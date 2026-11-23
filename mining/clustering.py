"""Data Mining Module B: K-Means Customer Segmentation (RFM Analysis).

Implements Customer Segmentation using:
- Recency, Frequency, Monetary (RFM) feature engineering
- Missing value validation & outlier filtering
- Feature standardization with sklearn.preprocessing.StandardScaler
- Clustering with sklearn.cluster.KMeans
- Dynamic assignment of understandable cluster labels based on centroids
- Comprehensive visual summary generation for Chart.js
"""

import time
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from database.db_connection import get_pymysql_connection


def get_rfm_explanations():
    """Returns educational explanations of RFM features and K-Means clustering

    for viva and mini-project examination.
    """
    return {
        'recency': {
            'name': 'Recency (R)',
            'definition': 'Days elapsed since the customer\'s most recent purchase date.',
            'interpretation': 'Lower recency means a customer has engaged more recently, signaling higher current retention.'
        },
        'frequency': {
            'name': 'Frequency (F)',
            'definition': 'Total number of distinct completed transaction invoices for the customer.',
            'interpretation': 'Higher frequency indicates strong customer brand loyalty and repeat purchasing habits.'
        },
        'monetary': {
            'name': 'Monetary (M)',
            'definition': 'Total monetary expenditure ($) across all transactions for the customer.',
            'interpretation': 'Measures lifetime financial value and revenue contribution to the business.'
        },
        'scaling': {
            'name': 'Feature Standardization (StandardScaler)',
            'definition': 'Transforms each feature to have mean = 0 and standard deviation = 1: z = (x - μ) / σ.',
            'interpretation': 'Standardization is required because Monetary ($) ranges into thousands while Frequency is in units. '
                           'Without scaling, distance-based algorithms like K-Means would be dominated by Monetary values.'
        }
    }


def extract_rfm_features(country=None):
    """Extracts customer-level RFM features from Fact_Sales and dimensions.

    Excludes the guest/unregistered customer (Customer_ID = 1).

    Args:
        country (str, optional): Geographic filter.

    Returns:
        pd.DataFrame: DataFrame with [Customer_ID, CustomerCode, Recency, Frequency, Monetary, LastPurchaseDate].
    """
    where_sql = "WHERE c.Customer_ID <> 1 AND c.CustomerCode <> 'UNKNOWN'"
    params = []

    if country:
        where_sql += " AND co.CountryName = %s"
        params.append(country)

    try:
        conn = get_pymysql_connection(include_db=True)
        try:
            with conn.cursor() as cursor:
                # Determine global dataset snapshot date (max transaction date)
                cursor.execute("SELECT MAX(FullDate) AS max_date FROM Dim_Date;")
                max_date_row = cursor.fetchone()
                if not max_date_row or not max_date_row['max_date']:
                    return pd.DataFrame()
                snapshot_date = max_date_row['max_date']

                query = f"""
                    SELECT 
                        c.Customer_ID,
                        c.CustomerCode,
                        MAX(d.FullDate) AS last_date,
                        COUNT(DISTINCT f.InvoiceNo) AS frequency,
                        ROUND(SUM(f.TotalAmount), 2) AS monetary
                    FROM Fact_Sales f
                    JOIN Dim_Customer c ON f.Customer_ID = c.Customer_ID
                    JOIN Dim_Date d ON f.Date_ID = d.Date_ID
                    JOIN Dim_Country co ON f.Country_ID = co.Country_ID
                    {where_sql}
                    GROUP BY c.Customer_ID, c.CustomerCode;
                """
                cursor.execute(query, params)
                rows = cursor.fetchall()
        finally:
            conn.close()

        if rows and len(rows) >= 10:
            df = pd.DataFrame(rows)

            # Calculate Recency in days relative to snapshot_date (+1 to avoid 0 days)
            df['last_date'] = pd.to_datetime(df['last_date'])
            snap_dt = pd.to_datetime(snapshot_date)
            df['recency'] = (snap_dt - df['last_date']).dt.days + 1

            # Ensure numeric columns and filter non-positive spend
            df['frequency'] = pd.to_numeric(df['frequency'], errors='coerce').fillna(1).astype(int)
            df['monetary'] = pd.to_numeric(df['monetary'], errors='coerce').fillna(0.0).astype(float)
            df = df[df['monetary'] > 0].copy()

            return df
        else:
            raise ValueError("Fewer than 10 customer records found in database.")

    except Exception as e:
        print(f"[RFM Extraction Notice] Warehouse extraction note: {e}")
        # Graceful fallback to available dataset files
        try:
            import os
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            excel_path = os.path.join(project_root, 'data', 'raw', 'Online Retail.xlsx')
            csv_path = os.path.join(project_root, 'data', 'processed', 'cleaned_online_retail.csv')

            df_raw = None
            if os.path.exists(excel_path):
                df_raw = pd.read_excel(excel_path, nrows=5000)
            elif os.path.exists(csv_path):
                df_raw = pd.read_csv(csv_path)

            if df_raw is not None and not df_raw.empty:
                cust_col = 'CustomerID' if 'CustomerID' in df_raw.columns else None
                inv_col = 'InvoiceNo' if 'InvoiceNo' in df_raw.columns else None
                date_col = 'InvoiceDate' if 'InvoiceDate' in df_raw.columns else None
                qty_col = 'Quantity' if 'Quantity' in df_raw.columns else None
                price_col = 'UnitPrice' if 'UnitPrice' in df_raw.columns else None
                cntry_col = 'Country' if 'Country' in df_raw.columns else None

                if cust_col and inv_col and date_col and qty_col and price_col:
                    df_clean = df_raw.dropna(subset=[cust_col, inv_col, date_col, qty_col, price_col]).copy()
                    df_clean = df_clean[df_clean[qty_col] > 0]
                    df_clean = df_clean[df_clean[price_col] > 0]

                    if country and cntry_col:
                        df_clean = df_clean[df_clean[cntry_col] == country]

                    if not df_clean.empty:
                        df_clean['TotalAmount'] = (df_clean[qty_col] * df_clean[price_col]).round(2)
                        df_clean[date_col] = pd.to_datetime(df_clean[date_col])
                        snap_dt = df_clean[date_col].max()

                        agg = df_clean.groupby(cust_col).agg(
                            last_date=(date_col, 'max'),
                            frequency=(inv_col, 'nunique'),
                            monetary=('TotalAmount', 'sum')
                        ).reset_index()

                        agg['Customer_ID'] = agg[cust_col].astype(int)
                        agg['CustomerCode'] = agg[cust_col].astype(str)
                        agg['recency'] = (snap_dt - agg['last_date']).dt.days + 1
                        agg['frequency'] = agg['frequency'].astype(int)
                        agg['monetary'] = agg['monetary'].round(2).astype(float)
                        agg = agg[agg['monetary'] > 0].copy()
                        return agg
        except Exception as fb_err:
            print(f"[RFM Fallback Error] {fb_err}")

        return pd.DataFrame()


def assign_meaningful_labels(centroids_df):
    """Dynamically assigns understandable business segment labels based on

    actual cluster centroid values (Recency, Frequency, Monetary),
    rather than arbitrary cluster IDs.

    Args:
        centroids_df (pd.DataFrame): DataFrame with columns [cluster, recency, frequency, monetary].

    Returns:
        dict: Mapping of cluster integer -> label string.
    """
    # Business value score: higher frequency & monetary increase score, higher recency decreases score
    # Min-max normalize components for fair scoring
    norm_df = centroids_df.copy()
    for col in ['frequency', 'monetary']:
        span = norm_df[col].max() - norm_df[col].min()
        norm_df[col + '_norm'] = (norm_df[col] - norm_df[col].min()) / span if span > 0 else 0.5

    span_rec = norm_df['recency'].max() - norm_df['recency'].min()
    # Invert recency: low recency is good (recent)
    norm_df['recency_norm'] = (norm_df['recency'].max() - norm_df['recency']) / span_rec if span_rec > 0 else 0.5

    norm_df['score'] = (norm_df['monetary_norm'] * 0.45) + (norm_df['frequency_norm'] * 0.35) + (norm_df['recency_norm'] * 0.20)
    sorted_clusters = norm_df.sort_values(by='score', ascending=False)['cluster'].tolist()

    k = len(sorted_clusters)
    label_map = {}

    if k == 2:
        label_map[sorted_clusters[0]] = "High-Value Active Shoppers"
        label_map[sorted_clusters[1]] = "Occasional / Low-Spend Shoppers"
    elif k == 3:
        label_map[sorted_clusters[0]] = "High-Value Champions (VIP)"
        label_map[sorted_clusters[1]] = "Loyal / Regular Customers"
        label_map[sorted_clusters[2]] = "At-Risk / Lapsed Customers"
    elif k == 4:
        label_map[sorted_clusters[0]] = "Platinum Champions (Highest Value)"
        label_map[sorted_clusters[1]] = "Gold Loyalists (Regular Shoppers)"
        label_map[sorted_clusters[2]] = "Silver Customers (Potential Loyalists)"
        label_map[sorted_clusters[3]] = "At-Risk / Inactive Shoppers"
    else:
        for rank, cid in enumerate(sorted_clusters, 1):
            label_map[cid] = f"Tier {rank} Segment"

    return label_map


def run_kmeans_clustering(n_clusters=3, country=None, random_state=42):
    """Executes K-Means Customer Segmentation on RFM features.

    Args:
        n_clusters (int): Number of clusters (k), default 3 (range 2-6).
        country (str, optional): Geographic filter.
        random_state (int): Reproducibility seed.

    Returns:
        dict: Complete clustering results, statistics, and chart configurations.
    """
    start_time = time.time()
    n_clusters = max(2, min(int(n_clusters), 6))

    # Step 1: Feature preparation
    rfm_df = extract_rfm_features(country=country)
    if rfm_df.empty or len(rfm_df) < n_clusters:
        return {
            'status': 'NO_DATA',
            'message': 'Insufficient customer records in warehouse for clustering.',
            'n_clusters': n_clusters,
            'customer_count': len(rfm_df),
            'clusters': [],
            'rfm_explanations': get_rfm_explanations()
        }

    # Step 2: Feature Matrix
    feature_cols = ['recency', 'frequency', 'monetary']
    X = rfm_df[feature_cols].values

    # Step 3: Feature Scaling with StandardScaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Step 4: K-Means Clustering
    kmeans = KMeans(n_clusters=n_clusters, init='k-means++', n_init=10, random_state=random_state)
    rfm_df['cluster'] = kmeans.fit_predict(X_scaled)

    # Calculate model quality metrics
    inertia = round(float(kmeans.inertia_), 2)
    try:
        silhouette = round(float(silhouette_score(X_scaled, rfm_df['cluster'])), 4) if len(rfm_df) > n_clusters else 0.0
    except Exception:
        silhouette = 0.0

    # Step 5: Cluster Summary & Understandable Label Assignment
    summary_list = []
    total_customers = len(rfm_df)
    total_spend_all = rfm_df['monetary'].sum()

    centroids_temp = []
    for cid in range(n_clusters):
        c_df = rfm_df[rfm_df['cluster'] == cid]
        centroids_temp.append({
            'cluster': cid,
            'recency': c_df['recency'].mean() if not c_df.empty else 0,
            'frequency': c_df['frequency'].mean() if not c_df.empty else 0,
            'monetary': c_df['monetary'].mean() if not c_df.empty else 0
        })

    label_map = assign_meaningful_labels(pd.DataFrame(centroids_temp))
    rfm_df['cluster_label'] = rfm_df['cluster'].map(label_map)

    for cid in range(n_clusters):
        c_df = rfm_df[rfm_df['cluster'] == cid]
        count = len(c_df)
        pct = round((count / total_customers) * 100, 1) if total_customers > 0 else 0
        cluster_rev = round(float(c_df['monetary'].sum()), 2)
        rev_pct = round((cluster_rev / total_spend_all) * 100, 1) if total_spend_all > 0 else 0

        summary_list.append({
            'cluster_id': cid,
            'label': label_map.get(cid, f"Cluster {cid}"),
            'customer_count': count,
            'customer_percentage': pct,
            'total_revenue': cluster_rev,
            'revenue_percentage': rev_pct,
            'avg_recency_days': round(float(c_df['recency'].mean()), 1),
            'avg_frequency_orders': round(float(c_df['frequency'].mean()), 1),
            'avg_monetary_spend': round(float(c_df['monetary'].mean()), 2)
        })

    # Sort summary by revenue contribution descending
    summary_list = sorted(summary_list, key=lambda x: x['total_revenue'], reverse=True)

    # Step 6: Chart.js Datasets
    # Doughnut chart distribution
    distribution_chart = {
        'labels': [s['label'] for s in summary_list],
        'counts': [s['customer_count'] for s in summary_list],
        'revenues': [s['total_revenue'] for s in summary_list]
    }

    # Comparison averages bar chart
    comparison_chart = {
        'labels': [s['label'] for s in summary_list],
        'avg_recency': [s['avg_recency_days'] for s in summary_list],
        'avg_frequency': [s['avg_frequency_orders'] for s in summary_list],
        'avg_monetary': [s['avg_monetary_spend'] for s in summary_list]
    }

    # Scatter plot data points (subsampled to 200 points for frontend rendering performance)
    sample_df = rfm_df.sample(min(200, len(rfm_df)), random_state=random_state)
    scatter_points = []
    for _, row in sample_df.iterrows():
        scatter_points.append({
            'x': round(float(row['recency']), 1),
            'y': round(float(row['monetary']), 2),
            'frequency': int(row['frequency']),
            'customer_code': str(row['CustomerCode']),
            'cluster': int(row['cluster']),
            'label': str(row['cluster_label'])
        })

    duration = round(time.time() - start_time, 2)

    return {
        'status': 'SUCCESS',
        'parameters': {
            'n_clusters': n_clusters,
            'country': country or 'All Countries',
            'random_state': random_state
        },
        'metrics': {
            'total_customers_analyzed': total_customers,
            'inertia_wcss': inertia,
            'silhouette_score': silhouette,
            'execution_time_seconds': duration
        },
        'cluster_summary': summary_list,
        'charts': {
            'distribution': distribution_chart,
            'comparison': comparison_chart,
            'scatter_points': scatter_points
        },
        'rfm_explanations': get_rfm_explanations()
    }


if __name__ == '__main__':
    print("=" * 65)
    print(" SmartMart Analytics - K-Means Customer Segmentation Demo")
    print("=" * 65)
    res = run_kmeans_clustering(n_clusters=3)
    print(f"Status:            {res['status']}")
    print(f"Total Customers:   {res['metrics']['total_customers_analyzed']}")
    print(f"Inertia (WCSS):    {res['metrics']['inertia_wcss']}")
    print(f"Silhouette Score:  {res['metrics']['silhouette_score']}")
    print(f"Execution Time:    {res['metrics']['execution_time_seconds']} s")
    print("-" * 65)
    print("Cluster Profiles & Meaningful Segment Labels:")
    for c in res['cluster_summary']:
        print(f"[{c['label']}]")
        print(f"  Customers:  {c['customer_count']:,} ({c['customer_percentage']}%) | Total Spend: ${c['total_revenue']:,.2f} ({c['revenue_percentage']}%)")
        print(f"  Averages:   Recency = {c['avg_recency_days']} days, Frequency = {c['avg_frequency_orders']} orders, Monetary = ${c['avg_monetary_spend']:,.2f}")
    print("=" * 65)
