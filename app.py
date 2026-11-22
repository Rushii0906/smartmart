"""SmartMart Analytics - Main Flask Application Entry Point

Full Stack Integration:
- Star Schema Dimensional Data Warehouse (MySQL)
- ETL Pipeline (Extract, Transform, Load)
- OLAP Engine (Roll-up, Drill-down, Slice, Dice)
- Data Mining Modules (Apriori, K-Means RFM, Decision Tree Classifier)
- Bootstrap 5 & Chart.js Analytical Frontend
"""

import os
from flask import Flask, jsonify, render_template
from config import Config
from database import db
from database.db_connection import test_connection_diagnostics, create_database_if_not_exists

# Import Blueprints
from routes.dashboard import dashboard_bp
from routes.data_routes import data_bp
from routes.etl_routes import etl_bp
from routes.olap_routes import olap_bp
from routes.mining_routes import mining_bp


def create_app(config_class=Config):
    """Application factory to create and configure the Flask app."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure required data folders exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

    # Initialize SQLAlchemy extension
    db.init_app(app)

    # Register Blueprints
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(etl_bp)
    app.register_blueprint(olap_bp)
    app.register_blueprint(mining_bp)

    # System Health Diagnostic Route
    @app.route('/health')
    def health():
        diag = test_connection_diagnostics()
        status_code = 200 if diag['server_connected'] else 503
        return jsonify(diag), status_code

    # Global Error Handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template(
            'error.html',
            error_code=404,
            error_msg="The requested analytics page or resource could not be found."
        ), 404

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return render_template(
            'error.html',
            error_code=413,
            error_msg="The uploaded dataset exceeds the maximum allowable limit of 32 MB."
        ), 413

    @app.errorhandler(500)
    def internal_error(error):
        return render_template(
            'error.html',
            error_code=500,
            error_msg="An internal server error occurred while processing the analytics operation."
        ), 500

    return app


# Application instance
app = create_app()

if __name__ == '__main__':
    create_database_if_not_exists()
    port = int(os.getenv('PORT', 5000))
    debug = Config.DEBUG
    app.run(host='0.0.0.0', port=port, debug=debug)
