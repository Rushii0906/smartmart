/**
 * SmartMart Analytics - Dashboard and Chart.js Initialization Script
 */

// Global Loading Overlay functions
function showLoading(msg = 'Processing data warehouse operation...') {
    const overlay = document.getElementById('loading-overlay');
    const msgEl = document.getElementById('loading-message');
    if (msgEl) msgEl.innerText = msg;
    if (overlay) overlay.style.display = 'flex';
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.style.display = 'none';
}

// Chart.js Color Palette
const ChartColors = {
    primary: '#6366f1',
    primaryLight: 'rgba(99, 102, 241, 0.15)',
    secondary: '#0ea5e9',
    success: '#10b981',
    amber: '#f59e0b',
    rose: '#f43f5e',
    violet: '#8b5cf6',
    palette: ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6', '#f97316']
};

/**
 * Initializes a responsive Line Chart for chronological sales data.
 */
function createLineChart(canvasId, labels, data, label = 'Revenue ($)') {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const ctx = canvas.getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                borderColor: ChartColors.primary,
                backgroundColor: ChartColors.primaryLight,
                borderWidth: 2.5,
                fill: true,
                tension: 0.35,
                pointBackgroundColor: ChartColors.primary,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return `${label}: $${context.raw.toLocaleString()}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { font: { size: 11 } }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: '#f1f5f9' },
                    ticks: {
                        callback: function (val) {
                            return '$' + (val >= 1000 ? (val / 1000).toFixed(0) + 'k' : val);
                        }
                    }
                }
            }
        }
    });
}

/**
 * Initializes a Bar Chart (Vertical or Horizontal).
 */
function createBarChart(canvasId, labels, data, label = 'Revenue ($)', isHorizontal = false) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const ctx = canvas.getContext('2d');
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                backgroundColor: isHorizontal ? ChartColors.secondary : ChartColors.primary,
                borderRadius: 6
            }]
        },
        options: {
            indexAxis: isHorizontal ? 'y' : 'x',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return `${label}: $${context.raw.toLocaleString()}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: '#f8fafc' },
                    ticks: { font: { size: 11 } }
                },
                y: {
                    grid: { display: isHorizontal },
                    ticks: { font: { size: 11 } }
                }
            }
        }
    });
}

/**
 * Initializes a Doughnut Chart for cluster or category distributions.
 */
function createDoughnutChart(canvasId, labels, data) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const ctx = canvas.getContext('2d');
    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: ChartColors.palette.slice(0, labels.length),
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { boxWidth: 12, font: { size: 11 } }
                }
            },
            cutout: '68%'
        }
    });
}

/**
 * Initializes a Scatter Chart for Customer RFM Segmentation.
 */
function createScatterChart(canvasId, points) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    // Group points by cluster label
    const clusterGroups = {};
    points.forEach(pt => {
        if (!clusterGroups[pt.label]) {
            clusterGroups[pt.label] = [];
        }
        clusterGroups[pt.label].push({ x: pt.x, y: pt.y, customer_code: pt.customer_code });
    });

    const datasets = Object.keys(clusterGroups).map((label, idx) => ({
        label: label,
        data: clusterGroups[label],
        backgroundColor: ChartColors.palette[idx % ChartColors.palette.length],
        pointRadius: 5,
        pointHoverRadius: 7
    }));

    const ctx = canvas.getContext('2d');
    return new Chart(ctx, {
        type: 'scatter',
        data: { datasets: datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            const raw = ctx.raw;
                            return `Customer ${raw.customer_code} | Recency: ${raw.x} days | Spend: $${raw.y.toLocaleString()}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Recency (Days since last purchase)' },
                    grid: { color: '#f8fafc' }
                },
                y: {
                    title: { display: true, text: 'Monetary ($ Lifetime Expenditure)' },
                    grid: { color: '#f1f5f9' },
                    ticks: {
                        callback: function (val) {
                            return '$' + val.toLocaleString();
                        }
                    }
                }
            }
        }
    });
}

// Auto-bind loading spinner to forms with class 'form-with-loading'
document.addEventListener('DOMContentLoaded', function () {
    const forms = document.querySelectorAll('form.form-with-loading');
    forms.forEach(form => {
        form.addEventListener('submit', function () {
            const msg = form.getAttribute('data-loading-message') || 'Processing analytics query...';
            showLoading(msg);
        });
    });
});
