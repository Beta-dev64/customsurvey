import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import sys
import traceback
from datetime import datetime, timezone
from functools import wraps
import json

class CustomFormatter(logging.Formatter):
    """Custom formatter with color coding for console output"""
    
    COLORS = {
        logging.DEBUG: '\033[36m',     # Cyan
        logging.INFO: '\033[32m',      # Green
        logging.WARNING: '\033[33m',   # Yellow
        logging.ERROR: '\033[31m',     # Red
        logging.CRITICAL: '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        if hasattr(record, 'request_id'):
            record.msg = f"[{record.request_id}] {record.msg}"
        
        log_color = self.COLORS.get(record.levelno, '')
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)

class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_record = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
            'thread': record.thread,
            'process': record.process
        }
        
        # Add extra fields if available
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        if hasattr(record, 'execution_id'):
            log_record['execution_id'] = record.execution_id
        if hasattr(record, 'outlet_id'):
            log_record['outlet_id'] = record.outlet_id
        
        # Add exception info if present
        if record.exc_info:
            log_record['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_record, default=str)

def setup_logging(app, log_level=logging.INFO, enable_json=False):
    """
    Configure comprehensive application logging
    
    Args:
        app: Flask application instance
        log_level: Logging level (default: INFO)
        enable_json: Enable JSON structured logging (default: False)
    """
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir, mode=0o755)
    
    # Set up formatters
    console_formatter = CustomFormatter(
        '[%(asctime)s] %(levelname)s in %(module)s.%(funcName)s:%(lineno)d: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] [%(module)s.%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # JSON formatter for structured logs
    json_formatter = StructuredFormatter() if enable_json else file_formatter
    
    # Configure Flask app logger
    app.logger.setLevel(log_level)
    
    # Clear existing handlers to avoid duplicate logs
    if app.logger.handlers:
        app.logger.handlers.clear()
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)
    app.logger.addHandler(console_handler)
    
    # Daily rotating file handler - main application log
    app_log_file = os.path.join(logs_dir, 'application.log')
    app_file_handler = TimedRotatingFileHandler(
        app_log_file,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    app_file_handler.setFormatter(file_formatter)
    app_file_handler.setLevel(log_level)
    app.logger.addHandler(app_file_handler)
    
    # Error log - separate file for errors and above
    error_log_file = os.path.join(logs_dir, 'errors.log')
    error_file_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=52428800,  # 50MB
        backupCount=10,
        encoding='utf-8'
    )
    error_file_handler.setFormatter(file_formatter)
    error_file_handler.setLevel(logging.ERROR)
    app.logger.addHandler(error_file_handler)
    
    # Execution tracking log for visits/executions
    execution_log_file = os.path.join(logs_dir, 'executions.log')
    execution_file_handler = RotatingFileHandler(
        execution_log_file,
        maxBytes=20971520,  # 20MB
        backupCount=5,
        encoding='utf-8'
    )
    execution_file_handler.setFormatter(json_formatter)
    execution_file_handler.setLevel(logging.INFO)
    
    # Create execution logger
    execution_logger = logging.getLogger('execution_tracker')
    execution_logger.setLevel(logging.INFO)
    execution_logger.addHandler(execution_file_handler)
    
    # Security log for authentication and authorization events
    security_log_file = os.path.join(logs_dir, 'security.log')
    security_file_handler = RotatingFileHandler(
        security_log_file,
        maxBytes=10485760,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    security_file_handler.setFormatter(json_formatter)
    security_file_handler.setLevel(logging.INFO)
    
    # Create security logger
    security_logger = logging.getLogger('security')
    security_logger.setLevel(logging.INFO)
    security_logger.addHandler(security_file_handler)
    
    # Database operations log
    db_log_file = os.path.join(logs_dir, 'database.log')
    db_file_handler = RotatingFileHandler(
        db_log_file,
        maxBytes=10485760,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    db_file_handler.setFormatter(file_formatter)
    db_file_handler.setLevel(logging.INFO)
    
    # Create database logger
    db_logger = logging.getLogger('database')
    db_logger.setLevel(logging.INFO)
    db_logger.addHandler(db_file_handler)
    
    # Configure root logger to catch all other logs
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Prevent duplicate logs from other loggers
    app.logger.propagate = False
    execution_logger.propagate = False
    security_logger.propagate = False
    db_logger.propagate = False
    
    # Log startup message
    app.logger.info('Comprehensive logging system initialized')
    app.logger.info(f'Log directory: {logs_dir}')
    app.logger.info(f'Log level: {logging.getLevelName(log_level)}')
    app.logger.info(f'JSON logging: {enable_json}')
    
    return app.logger

def log_execution(func):
    """Decorator to log execution tracking operations"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger('execution_tracker')
        start_time = datetime.now()
        
        try:
            result = func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info('Execution operation completed', extra={
                'function': func.__name__,
                'duration_seconds': duration,
                'success': True
            })
            
            return result
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.error('Execution operation failed', extra={
                'function': func.__name__,
                'duration_seconds': duration,
                'error': str(e),
                'success': False
            }, exc_info=True)
            
            raise
    
    return wrapper

def log_security_event(event_type, user_id=None, details=None):
    """Log security events like login attempts, access denied, etc."""
    logger = logging.getLogger('security')
    
    logger.info(f'Security event: {event_type}', extra={
        'event_type': event_type,
        'user_id': user_id,
        'details': details or {},
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

def log_database_operation(operation, table, details=None):
    """Log database operations"""
    logger = logging.getLogger('database')
    
    logger.info(f'Database {operation} on {table}', extra={
        'operation': operation,
        'table': table,
        'details': details or {}
    })
