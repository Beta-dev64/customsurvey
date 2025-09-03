# pykes/config.py
import os
import secrets
from datetime import timedelta
from pathlib import Path

class Config:
    """Base configuration class"""
    
    # Application settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Database settings (Windows compatible paths)
    DB_PATH = os.environ.get('DB_PATH') or os.path.join(os.getcwd(), 'maindatabase.db')
    DATABASE_URL = os.environ.get('DATABASE_URL') or f'sqlite:///{DB_PATH.replace(chr(92), "/")}'  # Convert Windows backslashes
    
    # File upload settings (Windows compatible paths)
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(os.getcwd(), 'static', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'csv', 'xlsx', 'xls'}  # Added Excel/CSV support
    
    # Session settings
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.environ.get('SESSION_LIFETIME_HOURS', 8)))
    
    # Security settings
    WTF_CSRF_ENABLED = os.environ.get('WTF_CSRF_ENABLED', 'True').lower() == 'true'
    WTF_CSRF_TIME_LIMIT = int(os.environ.get('WTF_CSRF_TIME_LIMIT', 3600))
    
    # Logging settings
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    ENABLE_JSON_LOGGING = os.environ.get('ENABLE_JSON_LOGGING', 'False').lower() == 'true'
    
    # Application limits and performance
    PAGINATION_PER_PAGE = int(os.environ.get('PAGINATION_PER_PAGE', 20))
    MAX_PAGINATION_PER_PAGE = int(os.environ.get('MAX_PAGINATION_PER_PAGE', 1000))
    DEFAULT_EXPORT_PER_PAGE = int(os.environ.get('DEFAULT_EXPORT_PER_PAGE', 1000))
    
    # Image processing settings
    IMAGE_QUALITY = int(os.environ.get('IMAGE_QUALITY', 85))
    THUMBNAIL_SIZE = tuple(map(int, os.environ.get('THUMBNAIL_SIZE', '200,200').split(',')))
    MAX_IMAGE_SIZE = tuple(map(int, os.environ.get('MAX_IMAGE_SIZE', '1920,1080').split(',')))
    
    # Cache settings
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'simple')
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', 300))
    
    # Rate limiting
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'True').lower() == 'true'
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '1000 per hour')
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
    
    @staticmethod
    def init_app(app):
        """Initialize application with configuration"""
        # Ensure upload directory exists
        upload_path = Path(app.config['UPLOAD_FOLDER'])
        upload_path.mkdir(parents=True, exist_ok=True)
        
        # Set secure headers
        @app.after_request
        def security_headers(response):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            if app.config['SESSION_COOKIE_SECURE']:
                response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            return response

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    WTF_CSRF_ENABLED = False  # Disable CSRF for development
    SESSION_COOKIE_SECURE = False
    
    # More verbose logging in development
    LOG_LEVEL = 'DEBUG'
    
class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Security settings for production
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_ENABLED = True
    
    # Production optimizations
    LOG_LEVEL = 'INFO'
    ENABLE_JSON_LOGGING = True
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Log to syslog in production if available
        import logging
        from logging.handlers import SysLogHandler
        
        try:
            syslog_handler = SysLogHandler()
            syslog_handler.setLevel(logging.WARNING)
            app.logger.addHandler(syslog_handler)
        except Exception:
            pass  # Syslog not available

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    
    # Use in-memory database for testing
    DB_PATH = ':memory:'
    DATABASE_URL = 'sqlite:///:memory:'
    
    # Disable rate limiting in tests
    RATELIMIT_ENABLED = False
    
    # Use temporary upload folder for tests
    UPLOAD_FOLDER = 'tests/temp_uploads'
    
    LOG_LEVEL = 'DEBUG'

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development').lower()
    return config.get(env, config['default'])
