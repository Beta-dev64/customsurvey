#!/usr/bin/env python3
# app.py - Main Flask application with enhanced error handling and modular structure

import os
import logging
from flask import Flask, request, jsonify, render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our modules
from pykes.config import get_config
from pykes.models import init_db, DatabaseError, get_database_stats
from pykes.routes import init_routes
from pykes.logging_config import setup_logging, log_security_event
from pykes.utils import cleanup_old_files

# Import blueprints
from app_reports import reports_bp
from app_admin import admin_bp

def create_app(config_name=None):
    """Application factory pattern for creating Flask app"""
    
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    config_class = get_config()
    app.config.from_object(config_class)
    
    # Initialize logging first
    logger = setup_logging(
        app, 
        log_level=getattr(logging, app.config['LOG_LEVEL'].upper()),
        enable_json=app.config.get('ENABLE_JSON_LOGGING', False)
    )
    
    # Initialize configuration
    config_class.init_app(app)
    
    # Initialize extensions
    init_extensions(app)
    
    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except DatabaseError as e:
        logger.error(f"Database initialization failed: {str(e)}")
        if not app.config['TESTING']:
            raise
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register request hooks
    register_request_hooks(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Initialize routes (legacy support)
    init_routes(app)
    
    # Register CLI commands
    register_cli_commands(app)
    
    # Health check endpoint
    register_health_check(app)
    
    logger.info(f"Application created successfully in {config_name} mode")
    return app

def init_extensions(app):
    """Initialize Flask extensions"""
    
    # Rate limiting
    if app.config.get('RATELIMIT_ENABLED', True):
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=[app.config.get('RATELIMIT_DEFAULT', '1000 per hour')],
            storage_uri=app.config.get('RATELIMIT_STORAGE_URL', 'memory://')
        )
        limiter.init_app(app)
        app.limiter = limiter
    
    # Caching
    cache = Cache(app, config={
        'CACHE_TYPE': app.config.get('CACHE_TYPE', 'simple'),
        'CACHE_DEFAULT_TIMEOUT': app.config.get('CACHE_DEFAULT_TIMEOUT', 300)
    })
    app.cache = cache

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
        return render_template('errors/400.html'), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        log_security_event('UNAUTHORIZED_ACCESS', details={'url': request.url, 'ip': request.remote_addr})
        if request.is_json:
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Authentication is required',
                'status_code': 401
            }), 401
        return render_template('errors/401.html'), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        log_security_event('FORBIDDEN_ACCESS', details={'url': request.url, 'ip': request.remote_addr})
        if request.is_json:
            return jsonify({
                'error': 'Forbidden',
                'message': 'You do not have permission to access this resource',
                'status_code': 403
            }), 403
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(404)
    def not_found(error):
        app.logger.info(f"404 error: {request.url}")
        if request.is_json:
            return jsonify({
                'error': 'Not Found',
                'message': 'The requested resource was not found',
                'status_code': 404
            }), 404
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        app.logger.warning(f"File too large: {request.url}")
        if request.is_json:
            return jsonify({
                'error': 'Request Entity Too Large',
                'message': 'The uploaded file is too large',
                'status_code': 413
            }), 413
        return render_template('errors/413.html'), 413
    
    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        app.logger.warning(f"Rate limit exceeded: {request.remote_addr} - {request.url}")
        if request.is_json:
            return jsonify({
                'error': 'Rate Limit Exceeded',
                'message': 'Too many requests. Please try again later.',
                'status_code': 429
            }), 429
        return render_template('errors/429.html'), 429
    
    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error(f"Internal server error: {str(error)}")
        if request.is_json:
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred',
                'status_code': 500
            }), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(DatabaseError)
    def database_error(error):
        app.logger.error(f"Database error: {str(error)}")
        if request.is_json:
            return jsonify({
                'error': 'Database Error',
                'message': 'A database error occurred',
                'status_code': 500
            }), 500
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        app.logger.warning(f"HTTP exception: {error.code} - {request.url}")
        if request.is_json:
            return jsonify({
                'error': error.name,
                'message': error.description,
                'status_code': error.code
            }), error.code
        return render_template(f'errors/{error.code}.html'), error.code
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.error(f"Unexpected error: {str(error)}", exc_info=True)
        if request.is_json:
            return jsonify({
                'error': 'Unexpected Error',
                'message': 'An unexpected error occurred',
                'status_code': 500
            }), 500
        return render_template('errors/500.html'), 500

def register_request_hooks(app):
    """Register request lifecycle hooks"""
    
    @app.before_request
    def before_request():
        """Execute before each request"""
        # Log request details
        app.logger.debug(f"Request: {request.method} {request.url} from {request.remote_addr}")
        
        # Add request ID for tracking
        import uuid
        request.id = str(uuid.uuid4())[:8]
    
    @app.after_request
    def after_request(response):
        """Execute after each request"""
        # Log response details
        app.logger.debug(f"Response: {response.status_code} for {request.method} {request.url}")
        
        # Add custom headers
        response.headers['X-Request-ID'] = getattr(request, 'id', 'unknown')
        
        return response
    
    @app.teardown_appcontext
    def teardown_db(exception):
        """Clean up after request"""
        if exception:
            app.logger.error(f"Request teardown with exception: {str(exception)}")

def register_blueprints(app):
    """Register application blueprints"""
    
    try:
        # Register admin blueprint
        app.register_blueprint(admin_bp)
        app.logger.info("Admin blueprint registered")
        
        # Register reports blueprint
        app.register_blueprint(reports_bp)
        app.logger.info("Reports blueprint registered")
        
    except Exception as e:
        app.logger.error(f"Error registering blueprints: {str(e)}")
        raise

def register_cli_commands(app):
    """Register CLI commands for maintenance"""
    
    @app.cli.command('init-db')
    def init_db_command():
        """Initialize the database"""
        try:
            init_db()
            print("Database initialized successfully")
        except Exception as e:
            print(f"Database initialization failed: {str(e)}")
    
    @app.cli.command('cleanup-files')
    def cleanup_files_command():
        """Clean up old uploaded files"""
        try:
            deleted_count = cleanup_old_files()
            print(f"Cleaned up {deleted_count} old files")
        except Exception as e:
            print(f"File cleanup failed: {str(e)}")
    
    @app.cli.command('db-stats')
    def db_stats_command():
        """Show database statistics"""
        try:
            stats = get_database_stats()
            print("Database Statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
        except Exception as e:
            print(f"Error getting database stats: {str(e)}")

def register_health_check(app):
    """Register health check endpoint"""
    
    @app.route('/health')
    def health_check():
        """Application health check endpoint"""
        try:
            # Check database connectivity
            stats = get_database_stats()
            
            health_status = {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'version': '1.0.0',
                'database': {
                    'connected': True,
                    'tables': stats.get('users_count', 0) > 0
                },
                'services': {
                    'uploads': os.path.exists(app.config['UPLOAD_FOLDER']),
                    'logs': os.path.exists('logs')
                }
            }
            
            return jsonify(health_status), 200
            
        except Exception as e:
            app.logger.error(f"Health check failed: {str(e)}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500
    
    @app.route('/health/ready')
    def readiness_check():
        """Readiness check for load balancers"""
        try:
            # More comprehensive checks for readiness
            stats = get_database_stats()
            
            if stats.get('users_count', 0) == 0:
                return jsonify({
                    'status': 'not_ready',
                    'reason': 'Database not initialized'
                }), 503
            
            return jsonify({'status': 'ready'}), 200
            
        except Exception as e:
            return jsonify({
                'status': 'not_ready',
                'error': str(e)
            }), 503

# Create the application instance
app = create_app()

if __name__ == '__main__':
    # Import datetime for health checks
    from datetime import datetime
    
    # Get configuration
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    app.logger.info(f"Starting application on {host}:{port} (debug={debug})")
    
    try:
        app.run(host=host, port=port, debug=debug)
    except Exception as e:
        app.logger.error(f"Failed to start application: {str(e)}")
        raise
