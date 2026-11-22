"""OLAP Analytics Blueprint for SmartMart Analytics.

Implements web controllers for:
- Roll-up
- Drill-down
- Slice
- Dice
"""

from flask import Blueprint, render_template, request
from analytics.olap import (
    olap_rollup,
    olap_drilldown,
    olap_slice,
    olap_dice,
    get_filter_options
)

olap_bp = Blueprint('olap', __name__)


@olap_bp.route('/olap', methods=['GET'])
def olap_view():
    """Renders the multidimensional OLAP analytics interface."""
    active_op = request.args.get('op', 'rollup')
    filter_options = get_filter_options()

    results = []
    chart_labels = []
    chart_revenues = []

    # Parameters for preservation in form
    rollup_level = request.args.get('rollup_level', 'monthly')
    rollup_year = request.args.get('rollup_year', '')

    drill_year = request.args.get('drill_year', str(filter_options['years'][0]) if filter_options['years'] else '2010')
    drill_quarter = request.args.get('drill_quarter', '')
    drill_month = request.args.get('drill_month', '')

    slice_dim = request.args.get('slice_dim', 'country')
    slice_val = request.args.get('slice_val_country') if slice_dim == 'country' else request.args.get('slice_val_year')
    if not slice_val:
        slice_val = filter_options['countries'][0] if filter_options['countries'] else 'United Kingdom'

    selected_dice_countries = request.args.getlist('dice_countries')
    selected_dice_years = request.args.getlist('dice_years')
    dice_min_rev = request.args.get('dice_min_rev', '10.0')

    # Execute corresponding OLAP operation
    if active_op == 'rollup':
        year_filter = int(rollup_year) if rollup_year else None
        results = olap_rollup(level=rollup_level, year=year_filter)
        chart_labels = [r.get('period_label') or str(r.get('YearNumber')) for r in results]
        chart_revenues = [r['total_revenue'] for r in results]

    elif active_op == 'drilldown':
        q_val = int(drill_quarter) if drill_quarter else None
        m_val = int(drill_month) if drill_month else None
        results = olap_drilldown(year=int(drill_year), quarter=q_val, month=m_val)
        chart_labels = [str(r.get('FullDate') or r.get('MonthName') or r.get('quarter_label')) for r in results]
        chart_revenues = [r['total_revenue'] for r in results]

    elif active_op == 'slice':
        slice_res = olap_slice(dimension=slice_dim, value=slice_val)
        results = slice_res['records']
        if slice_dim == 'country':
            chart_labels = [f"{r['MonthName']} {r['YearNumber']}" for r in results]
        else:
            chart_labels = [r['CountryName'] for r in results[:10]]
        chart_revenues = [r['total_revenue'] for r in results[:len(chart_labels)]]

    elif active_op == 'dice':
        min_rev = float(dice_min_rev) if dice_min_rev else 0.0
        dice_res = olap_dice(
            countries=selected_dice_countries,
            years=selected_dice_years,
            min_revenue=min_rev,
            limit=25
        )
        results = dice_res['records']
        chart_labels = [f"{r['CountryName']} ({r['StockCode']})" for r in results[:8]]
        chart_revenues = [r['total_revenue'] for r in results[:8]]

    olap_chart = {
        'labels': chart_labels,
        'revenues': chart_revenues
    }

    return render_template(
        'olap.html',
        active_op=active_op,
        filter_options=filter_options,
        results=results,
        olap_chart=olap_chart,
        rollup_level=rollup_level,
        rollup_year=rollup_year,
        drill_year=drill_year,
        drill_quarter=drill_quarter,
        drill_month=drill_month,
        slice_dim=slice_dim,
        slice_val=slice_val,
        selected_dice_countries=selected_dice_countries,
        selected_dice_years=selected_dice_years,
        dice_min_rev=dice_min_rev
    )
