# Routes Package Initialization
from routes.dashboard import dashboard_bp
from routes.data_routes import data_bp
from routes.etl_routes import etl_bp
from routes.olap_routes import olap_bp
from routes.mining_routes import mining_bp

__all__ = [
    'dashboard_bp',
    'data_bp',
    'etl_bp',
    'olap_bp',
    'mining_bp'
]
