#!/usr/bin/env python3
"""
Deployment-ready Flask application for PythonAnywhere
Enhanced error handling and graceful degradation for missing dependencies
"""

import os
import sys
import logging
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from flask import Flask, request, jsonify, render_template, redirect, url_for
    from werkzeug.exceptions import HTTPException
except ImportError as e:
    logger.error(f"Flask import error: {str(e)}")
    raise

# Optional imports with graceful fallbacks
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    logger.warning("Flask-Limiter not available. Rate limiting disabled.")
    LIMITER_AVAILABLE = False

try:
    from flask_caching import Cache
    CACHING_AVAILABLE = True
except ImportError:
    logger.warning("Flask-Caching not available. Caching disabled.")
    CACHING_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
except ImportError:
    logger.warning("python-dotenv not available. Environment variables from system only.")
    DOTENV_AVAILABLE = False

# Import our modules with error handling
try:
    from pykes.config import get_config
except ImportError:
    logger.warning("Config module not found. Using default configuration.")
    get_config = None

try:
    from pykes.models import init_db, DatabaseError, get_database_stats
except ImportError as e:
    logger.error(f"Models import error: {str(e)}")
    raise

try:
    from pykes.routes import init_routes
except ImportError:
    logger.warning("Routes module not found. Basic routing only.")
    init_routes = None

try:
    from pykes.logging_config import setup_logging, log_security_event
except ImportError:
    logger.warning("Logging config not found. Using basic logging.")
    setup_logging = None
    log_security_event = None

try:
    from pykes.utils import cleanup_old_files
except ImportError:
    logger.warning("Utils module not found. Cleanup disabled.")
    cleanup_old_files = None

# Import blueprints with error handling
try:
    from app_reports import reports_bp
    REPORTS_BP_AVAILABLE = True
except ImportError:
    logger.warning("Reports blueprint not available")
    REPORTS_BP_AVAILABLE = False

try:
    from app_admin import admin_bp
    ADMIN_BP_AVAILABLE = True
except ImportError:
    logger.warning("Admin blueprint not available")
    ADMIN_BP_AVAILABLE = False

class SimpleConfig:
    """Fallback configuration class"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production-' + str(os.urandom(16).hex()))
    # SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    TESTING = False
    LOG_LEVEL = 'INFO'
    RATELIMIT_ENABLED = False
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file upload

    # Session configuration for better reliability
    SESSION_COOKIE_SECURE = False  # Set to True if using HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    @staticmethod
    def init_app(app):
        # pass
         # Configure session settings
        app.config['SESSION_COOKIE_SECURE'] = SimpleConfig.SESSION_COOKIE_SECURE
        app.config['SESSION_COOKIE_HTTPONLY'] = SimpleConfig.SESSION_COOKIE_HTTPONLY
        app.config['SESSION_COOKIE_SAMESITE'] = SimpleConfig.SESSION_COOKIE_SAMESITE
        app.config['SESSION_PERMANENT'] = SimpleConfig.SESSION_PERMANENT
        app.config['PERMANENT_SESSION_LIFETIME'] = SimpleConfig.PERMANENT_SESSION_LIFETIME

def create_app(config_name=None):
    """Application factory pattern for creating Flask app with better error handling"""

    # Create Flask app
    app = Flask(__name__)

    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    try:
        if get_config:
            config_class = get_config()
        else:
            config_class = SimpleConfig()

        app.config.from_object(config_class)
    except Exception as e:
        logger.error(f"Configuration error: {str(e)}")
        app.config.from_object(SimpleConfig())

    # Initialize logging
    if setup_logging:
        try:
            logger_instance = setup_logging(
                app,
                log_level=getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper()),
                enable_json=app.config.get('ENABLE_JSON_LOGGING', False)
            )
        except Exception as e:
            logger.error(f"Logging setup error: {str(e)}")

    # Initialize configuration
    try:
        config_class.init_app(app)
    except Exception as e:
        logger.error(f"Config initialization error: {str(e)}")

    # Initialize extensions with fallbacks
    init_extensions(app)

    # Initialize database with better error handling
    try:
        init_db()
        logger.info("Database initialized successfully")
    except DatabaseError as e:
        logger.error(f"Database initialization failed: {str(e)}")
        # Don't crash the app, but log the error
        app.config['DATABASE_ERROR'] = str(e)
    except Exception as e:
        logger.error(f"Unexpected database error: {str(e)}")
        app.config['DATABASE_ERROR'] = str(e)

    # Register error handlers
    register_error_handlers(app)

    # Register request hooks
    register_request_hooks(app)

    # Register blueprints
    register_blueprints(app)

    # Initialize routes (legacy support)
    if init_routes:
        try:
            init_routes(app)
        except Exception as e:
            logger.error(f"Routes initialization error: {str(e)}")

    # Health check endpoint
    register_health_check(app)

    # Add database error page route
    register_database_error_route(app)

    logger.info(f"Application created successfully in {config_name} mode")
    return app

def init_extensions(app):
    """Initialize Flask extensions with graceful fallbacks"""

    # Rate limiting
    if LIMITER_AVAILABLE and app.config.get('RATELIMIT_ENABLED', True):
        try:
            limiter = Limiter(
                key_func=get_remote_address,
                default_limits=[app.config.get('RATELIMIT_DEFAULT', '1000 per hour')],
                storage_uri=app.config.get('RATELIMIT_STORAGE_URL', 'memory://')
            )
            limiter.init_app(app)
            app.limiter = limiter
            logger.info("Rate limiting initialized")
        except Exception as e:
            logger.warning(f"Rate limiting initialization failed: {str(e)}")

    # Caching
    if CACHING_AVAILABLE:
        try:
            cache = Cache(app, config={
                'CACHE_TYPE': app.config.get('CACHE_TYPE', 'simple'),
                'CACHE_DEFAULT_TIMEOUT': app.config.get('CACHE_DEFAULT_TIMEOUT', 300)
            })
            app.cache = cache
            logger.info("Caching initialized")
        except Exception as e:
            logger.warning(f"Caching initialization failed: {str(e)}")

def register_error_handlers(app):
    """Register comprehensive error handlers"""

    @app.errorhandler(400)
    def bad_request(error):
        app.logger.warning(f"Bad request: {request.url} - {str(error)}")
        if request.is_json:
            return jsonify({
                'error': 'Bad Request',
                'message': 'The request was invalid or malformed',
                'status_code': 400
            }), 400
        try:
            return render_template('errors/400.html'), 400
        except:
            return "Bad Request", 400

    @app.errorhandler(401)
    def unauthorized(error):
        if log_security_event:
            log_security_event('UNAUTHORIZED_ACCESS', details={'url': request.url, 'ip': request.remote_addr})
        if request.is_json:
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Authentication is required',
                'status_code': 401
            }), 401
        try:
            return render_template('errors/401.html'), 401
        except:
            return "Unauthorized", 401

    @app.errorhandler(403)
    def forbidden(error):
        if log_security_event:
            log_security_event('FORBIDDEN_ACCESS', details={'url': request.url, 'ip': request.remote_addr})
        if request.is_json:
            return jsonify({
                'error': 'Forbidden',
                'message': 'You do not have permission to access this resource',
                'status_code': 403
            }), 403
        try:
            return render_template('errors/403.html'), 403
        except:
            return "Forbidden", 403

    @app.errorhandler(404)
    def not_found(error):
        app.logger.info(f"404 error: {request.url}")
        if request.is_json:
            return jsonify({
                'error': 'Not Found',
                'message': 'The requested resource was not found',
                'status_code': 404
            }), 404
        try:
            return render_template('errors/404.html'), 404
        except:
            return "Not Found", 404

    @app.errorhandler(413)
    def request_entity_too_large(error):
        app.logger.warning(f"File too large: {request.url}")
        if request.is_json:
            return jsonify({
                'error': 'Request Entity Too Large',
                'message': 'The uploaded file is too large',
                'status_code': 413
            }), 413
        try:
            return render_template('errors/413.html'), 413
        except:
            return "File Too Large", 413

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        app.logger.warning(f"Rate limit exceeded: {request.remote_addr} - {request.url}")
        if request.is_json:
            return jsonify({
                'error': 'Rate Limit Exceeded',
                'message': 'Too many requests. Please try again later.',
                'status_code': 429
            }), 429
        try:
            return render_template('errors/429.html'), 429
        except:
            return "Rate Limit Exceeded", 429

    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error(f"Internal server error: {str(error)}")
        if request.is_json:
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred',
                'status_code': 500
            }), 500
        try:
            return render_template('errors/500.html'), 500
        except:
            return "Internal Server Error", 500

    @app.errorhandler(DatabaseError)
    def database_error(error):
        app.logger.error(f"Database error: {str(error)}")
        if request.is_json:
            return jsonify({
                'error': 'Database Error',
                'message': 'A database error occurred. Please contact support.',
                'status_code': 500
            }), 500
        try:
            return render_template('errors/database_error.html', error=str(error)), 500
        except:
            return f"Database Error: {str(error)}", 500

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        app.logger.warning(f"HTTP exception: {error.code} - {request.url}")
        if request.is_json:
            return jsonify({
                'error': error.name,
                'message': error.description,
                'status_code': error.code
            }), error.code
        try:
            return render_template(f'errors/{error.code}.html'), error.code
        except:
            return f"{error.name}: {error.description}", error.code

def register_request_hooks(app):
    """Register request processing hooks"""

    @app.before_request
    def before_request():
        """Pre-request processing"""
        try:
            # Log request details in debug mode
            if app.debug:
                app.logger.debug(f"Request: {request.method} {request.url}")
        except Exception as e:
            app.logger.error(f"Before request hook error: {str(e)}")

    @app.after_request
    def after_request(response):
        """Post-request processing"""
        try:
            # Add security headers
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'

            return response
        except Exception as e:
            app.logger.error(f"After request hook error: {str(e)}")
            return response

def register_blueprints(app):
    """Register application blueprints with error handling"""

    if REPORTS_BP_AVAILABLE:
        try:
            app.register_blueprint(reports_bp, url_prefix='/reports')
            logger.info("Reports blueprint registered")
        except Exception as e:
            logger.error(f"Failed to register reports blueprint: {str(e)}")

    if ADMIN_BP_AVAILABLE:
        try:
            app.register_blueprint(admin_bp, url_prefix='/admin')
            logger.info("Admin blueprint registered")
        except Exception as e:
            logger.error(f"Failed to register admin blueprint: {str(e)}")

def register_health_check(app):
    """Register health check endpoint"""

    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        try:
            # Basic health checks
            health_status = {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'version': '1.0.0'
            }

            # Check database
            try:
                stats = get_database_stats()
                health_status['database'] = 'connected'
                health_status['stats'] = stats
            except Exception as e:
                health_status['database'] = 'error'
                health_status['database_error'] = str(e)
                health_status['status'] = 'degraded'

            # Check if there are database errors from initialization
            if app.config.get('DATABASE_ERROR'):
                health_status['status'] = 'degraded'
                health_status['database_init_error'] = app.config['DATABASE_ERROR']

            return jsonify(health_status)

        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500

def register_database_error_route(app):
    """Register route for database error page"""

    @app.route('/database-error')
    def database_error_page():
        """Show database error information"""
        db_error = app.config.get('DATABASE_ERROR', 'Unknown database error')

        try:
            return render_template('errors/database_error.html', error=db_error)
        except:
            return f"""
            <html>
            <head><title>Database Error</title></head>
            <body>
                <h1>Database Error</h1>
                <p>There was an error initializing the database:</p>
                <pre>{db_error}</pre>
                <p>Please contact the administrator.</p>
                <a href="/">Return to Home</a>
            </body>
            </html>
            """, 500

# Basic routes for testing
def add_basic_routes(app):
    """Add basic routes for testing, avoiding endpoint conflicts"""
    # Check if 'index' endpoint already exists
    if 'index' not in [rule.endpoint for rule in app.url_map.iter_rules()]:
        @app.route('/')
        def index():
            """Home page with database status"""
            try:
                # Check if there's a database error
                if app.config.get('DATABASE_ERROR'):
                    return redirect(url_for('database_error_page'))
                # Try to render the main template
                try:
                    return render_template('index.html')
                except Exception as template_error:
                    logger.warning(f"Template error: {str(template_error)}")
                    # Fallback to simple HTML
                    return """
                    <html>
                    <head><title>SurveyTray - POSM Retail Activation</title></head>
                    <body>
                        <h1>SurveyTray</h1>
                        <p>POSM Retail Activation System</p>
                        <p>Application is running. Template system loading...</p>
                        <a href="/health">Health Check</a>
                    </body>
                    </html>
                    """
            except Exception as e:
                logger.error(f"Index route error: {str(e)}")
                return f"Application Error: {str(e)}", 500
    else:
        logger.info("Skipping basic index route registration as 'index' endpoint already exists")

    @app.route('/test')
    def test():
        """Simple test endpoint"""
        return jsonify({
            'message': 'Application is running',
            'timestamp': datetime.now().isoformat(),
            'python_version': sys.version,
            'flask_available': True,
            'limiter_available': LIMITER_AVAILABLE,
            'caching_available': CACHING_AVAILABLE
        })

# Create the application
try:
    app = create_app()
    add_basic_routes(app)

    # For PythonAnywhere compatibility
    application = app

    logger.info("Flask application created successfully")

except Exception as e:
    logger.error(f"Failed to create Flask application: {str(e)}")
    # Create a minimal app that shows the error
    app = Flask(__name__)

    @app.route('/')
    def error_page():
        return f"""
        <html>
        <head><title>Application Error</title></head>
        <body>
            <h1>Application Startup Error</h1>
            <p>There was an error starting the application:</p>
            <pre>{str(e)}</pre>
            <p>Please check the server logs for more details.</p>
        </body>
        </html>
        """, 500

    application = app

# For direct running
if __name__ == "__main__":
    try:
        # Import datetime here since we use it in routes
        from datetime import datetime

        port = int(os.environ.get('PORT', 5000))
        debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

        logger.info(f"Starting application on port {port}, debug={debug}")
        app.run(host='0.0.0.0', port=port, debug=debug)

    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        print(f"Failed to start: {str(e)}")
