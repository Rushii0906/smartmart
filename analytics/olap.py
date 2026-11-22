"""OLAP Analytics Module for SmartMart Analytics.

Implements the four foundational OLAP operations on the Star Schema:
1. Roll-up: Aggregates sales data to higher levels of time granularity (Day -> Month -> Year).
2. Drill-down: Navigates from summarized high-level data down to detailed levels (Year -> Quarter -> Month -> Day).
3. Slice: Produces a 2D sub-cube by fixing exactly one dimension (e.g. Country or Year).
4. Dice: Selects a sub-cube by applying multi-dimensional filters across multiple dimensions simultaneously.

Also provides chart-ready analytical datasets for Chart.js visualisations.
"""

from database.db_connection import get_pymysql_connection


def get_warehouse_kpis(filters=None):
    """Calculates top-level KPI metrics from Fact_Sales and dimensions.

    Args:
        filters (dict, optional): Optional filters (country, year).

    Returns:
        dict: Top-level metrics.
    """
    where_clauses = ["1=1"]
    params = []

    if filters:
        if filters.get('country'):
            where_clauses.append("co.CountryName = %s")
            params.append(filters['country'])
        if filters.get('year'):
            where_clauses.append("d.YearNumber = %s")
            params.append(int(filters['year']))

    where_str = " AND ".join(where_clauses)

    query = f"""
        SELECT 
            COUNT(DISTINCT f.InvoiceNo) AS total_invoices,
            COALESCE(SUM(f.Quantity), 0) AS total_quantity,
            ROUND(COALESCE(SUM(f.TotalAmount), 0), 2) AS total_revenue,
            COUNT(DISTINCT CASE WHEN f.Customer_ID > 1 THEN f.Customer_ID END) AS registered_customers,
            COUNT(DISTINCT f.Customer_ID) AS total_customers,
            COUNT(DISTINCT f.Product_ID) AS unique_products,
            COUNT(f.Sales_ID) AS fact_rows
        FROM Fact_Sales f
        JOIN Dim_Date d ON f.Date_ID = d.Date_ID
        JOIN Dim_Country co ON f.Country_ID = co.Country_ID
        WHERE {where_str};
    """

    conn = get_pymysql_connection(include_db=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            res = cursor.fetchone()

        total_rev = float(res['total_revenue'] or 0.0)
        total_inv = int(res['total_invoices'] or 0)
        avg_inv_val = round(total_rev / total_inv, 2) if total_inv > 0 else 0.0

        return {
            'total_revenue': total_rev,
            'total_invoices': total_inv,
            'total_quantity': int(res['total_quantity'] or 0),
            'registered_customers': int(res['registered_customers'] or 0),
            'total_customers': int(res['total_customers'] or 0),
            'unique_products': int(res['unique_products'] or 0),
            'fact_rows': int(res['fact_rows'] or 0),
            'avg_invoice_value': avg_inv_val
        }
    finally:
        conn.close()


def olap_rollup(level='monthly', year=None):
    """OLAP Roll-up Operation: Aggregates sales data to a higher level of time hierarchy.

    Args:
        level (str): 'yearly', 'quarterly', or 'monthly' (default).
        year (int, optional): Restrict aggregation to a specific year.

    Returns:
        list of dict: Aggregated time periods and metrics.
    """
    where_sql = "WHERE 1=1"
    params = []
    if year:
        where_sql += " AND d.YearNumber = %s"
        params.append(int(year))

    if level == 'yearly':
        query = f"""
            SELECT 
                d.YearNumber,
                COUNT(DISTINCT f.InvoiceNo) AS total_invoices,
                SUM(f.Quantity) AS total_quantity,
                ROUND(SUM(f.TotalAmount), 2) AS total_revenue,
                ROUND(AVG(f.TotalAmount), 2) AS avg_line_value
            FROM Fact_Sales f
            JOIN Dim_Date d ON f.Date_ID = d.Date_ID
            {where_sql}
            GROUP BY d.YearNumber
            ORDER BY d.YearNumber;
        """
    elif level == 'quarterly':
        query = f"""
            SELECT 
                d.YearNumber,
                d.QuarterNumber,
                CONCAT(d.YearNumber, ' Q', d.QuarterNumber) AS period_label,
                COUNT(DISTINCT f.InvoiceNo) AS total_invoices,
                SUM(f.Quantity) AS total_quantity,
                ROUND(SUM(f.TotalAmount), 2) AS total_revenue,
                ROUND(AVG(f.TotalAmount), 2) AS avg_line_value
            FROM Fact_Sales f
            JOIN Dim_Date d ON f.Date_ID = d.Date_ID
            {where_sql}
            GROUP BY d.YearNumber, d.QuarterNumber
            ORDER BY d.YearNumber, d.QuarterNumber;
        """
    else:  # monthly
        query = f"""
            SELECT 
                d.YearNumber,
                d.MonthNumber,
                d.MonthName,
                CONCAT(d.MonthName, ' ', d.YearNumber) AS period_label,
                COUNT(DISTINCT f.InvoiceNo) AS total_invoices,
                SUM(f.Quantity) AS total_quantity,
                ROUND(SUM(f.TotalAmount), 2) AS total_revenue,
                ROUND(AVG(f.TotalAmount), 2) AS avg_line_value
            FROM Fact_Sales f
            JOIN Dim_Date d ON f.Date_ID = d.Date_ID
            {where_sql}
            GROUP BY d.YearNumber, d.MonthNumber, d.MonthName
            ORDER BY d.YearNumber, d.MonthNumber;
        """

    conn = get_pymysql_connection(include_db=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        # Convert Decimal values for clean serialization
        for r in rows:
            r['total_revenue'] = float(r['total_revenue'])
            r['avg_line_value'] = float(r['avg_line_value'])
            r['total_quantity'] = int(r['total_quantity'])
        return rows
    finally:
        conn.close()


def olap_drilldown(year, quarter=None, month=None):
    """OLAP Drill-down Operation: Navigates from summarized high-level data

    down to more granular time levels.

    Args:
        year (int): Required starting year.
        quarter (int, optional): If specified, drills down to months in this quarter.
        month (int, optional): If specified, drills down to daily sales in this month.

    Returns:
        list of dict: Detailed breakdown records.
    """
    conn = get_pymysql_connection(include_db=True)
    try:
        with conn.cursor() as cursor:
            if month is not None:
                # Drill-down to Daily sales for the selected year and month
                query = """
                    SELECT 
                        d.FullDate,
                        d.DayNumber,
                        COUNT(DISTINCT f.InvoiceNo) AS total_invoices,
                        SUM(f.Quantity) AS total_quantity,
                        ROUND(SUM(f.TotalAmount), 2) AS total_revenue
                    FROM Fact_Sales f
                    JOIN Dim_Date d ON f.Date_ID = d.Date_ID
                    WHERE d.YearNumber = %s AND d.MonthNumber = %s
                    GROUP BY d.FullDate, d.DayNumber
                    ORDER BY d.DayNumber;
                """
                cursor.execute(query, (int(year), int(month)))
                rows = cursor.fetchall()
                for r in rows:
                    r['FullDate'] = str(r['FullDate'])
                    r['total_revenue'] = float(r['total_revenue'])
                    r['total_quantity'] = int(r['total_quantity'])
                return rows

            elif quarter is not None:
                # Drill-down to Months in the selected quarter
                query = """
                    SELECT 
                        d.MonthNumber,
                        d.MonthName,
                        COUNT(DISTINCT f.InvoiceNo) AS total_invoices,
                        SUM(f.Quantity) AS total_quantity,
                        ROUND(SUM(f.TotalAmount), 2) AS total_revenue
                    FROM Fact_Sales f
                    JOIN Dim_Date d ON f.Date_ID = d.Date_ID
                    WHERE d.YearNumber = %s AND d.QuarterNumber = %s
                    GROUP BY d.MonthNumber, d.MonthName
                    ORDER BY d.MonthNumber;
                """
                cursor.execute(query, (int(year), int(quarter)))
                rows = cursor.fetchall()
                for r in rows:
                    r['total_revenue'] = float(r['total_revenue'])
                    r['total_quantity'] = int(r['total_quantity'])
                return rows

            else:
                # Drill-down to Quarters of the selected year
                query = """
                    SELECT 
                        d.QuarterNumber,
                        CONCAT('Quarter ', d.QuarterNumber) AS quarter_label,
                        COUNT(DISTINCT f.InvoiceNo) AS total_invoices,
                        SUM(f.Quantity) AS total_quantity,
                        ROUND(SUM(f.TotalAmount), 2) AS total_revenue
                    FROM Fact_Sales f
                    JOIN Dim_Date d ON f.Date_ID = d.Date_ID
                    WHERE d.YearNumber = %s
                    GROUP BY d.QuarterNumber
                    ORDER BY d.QuarterNumber;
                """
                cursor.execute(query, (int(year),))
                rows = cursor.fetchall()
                for r in rows:
                    r['total_revenue'] = float(r['total_revenue'])
                    r['total_quantity'] = int(r['total_quantity'])
                return rows
    finally:
        conn.close()


def olap_slice(dimension, value):
    """OLAP Slice Operation: Filters data on exactly one dimension to produce a 2D slice.

    Args:
        dimension (str): 'country', 'year', or 'product'
        value (str or int): Dimension value to fix (e.g., 'United Kingdom' or 2011)

    Returns:
        dict: Sliced analysis containing records, totals, and dimension metadata.
    """
    conn = get_pymysql_connection(include_db=True)
    try:
        with conn.cursor() as cursor:
            if dimension == 'country':
                query = """
                    SELECT 
                        d.YearNumber,
                        d.MonthNumber,
                        d.MonthName,
                        COUNT(DISTINCT f.InvoiceNo) AS total_invoices,
                        SUM(f.Quantity) AS total_quantity,
                        ROUND(SUM(f.TotalAmount), 2) AS total_revenue
                    FROM Fact_Sales f
                    JOIN Dim_Country co ON f.Country_ID = co.Country_ID
                    JOIN Dim_Date d ON f.Date_ID = d.Date_ID
                    WHERE co.CountryName = %s
                    GROUP BY d.YearNumber, d.MonthNumber, d.MonthName
                    ORDER BY d.YearNumber, d.MonthNumber;
                """
                cursor.execute(query, (str(value),))
                rows = cursor.fetchall()

            elif dimension == 'year':
                query = """
                    SELECT 
                        co.CountryName,
                        COUNT(DISTINCT f.InvoiceNo) AS total_invoices,
                        SUM(f.Quantity) AS total_quantity,
                        ROUND(SUM(f.TotalAmount), 2) AS total_revenue
                    FROM Fact_Sales f
                    JOIN Dim_Country co ON f.Country_ID = co.Country_ID
                    JOIN Dim_Date d ON f.Date_ID = d.Date_ID
                    WHERE d.YearNumber = %s
                    GROUP BY co.CountryName
                    ORDER BY total_revenue DESC;
                """
                cursor.execute(query, (int(value),))
                rows = cursor.fetchall()

            elif dimension == 'product':
                query = """
                    SELECT 
                        d.YearNumber,
                        d.MonthName,
                        co.CountryName,
                        SUM(f.Quantity) AS total_quantity,
                        ROUND(SUM(f.TotalAmount), 2) AS total_revenue
                    FROM Fact_Sales f
                    JOIN Dim_Product p ON f.Product_ID = p.Product_ID
                    JOIN Dim_Date d ON f.Date_ID = d.Date_ID
                    JOIN Dim_Country co ON f.Country_ID = co.Country_ID
                    WHERE p.StockCode = %s OR p.Product_ID = %s
                    GROUP BY d.YearNumber, d.MonthName, d.MonthNumber, co.CountryName
                    ORDER BY d.YearNumber, d.MonthNumber, total_revenue DESC;
                """
                cursor.execute(query, (str(value), str(value)))
                rows = cursor.fetchall()

            else:
                rows = []

        for r in rows:
            r['total_revenue'] = float(r['total_revenue'])
            r['total_quantity'] = int(r['total_quantity'])

        total_rev = round(sum(r['total_revenue'] for r in rows), 2)
        total_qty = sum(r['total_quantity'] for r in rows)

        return {
            'operation': 'SLICE',
            'fixed_dimension': dimension,
            'fixed_value': value,
            'total_revenue': total_rev,
            'total_quantity': total_qty,
            'rows_count': len(rows),
            'records': rows
        }
    finally:
        conn.close()


def olap_dice(countries=None, years=None, min_revenue=None, max_revenue=None, limit=50):
    """OLAP Dice Operation: Evaluates multi-dimensional filters across multiple dimensions.

    Args:
        countries (list, optional): List of country names.
        years (list, optional): List of integer years.
        min_revenue (float, optional): Lower bound on line total amount.
        max_revenue (float, optional): Upper bound on line total amount.
        limit (int): Maximum records to return.

    Returns:
        dict: Diced sub-cube containing filtered records and aggregated totals.
    """
    where_clauses = ["1=1"]
    params = []

    if countries and len(countries) > 0:
        placeholders = ', '.join(['%s'] * len(countries))
        where_clauses.append(f"co.CountryName IN ({placeholders})")
        params.extend(countries)

    if years and len(years) > 0:
        placeholders = ', '.join(['%s'] * len(years))
        where_clauses.append(f"d.YearNumber IN ({placeholders})")
        params.extend([int(y) for y in years])

    if min_revenue is not None:
        where_clauses.append("f.TotalAmount >= %s")
        params.append(float(min_revenue))

    if max_revenue is not None:
        where_clauses.append("f.TotalAmount <= %s")
        params.append(float(max_revenue))

    where_sql = " AND ".join(where_clauses)

    query = f"""
        SELECT 
            co.CountryName,
            d.YearNumber,
            d.MonthName,
            p.StockCode,
            p.Description,
            SUM(f.Quantity) AS total_quantity,
            ROUND(SUM(f.TotalAmount), 2) AS total_revenue
        FROM Fact_Sales f
        JOIN Dim_Country co ON f.Country_ID = co.Country_ID
        JOIN Dim_Date d ON f.Date_ID = d.Date_ID
        JOIN Dim_Product p ON f.Product_ID = p.Product_ID
        WHERE {where_sql}
        GROUP BY co.CountryName, d.YearNumber, d.MonthName, d.MonthNumber, p.StockCode, p.Description
        ORDER BY total_revenue DESC
        LIMIT %s;
    """
    params.append(int(limit))

    conn = get_pymysql_connection(include_db=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        for r in rows:
            r['total_revenue'] = float(r['total_revenue'])
            r['total_quantity'] = int(r['total_quantity'])

        return {
            'operation': 'DICE',
            'filters': {
                'countries': countries or [],
                'years': years or [],
                'min_revenue': min_revenue,
                'max_revenue': max_revenue
            },
            'rows_count': len(rows),
            'records': rows
        }
    finally:
        conn.close()


def get_monthly_revenue_chart(country=None, year=None):
    """Prepares structured chronological data for Chart.js line charts."""
    where_clauses = ["1=1"]
    params = []
    if country:
        where_clauses.append("co.CountryName = %s")
        params.append(country)
    if year:
        where_clauses.append("d.YearNumber = %s")
        params.append(int(year))

    where_sql = " AND ".join(where_clauses)
    query = f"""
        SELECT 
            d.YearNumber,
            d.MonthNumber,
            d.MonthName,
            CONCAT(SUBSTRING(d.MonthName, 1, 3), ' ', d.YearNumber) AS label,
            ROUND(SUM(f.TotalAmount), 2) AS revenue,
            COUNT(DISTINCT f.InvoiceNo) AS invoices,
            SUM(f.Quantity) AS quantity
        FROM Fact_Sales f
        JOIN Dim_Date d ON f.Date_ID = d.Date_ID
        JOIN Dim_Country co ON f.Country_ID = co.Country_ID
        WHERE {where_sql}
        GROUP BY d.YearNumber, d.MonthNumber, d.MonthName
        ORDER BY d.YearNumber, d.MonthNumber;
    """

    conn = get_pymysql_connection(include_db=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        labels = [r['label'] for r in rows]
        revenues = [float(r['revenue']) for r in rows]
        invoices = [int(r['invoices']) for r in rows]
        quantities = [int(r['quantity']) for r in rows]

        return {
            'labels': labels,
            'revenues': revenues,
            'invoices': invoices,
            'quantities': quantities
        }
    finally:
        conn.close()


def get_country_revenue_chart(limit=10):
    """Prepares top countries by revenue for Chart.js horizontal bar charts."""
    query = """
        SELECT 
            co.CountryName,
            ROUND(SUM(f.TotalAmount), 2) AS total_revenue,
            COUNT(DISTINCT f.InvoiceNo) AS invoices
        FROM Fact_Sales f
        JOIN Dim_Country co ON f.Country_ID = co.Country_ID
        GROUP BY co.CountryName
        ORDER BY total_revenue DESC
        LIMIT %s;
    """
    conn = get_pymysql_connection(include_db=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (int(limit),))
            rows = cursor.fetchall()

        return {
            'labels': [r['CountryName'] for r in rows],
            'revenues': [float(r['total_revenue']) for r in rows],
            'invoices': [int(r['invoices']) for r in rows]
        }
    finally:
        conn.close()


def get_top_products_chart(limit=10):
    """Prepares top products by revenue for Chart.js bar charts."""
    query = """
        SELECT 
            p.StockCode,
            COALESCE(p.Description, p.StockCode) AS product_name,
            ROUND(SUM(f.TotalAmount), 2) AS total_revenue,
            SUM(f.Quantity) AS total_quantity
        FROM Fact_Sales f
        JOIN Dim_Product p ON f.Product_ID = p.Product_ID
        GROUP BY p.Product_ID, p.StockCode, p.Description
        ORDER BY total_revenue DESC
        LIMIT %s;
    """
    conn = get_pymysql_connection(include_db=True)
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (int(limit),))
            rows = cursor.fetchall()

        # Truncate overly long descriptions for chart aesthetics
        labels = [(r['product_name'][:25] + '...' if len(r['product_name']) > 25 else r['product_name']) for r in rows]

        return {
            'labels': labels,
            'stock_codes': [r['StockCode'] for r in rows],
            'revenues': [float(r['total_revenue']) for r in rows],
            'quantities': [int(r['total_quantity']) for r in rows]
        }
    finally:
        conn.close()


def get_filter_options():
    """Fetches dynamic dimension members for dropdown filters in the frontend."""
    try:
        conn = get_pymysql_connection(include_db=True)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT DISTINCT CountryName FROM Dim_Country ORDER BY CountryName;")
                countries = [r['CountryName'] for r in cursor.fetchall()]

                cursor.execute("SELECT DISTINCT YearNumber FROM Dim_Date ORDER BY YearNumber;")
                years = [r['YearNumber'] for r in cursor.fetchall()]

                cursor.execute("SELECT DISTINCT MonthNumber, MonthName FROM Dim_Date ORDER BY MonthNumber;")
                months = cursor.fetchall()

                cursor.execute("""
                    SELECT Product_ID, StockCode, COALESCE(Description, StockCode) AS Description 
                    FROM Dim_Product 
                    ORDER BY Description 
                    LIMIT 50;
                """)
                top_products = cursor.fetchall()

            return {
                'countries': countries,
                'years': years,
                'months': months,
                'products': top_products
            }
        finally:
            conn.close()
    except Exception as e:
        print(f"[Filter Options Warning] Falling back to empty filters: {e}")
        return {
            'countries': [],
            'years': [],
            'months': [],
            'products': []
        }
