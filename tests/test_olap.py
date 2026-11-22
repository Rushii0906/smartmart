"""Test suite for Stage 4: OLAP Operations (Roll-up, Drill-down, Slice, Dice) and Reports."""

import pytest
import io
import pandas as pd
from analytics.olap import (
    get_warehouse_kpis,
    olap_rollup,
    olap_drilldown,
    olap_slice,
    olap_dice,
    get_monthly_revenue_chart,
    get_country_revenue_chart,
    get_top_products_chart,
    get_filter_options
)
from analytics.reports import (
    get_executive_insights,
    export_monthly_sales_csv,
    export_country_performance_csv,
    export_product_performance_csv
)


def test_get_warehouse_kpis():
    """Verify that KPI calculation returns valid numeric figures from warehouse."""
    kpis = get_warehouse_kpis()
    assert isinstance(kpis, dict)
    assert kpis['total_revenue'] > 0
    assert kpis['total_invoices'] > 0
    assert kpis['total_quantity'] > 0
    assert kpis['avg_invoice_value'] > 0
    assert kpis['unique_products'] > 0


def test_olap_rollup_monthly():
    """Verify OLAP Roll-up at monthly granularity."""
    results = olap_rollup(level='monthly')
    assert isinstance(results, list)
    assert len(results) > 0

    first = results[0]
    assert 'YearNumber' in first
    assert 'MonthNumber' in first
    assert 'MonthName' in first
    assert 'total_revenue' in first
    assert 'total_invoices' in first
    assert first['total_revenue'] > 0


def test_olap_rollup_yearly():
    """Verify OLAP Roll-up at yearly granularity."""
    results = olap_rollup(level='yearly')
    assert isinstance(results, list)
    assert len(results) > 0
    for r in results:
        assert 'YearNumber' in r
        assert r['total_revenue'] > 0


def test_olap_drilldown_quarters_and_days():
    """Verify OLAP Drill-down down to quarters and down to individual days."""
    # Step 1: Get available years
    options = get_filter_options()
    assert len(options['years']) > 0
    sample_year = options['years'][0]

    # Drill-down to quarters
    quarters = olap_drilldown(year=sample_year)
    assert isinstance(quarters, list)
    assert len(quarters) > 0
    assert 'QuarterNumber' in quarters[0]

    # Drill-down to days of month 12
    days = olap_drilldown(year=sample_year, month=12)
    assert isinstance(days, list)
    assert len(days) > 0
    assert 'FullDate' in days[0]
    assert 'DayNumber' in days[0]


def test_olap_slice_country():
    """Verify OLAP Slice by fixing Country dimension."""
    slice_res = olap_slice(dimension='country', value='United Kingdom')
    assert slice_res['operation'] == 'SLICE'
    assert slice_res['fixed_dimension'] == 'country'
    assert slice_res['fixed_value'] == 'United Kingdom'
    assert slice_res['total_revenue'] > 0
    assert len(slice_res['records']) > 0


def test_olap_slice_year():
    """Verify OLAP Slice by fixing Year dimension."""
    options = get_filter_options()
    sample_year = options['years'][0]

    slice_res = olap_slice(dimension='year', value=sample_year)
    assert slice_res['operation'] == 'SLICE'
    assert slice_res['fixed_dimension'] == 'year'
    assert slice_res['total_revenue'] > 0
    assert len(slice_res['records']) > 0
    assert 'CountryName' in slice_res['records'][0]


def test_olap_dice():
    """Verify OLAP Dice across multiple countries and revenue thresholds."""
    options = get_filter_options()
    selected_countries = options['countries'][:3]

    dice_res = olap_dice(countries=selected_countries, min_revenue=10.0, limit=20)
    assert dice_res['operation'] == 'DICE'
    assert isinstance(dice_res['records'], list)
    assert len(dice_res['records']) > 0

    for rec in dice_res['records']:
        assert rec['CountryName'] in selected_countries
        assert rec['total_revenue'] >= 10.0


def test_chart_data_queries():
    """Verify Chart.js datasets for monthly, country, and product visualisations."""
    monthly_chart = get_monthly_revenue_chart()
    assert 'labels' in monthly_chart
    assert 'revenues' in monthly_chart
    assert len(monthly_chart['labels']) == len(monthly_chart['revenues'])
    assert len(monthly_chart['labels']) > 0

    country_chart = get_country_revenue_chart(limit=5)
    assert len(country_chart['labels']) <= 5
    assert len(country_chart['labels']) == len(country_chart['revenues'])

    product_chart = get_top_products_chart(limit=5)
    assert len(product_chart['labels']) <= 5
    assert len(product_chart['labels']) == len(product_chart['revenues'])


def test_executive_insights_and_reports():
    """Verify executive summary generation and CSV exports."""
    insights = get_executive_insights()
    assert 'kpis' in insights
    assert 'key_findings' in insights
    assert len(insights['key_findings']) >= 3

    # Monthly CSV export
    monthly_csv = export_monthly_sales_csv()
    assert 'Year,Month,Month_Name,Total_Invoices' in monthly_csv
    df_m = pd.read_csv(io.StringIO(monthly_csv))
    assert not df_m.empty

    # Country CSV export
    country_csv = export_country_performance_csv()
    assert 'Country,Total_Invoices' in country_csv
    df_c = pd.read_csv(io.StringIO(country_csv))
    assert not df_c.empty

    # Product CSV export
    prod_csv = export_product_performance_csv(limit=50)
    assert 'Stock_Code,Description,Total_Units_Sold' in prod_csv
    df_p = pd.read_csv(io.StringIO(prod_csv))
    assert not df_p.empty
