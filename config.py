import os
from urllib.parse import quote_plus, urlparse
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load environment variables from .env file
load_dotenv(os.path.join(BASE_DIR, '.env'))


class Config:
    """Application configuration class reading from environment variables."""
    
    BASE_DIR = BASE_DIR
    
    # Environment & Debug
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    DEBUG = os.getenv('FLASK_DEBUG', '0').lower() in ('1', 'true', 'yes')
    TESTING = False

    # Secret Key for session management and CSRF protection
    SECRET_KEY = os.getenv('SECRET_KEY', 'smartmart-analytics-production-key-change-in-env')

    # Session & Cookie Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('1', 'true', 'yes')

    # Database Configuration (supports both explicit params and standard DATABASE_URL)
    raw_db_url = os.getenv('DATABASE_URL')
    if raw_db_url:
        # Standardize prefix for SQLAlchemy with PyMySQL driver
        if raw_db_url.startswith('mysql://'):
            SQLALCHEMY_DATABASE_URI = raw_db_url.replace('mysql://', 'mysql+pymysql://', 1)
        elif not raw_db_url.startswith('mysql+pymysql://'):
            SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{raw_db_url.split('://', 1)[-1]}"
        else:
            SQLALCHEMY_DATABASE_URI = raw_db_url

        parsed = urlparse(raw_db_url)
        DB_USER = parsed.username or 'root'
        DB_PASSWORD = parsed.password or ''
        DB_HOST = parsed.hostname or 'localhost'
        DB_PORT = str(parsed.port or 3306)
        DB_NAME = parsed.path.lstrip('/') or 'smartmart_dw'
    else:
        DB_USER = os.getenv('DB_USER', 'root')
        DB_PASSWORD = os.getenv('DB_PASSWORD', '')
        DB_HOST = os.getenv('DB_HOST', 'localhost')
        DB_PORT = os.getenv('DB_PORT', '3306')
        DB_NAME = os.getenv('DB_NAME', 'smartmart_dw')

        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            f"?charset=utf8mb4"
        )
    
    # SQLAlchemy Connection Options
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_timeout': 20,
        'pool_pre_ping': True
    }

    # File Upload and Processing Paths
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'data', 'raw')
    PROCESSED_FOLDER = os.path.join(BASE_DIR, 'data', 'processed')
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32 MB max upload limit
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
