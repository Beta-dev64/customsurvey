#!/usr/bin/env python3
"""
Clean Database Initialization Script
Creates database tables without any sample data
"""

import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

# Database configuration
DB_PATH = 'maindatabase.db'
UPLOAD_FOLDER = 'static/uploads'

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseError(Exception):
    """Custom database exception"""
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

def init_db_clean():
    """Initialize database with only table structures (no sample data)"""
    try:
        logger.info("Initializing clean database...")
        
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

            # Only create default profile if it doesn't exist, but NO sample outlets/users
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
                
            # Commit all changes
            conn.commit()
            logger.info("Clean database initialized successfully (tables only, no sample data)")
            
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise DatabaseError(f"Failed to initialize database: {str(e)}")

def check_tables_exist():
    """Check if tables exist and are empty"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"Existing tables: {tables}")
            
            # Check table counts
            for table in ['users', 'outlets', 'executions']:
                if table in tables:
                    cursor.execute(f'SELECT COUNT(*) FROM {table}')
                    count = cursor.fetchone()[0]
                    logger.info(f"Table '{table}' has {count} records")
                    
    except Exception as e:
        logger.error(f"Error checking tables: {str(e)}")

if __name__ == "__main__":
    print("Initializing clean database (tables only)...")
    init_db_clean()
    print("Checking table status...")
    check_tables_exist()
    print("Database initialization completed!")
