"""Reporting and Data Export Module for SmartMart Analytics.

Generates business intelligence analytical summaries and provides
CSV export capabilities for OLAP and dimensional sales reports.
"""

import io
import csv
import pandas as pd
from database.db_connection import get_pymysql_connection
from analytics.olap import get_warehouse_kpis, olap_rollup


def get_executive_insights():
    """Generates an executive summary of key analytical insights derived

    from the retail data warehouse.

    Returns:
        dict: High-level business findings.
    """
    kpis = get_warehouse_kpis()
    conn = get_pymysql_connection(include_db=True)

    try:
        with conn.cursor() as cursor:
            # Top Country Contribution
            cursor.execute("""
                SELECT co.CountryName, ROUND(SUM(f.TotalAmount), 2) AS country_rev
                FROM Fact_Sales f
                JOIN Dim_Country co ON f.Country_ID = co.Country_ID
                GROUP BY co.CountryName
                ORDER BY country_rev DESC
                LIMIT 1;
            """)
            top_country = cursor.fetchone()

            # Top Product Contribution
            cursor.execute("""
                SELECT p.StockCode, p.Description, ROUND(SUM(f.TotalAmount), 2) AS prod_rev, SUM(f.Quantity) AS prod_qty
                FROM Fact_Sales f
                JOIN Dim_Product p ON f.Product_ID = p.Product_ID
                GROUP BY p.Product_ID, p.StockCode, p.Description
                ORDER BY prod_rev DESC
                LIMIT 1;
            """)
            top_prod = cursor.fetchone()

            # Registered vs Guest (Unknown) Customer Breakdown
            cursor.execute("""
                SELECT 
                    CASE WHEN f.Customer_ID = 1 THEN 'Guest (Unknown)' ELSE 'Registered Customer' END AS customer_type,
                    COUNT(DISTINCT f.InvoiceNo) AS invoices,
                    ROUND(SUM(f.TotalAmount), 2) AS revenue
                FROM Fact_Sales f
                GROUP BY customer_type;
            """)
            cust_breakdown = cursor.fetchall()

        total_rev = kpis['total_revenue']
        top_country_share = round((float(top_country['country_rev']) / total_rev) * 100, 1) if total_rev > 0 and top_country else 0.0
        top_prod_share = round((float(top_prod['prod_rev']) / total_rev) * 100, 1) if total_rev > 0 and top_prod else 0.0

        findings = [
            f"Total retail revenue generated is ${total_rev:,.2f} across {kpis['total_invoices']:,} distinct customer invoices.",
            f"The primary revenue-generating market is '{top_country['CountryName'] if top_country else 'N/A'}' accounting for {top_country_share}% of total turnover.",
            f"The best-performing individual product is '{top_prod['Description'] if top_prod else 'N/A'}' generating ${float(top_prod['prod_rev'] or 0):,.2f} ({top_prod_share}% share).",
            f"Average revenue per transaction invoice stands at ${kpis['avg_invoice_value']:,.2f} with {kpis['total_quantity']:,} units sold in total."
        ]

        return {
            'kpis': kpis,
            'top_market': top_country,
            'top_product': top_prod,
            'customer_breakdown': cust_breakdown,
            'key_findings': findings
        }
    finally:
        conn.close()


def export_monthly_sales_csv():
    """Exports monthly aggregated sales roll-up report to CSV format string."""
    conn = get_pymysql_connection(include_db=True)
    try:
        query = """
            SELECT 
                d.YearNumber AS Year,
                d.MonthNumber AS Month,
                d.MonthName AS Month_Name,
                COUNT(DISTINCT f.InvoiceNo) AS Total_Invoices,
                SUM(f.Quantity) AS Units_Sold,
                ROUND(SUM(f.TotalAmount), 2) AS Total_Revenue,
                ROUND(AVG(f.TotalAmount), 2) AS Avg_Line_Value
            FROM Fact_Sales f
            JOIN Dim_Date d ON f.Date_ID = d.Date_ID
            GROUP BY d.YearNumber, d.MonthNumber, d.MonthName
            ORDER BY d.YearNumber, d.MonthNumber;
        """
        with conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        df = pd.DataFrame(rows)
        output = io.StringIO()
        df.to_csv(output, index=False)
        return output.getvalue()
    finally:
        conn.close()


def export_country_performance_csv():
    """Exports country-wise sales breakdown report to CSV format string."""
    conn = get_pymysql_connection(include_db=True)
    try:
        query = """
            SELECT 
                co.CountryName AS Country,
                COUNT(DISTINCT f.InvoiceNo) AS Total_Invoices,
                COUNT(DISTINCT f.Customer_ID) AS Unique_Customers,
                SUM(f.Quantity) AS Units_Sold,
                ROUND(SUM(f.TotalAmount), 2) AS Total_Revenue,
                ROUND(AVG(f.TotalAmount), 2) AS Avg_Line_Value
            FROM Fact_Sales f
            JOIN Dim_Country co ON f.Country_ID = co.Country_ID
            GROUP BY co.CountryName
            ORDER BY Total_Revenue DESC;
        """
        with conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        df = pd.DataFrame(rows)
        output = io.StringIO()
        df.to_csv(output, index=False)
        return output.getvalue()
    finally:
        conn.close()


def export_product_performance_csv(limit=500):
    """Exports detailed product performance report to CSV format string."""
    conn = get_pymysql_connection(include_db=True)
    try:
        query = """
            SELECT 
                p.StockCode AS Stock_Code,
                COALESCE(p.Description, '(No Description)') AS Description,
                SUM(f.Quantity) AS Total_Units_Sold,
                ROUND(SUM(f.TotalAmount), 2) AS Total_Revenue,
                ROUND(AVG(f.UnitPrice), 2) AS Avg_Unit_Price,
                COUNT(DISTINCT f.InvoiceNo) AS Total_Orders
            FROM Fact_Sales f
            JOIN Dim_Product p ON f.Product_ID = p.Product_ID
            GROUP BY p.Product_ID, p.StockCode, p.Description
            ORDER BY Total_Revenue DESC
            LIMIT %s;
        """
        with conn.cursor() as cursor:
            cursor.execute(query, (int(limit),))
            rows = cursor.fetchall()

        df = pd.DataFrame(rows)
        output = io.StringIO()
        df.to_csv(output, index=False)
        return output.getvalue()
    finally:
        conn.close()
