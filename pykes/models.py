# pykes/models.py
import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, Dict, List, Any, Tuple, Union
from pathlib import Path
import json
import threading
from .logging_config import log_database_operation

# Configure logger
logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = 'maindatabase.db'
UPLOAD_FOLDER = 'static/uploads'

# Thread-local storage for database connections
_local = threading.local()

class DatabaseError(Exception):
    """Custom database exception"""
    pass

class ValidationError(Exception):
    """Custom validation exception"""
    pass

@contextmanager
def get_db_connection():
    """Context manager for database connections with proper error handling"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        
        # Enable foreign key constraints
        conn.execute('PRAGMA foreign_keys = ON')
        
        # Optimize for performance
        conn.execute('PRAGMA journal_mode = WAL')
        conn.execute('PRAGMA synchronous = NORMAL')
        conn.execute('PRAGMA cache_size = 1000')
        conn.execute('PRAGMA temp_store = MEMORY')
        
        yield conn
        
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {str(e)}")
        raise DatabaseError(f"Database operation failed: {str(e)}")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected error in database operation: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def execute_query(query: str, params: tuple = (), fetch: str = 'none') -> Any:
    """Execute database query with proper error handling"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch == 'one':
                result = cursor.fetchone()
                conn.commit()
                return result
            elif fetch == 'all':
                result = cursor.fetchall()
                conn.commit()
                return result
            else:
                conn.commit()
                return cursor.rowcount
                
    except Exception as e:
        logger.error(f"Query execution failed: {query[:100]}... Error: {str(e)}")
        raise DatabaseError(f"Query execution failed: {str(e)}")

def init_db():
    """Initialize database with comprehensive error handling and optimizations"""
    try:
        logger.info("Initializing database...")
        
        # Ensure database directory exists
        db_path = Path(DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure upload directory exists
        upload_path = Path(UPLOAD_FOLDER)
        upload_path.mkdir(parents=True, exist_ok=True)
        
        with get_db_connection() as conn:
            c = conn.cursor()

            # Create outlets table with constraints and indexes
            c.execute('''
            CREATE TABLE IF NOT EXISTS outlets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                urn TEXT UNIQUE NOT NULL,
                outlet_name TEXT NOT NULL,
                customer_name TEXT,
                address TEXT,
                phone TEXT,
                outlet_type TEXT,
                local_govt TEXT,
                state TEXT,
                region TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                CONSTRAINT urn_format CHECK (length(urn) > 0),
                CONSTRAINT outlet_name_length CHECK (length(outlet_name) > 0),
                CONSTRAINT region_required CHECK (length(region) > 0)
            )
            ''') 
            
            # Create indexes for outlets table
            c.execute('CREATE INDEX IF NOT EXISTS idx_outlets_region ON outlets(region)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_outlets_state ON outlets(state)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_outlets_lga ON outlets(local_govt)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_outlets_type ON outlets(outlet_type)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_outlets_active ON outlets(is_active)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_outlets_urn ON outlets(urn)')

            # Create users table with enhanced constraints
            c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'field_agent',
                region TEXT,
                state TEXT,
                lga TEXT,
                email TEXT,
                phone TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT,
                failed_login_attempts INTEGER DEFAULT 0,
                locked_until TEXT,
                CONSTRAINT username_length CHECK (length(username) >= 3),
                CONSTRAINT password_length CHECK (length(password) >= 6),
                CONSTRAINT role_valid CHECK (role IN ('admin', 'field_agent', 'supervisor'))
            )
            ''')
            
            # Create indexes for users table
            c.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_users_region ON users(region)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)')

            # Create executions table with comprehensive tracking
            c.execute('''
            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                outlet_id INTEGER NOT NULL,
                agent_id INTEGER NOT NULL,
                execution_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                before_image TEXT,
                after_image TEXT,
                before_image_thumbnail TEXT,
                after_image_thumbnail TEXT,
                latitude REAL,
                longitude REAL,
                notes TEXT,
                products_available TEXT,  -- JSON string
                execution_score REAL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completion_time TEXT,
                review_status TEXT DEFAULT 'pending',
                reviewer_id INTEGER,
                review_notes TEXT,
                gps_accuracy REAL,
                device_info TEXT,
                upload_method TEXT DEFAULT 'manual',
                FOREIGN KEY (outlet_id) REFERENCES outlets (id) ON DELETE CASCADE,
                FOREIGN KEY (agent_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (reviewer_id) REFERENCES users (id),
                CONSTRAINT status_valid CHECK (status IN ('Pending', 'In_Progress', 'Completed', 'Cancelled')),
                CONSTRAINT review_status_valid CHECK (review_status IN ('pending', 'approved', 'rejected')),
                CONSTRAINT coordinates_valid CHECK (
                    (latitude IS NULL AND longitude IS NULL) OR
                    (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)
                ),
                CONSTRAINT score_valid CHECK (execution_score >= 0 AND execution_score <= 100)
            )
            ''')
            
            # Create indexes for executions table
            c.execute('CREATE INDEX IF NOT EXISTS idx_executions_outlet ON executions(outlet_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_executions_agent ON executions(agent_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_executions_date ON executions(execution_date)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_executions_review ON executions(review_status)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_executions_created ON executions(created_at)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_executions_coords ON executions(latitude, longitude)')

            # Create profile table for customizable branding
            c.execute('''
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY,
                company_name TEXT NOT NULL DEFAULT 'DANGOTE',
                app_title TEXT NOT NULL DEFAULT 'POSM Retail Activation 2025',
                primary_color TEXT NOT NULL DEFAULT '#fdcc03',
                secondary_color TEXT NOT NULL DEFAULT '#f8f9fa',
                accent_color TEXT NOT NULL DEFAULT '#343a40',
                logo_path TEXT DEFAULT 'img/dangote-logo.png',
                favicon_path TEXT DEFAULT 'img/favicon.png',
                company_address TEXT,
                company_phone TEXT,
                company_email TEXT,
                company_website TEXT,
                footer_text TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Check if profile exists, if not create default
            c.execute("SELECT COUNT(*) FROM profile")
            if c.fetchone()[0] == 0:
                c.execute('''
                INSERT INTO profile (
                    company_name, app_title, primary_color, secondary_color, accent_color,
                    logo_path, favicon_path, company_address, company_phone, company_email,
                    footer_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    'DANGOTE',
                    'POSM Retail Activation 2025',
                    '#fdcc03',
                    '#f8f9fa',
                    '#343a40',
                    'img/dangote-logo.png',
                    'img/favicon.png',
                    'Dangote Industries Limited, Lagos, Nigeria',
                    '+234-1-234-5678',
                    'info@dangote.com',
                    '© 2025 Dangote Industries Limited. All rights reserved.'
                ))

            # Tables created successfully - no sample data inserted
            # Use separate scripts to populate sample/demo data as needed
                    
            # Commit all changes
            conn.commit()
            logger.info("Database initialized successfully")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise DatabaseError(f"Failed to initialize database: {str(e)}")

# Database connection already defined above as context manager

def get_db_connection_simple():
    """Simple database connection for backward compatibility"""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

# Enhanced Model Classes for better data handling

class BaseModel:
    """Base model class with common functionality"""
    
    @staticmethod
    def validate_required_fields(data: dict, required_fields: list) -> Tuple[bool, str]:
        """Validate required fields are present"""
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
        return True, "Validation passed"
    
    @staticmethod
    def sanitize_data(data: dict) -> dict:
        """Sanitize input data"""
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = value.strip()
            else:
                sanitized[key] = value
        return sanitized

class UserModel(BaseModel):
    """User model with enhanced validation and security"""
    
    REQUIRED_FIELDS = ['username', 'password', 'full_name', 'role']
    VALID_ROLES = ['admin', 'field_agent', 'supervisor']
    
    @classmethod
    def create_user(cls, user_data: dict) -> Tuple[bool, Union[int, str]]:
        """Create new user with validation"""
        try:
            # Sanitize data
            user_data = cls.sanitize_data(user_data)
            
            # Validate required fields
            is_valid, message = cls.validate_required_fields(user_data, cls.REQUIRED_FIELDS)
            if not is_valid:
                return False, message
            
            # Validate role
            if user_data['role'] not in cls.VALID_ROLES:
                return False, f"Invalid role. Must be one of: {', '.join(cls.VALID_ROLES)}"
            
            # Validate username length
            if len(user_data['username']) < 3:
                return False, "Username must be at least 3 characters"
            
            # Validate password length  
            if len(user_data['password']) < 6:
                return False, "Password must be at least 6 characters"
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check if username exists
                cursor.execute("SELECT id FROM users WHERE username = ?", (user_data['username'],))
                if cursor.fetchone():
                    return False, "Username already exists"
                
                # Insert user
                cursor.execute('''
                INSERT INTO users (username, password, full_name, role, region, state, lga, email, phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_data['username'],
                    user_data['password'],
                    user_data['full_name'],
                    user_data['role'],
                    user_data.get('region'),
                    user_data.get('state'),
                    user_data.get('lga'),
                    user_data.get('email'),
                    user_data.get('phone')
                ))
                
                user_id = cursor.lastrowid
                conn.commit()
                
                log_database_operation('CREATE', 'users', {'user_id': user_id, 'username': user_data['username']})
                logger.info(f"User created successfully: {user_data['username']} (ID: {user_id})")
                
                return True, user_id
                
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return False, f"Failed to create user: {str(e)}"
    
    @classmethod
    def authenticate_user(cls, username: str, password: str) -> Tuple[bool, Optional[dict]]:
        """Authenticate user with enhanced security"""
        try:
            from datetime import timedelta  # Import timedelta
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get user with active status check
                cursor.execute(
                    "SELECT * FROM users WHERE username = ? AND is_active = 1", 
                    (username,)
                )
                user = cursor.fetchone()
                
                if not user:
                    logger.warning(f"Login attempt for non-existent user: {username}")
                    return False, None
                
                # Check if account is locked
                if user['locked_until']:
                    locked_until = datetime.fromisoformat(user['locked_until'])
                    if datetime.now() < locked_until:
                        logger.warning(f"Login attempt for locked account: {username}")
                        return False, None
                
                # Verify password (in production, use proper password hashing)
                if user['password'] == password:
                    # Reset failed attempts on successful login
                    cursor.execute(
                        "UPDATE users SET failed_login_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?",
                        (datetime.now().isoformat(), user['id'])
                    )
                    conn.commit()
                    
                    log_database_operation('LOGIN_SUCCESS', 'users', {'user_id': user['id'], 'username': username})
                    logger.info(f"Successful login for user: {username}")
                    
                    return True, dict(user)
                else:
                    # Increment failed attempts
                    failed_attempts = user['failed_login_attempts'] + 1
                    locked_until = None
                    
                    # Lock account after 5 failed attempts for 30 minutes
                    if failed_attempts >= 5:
                        locked_until = (datetime.now() + timedelta(minutes=30)).isoformat()
                    
                    cursor.execute(
                        "UPDATE users SET failed_login_attempts = ?, locked_until = ? WHERE id = ?",
                        (failed_attempts, locked_until, user['id'])
                    )
                    conn.commit()
                    
                    logger.warning(f"Failed login attempt for user: {username} (attempt {failed_attempts})")
                    return False, None
                    
        except Exception as e:
            logger.error(f"Error authenticating user: {str(e)}")
            return False, None

class OutletModel(BaseModel):
    """Outlet model with enhanced validation"""
    
    REQUIRED_FIELDS = ['urn', 'outlet_name', 'region']
    
    @classmethod
    def create_outlet(cls, outlet_data: dict) -> Tuple[bool, Union[int, str]]:
        """Create new outlet with validation"""
        try:
            # Sanitize data
            outlet_data = cls.sanitize_data(outlet_data)
            
            # Validate required fields
            is_valid, message = cls.validate_required_fields(outlet_data, cls.REQUIRED_FIELDS)
            if not is_valid:
                return False, message
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check if URN exists
                cursor.execute("SELECT id FROM outlets WHERE urn = ?", (outlet_data['urn'],))
                if cursor.fetchone():
                    return False, "URN already exists"
                
                # Insert outlet
                cursor.execute('''
                INSERT INTO outlets (urn, outlet_name, customer_name, address, phone, outlet_type, local_govt, state, region)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    outlet_data['urn'],
                    outlet_data['outlet_name'],
                    outlet_data.get('customer_name'),
                    outlet_data.get('address'),
                    outlet_data.get('phone'),
                    outlet_data.get('outlet_type'),
                    outlet_data.get('local_govt'),
                    outlet_data.get('state'),
                    outlet_data['region']
                ))
                
                outlet_id = cursor.lastrowid
                conn.commit()
                
                log_database_operation('CREATE', 'outlets', {'outlet_id': outlet_id, 'urn': outlet_data['urn']})
                logger.info(f"Outlet created successfully: {outlet_data['urn']} (ID: {outlet_id})")
                
                return True, outlet_id
                
        except Exception as e:
            logger.error(f"Error creating outlet: {str(e)}")
            return False, f"Failed to create outlet: {str(e)}"

class ExecutionModel(BaseModel):
    """Execution model with enhanced validation and tracking"""
    
    REQUIRED_FIELDS = ['outlet_id', 'agent_id']
    VALID_STATUSES = ['Pending', 'In_Progress', 'Completed', 'Cancelled']
    
    @classmethod
    def create_execution(cls, execution_data: dict) -> Tuple[bool, Union[int, str]]:
        """Create new execution with validation"""
        try:
            # Validate required fields
            is_valid, message = cls.validate_required_fields(execution_data, cls.REQUIRED_FIELDS)
            if not is_valid:
                return False, message
            
            # Validate coordinates if provided
            if execution_data.get('latitude') and execution_data.get('longitude'):
                from .utils import validate_coordinates
                coord_valid, coord_message = validate_coordinates(
                    execution_data['latitude'], 
                    execution_data['longitude']
                )
                if not coord_valid:
                    return False, coord_message
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Verify outlet and agent exist
                cursor.execute("SELECT id FROM outlets WHERE id = ? AND is_active = 1", (execution_data['outlet_id'],))
                if not cursor.fetchone():
                    return False, "Outlet not found or inactive"
                
                cursor.execute("SELECT id FROM users WHERE id = ? AND is_active = 1", (execution_data['agent_id'],))
                if not cursor.fetchone():
                    return False, "Agent not found or inactive"
                
                # Insert execution
                cursor.execute('''
                INSERT INTO executions (
                    outlet_id, agent_id, execution_date, before_image, after_image, 
                    before_image_thumbnail, after_image_thumbnail,
                    latitude, longitude, notes, products_available, status,
                    gps_accuracy, device_info, upload_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    execution_data['outlet_id'],
                    execution_data['agent_id'],
                    execution_data.get('execution_date', datetime.now().isoformat()),
                    execution_data.get('before_image'),
                    execution_data.get('after_image'),
                    execution_data.get('before_image_thumbnail'),
                    execution_data.get('after_image_thumbnail'),
                    execution_data.get('latitude'),
                    execution_data.get('longitude'),
                    execution_data.get('notes'),
                    json.dumps(execution_data.get('products_available', {})),
                    execution_data.get('status', 'Pending'),
                    execution_data.get('gps_accuracy'),
                    json.dumps(execution_data.get('device_info', {})),
                    execution_data.get('upload_method', 'manual')
                ))
                
                execution_id = cursor.lastrowid
                conn.commit()
                
                log_database_operation('CREATE', 'executions', {
                    'execution_id': execution_id, 
                    'outlet_id': execution_data['outlet_id'],
                    'agent_id': execution_data['agent_id']
                })
                logger.info(f"Execution created successfully: ID {execution_id}")
                
                return True, execution_id
                
        except Exception as e:
            logger.error(f"Error creating execution: {str(e)}")
            return False, f"Failed to create execution: {str(e)}"

# Profile management functions with enhanced error handling
def get_profile() -> Optional[dict]:
    """Get the current profile settings with error handling"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM profile WHERE id = 1')
            profile = cursor.fetchone()
            return dict(profile) if profile else None
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        return None

def update_profile(profile_data: dict) -> bool:
    """Update profile settings with enhanced validation"""
    try:
        # Validate required fields
        required_fields = ['company_name', 'app_title']
        for field in required_fields:
            if not profile_data.get(field):
                logger.error(f"Missing required profile field: {field}")
                return False
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
            UPDATE profile SET 
                company_name = ?, app_title = ?, primary_color = ?, secondary_color = ?, 
                accent_color = ?, logo_path = ?, favicon_path = ?, company_address = ?, 
                company_phone = ?, company_email = ?, company_website = ?, footer_text = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            ''', (
                profile_data.get('company_name'),
                profile_data.get('app_title'),
                profile_data.get('primary_color'),
                profile_data.get('secondary_color'),
                profile_data.get('accent_color'),
                profile_data.get('logo_path'),
                profile_data.get('favicon_path'),
                profile_data.get('company_address'),
                profile_data.get('company_phone'),
                profile_data.get('company_email'),
                profile_data.get('company_website'),
                profile_data.get('footer_text')
            ))
            
            conn.commit()
            log_database_operation('UPDATE', 'profile', profile_data)
            logger.info("Profile updated successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        return False

# Database maintenance functions
def optimize_database() -> bool:
    """Optimize database performance"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Run VACUUM to reclaim space
            cursor.execute('VACUUM')
            
            # Analyze tables for query optimization
            cursor.execute('ANALYZE')
            
            logger.info("Database optimization completed")
            return True
            
    except Exception as e:
        logger.error(f"Database optimization failed: {str(e)}")
        return False

def get_database_stats() -> dict:
    """Get database statistics"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Table counts
            for table in ['users', 'outlets', 'executions', 'profile']:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                stats[f'{table}_count'] = cursor.fetchone()[0]
            
            # Database size
            cursor.execute('PRAGMA page_count')
            page_count = cursor.fetchone()[0]
            cursor.execute('PRAGMA page_size')
            page_size = cursor.fetchone()[0]
            stats['database_size_bytes'] = page_count * page_size
            stats['database_size_mb'] = (page_count * page_size) / (1024 * 1024)
            
            return stats
            
    except Exception as e:
        logger.error(f"Error getting database stats: {str(e)}")
        return {}
