#!/usr/bin/env python3
"""
Database Schema Migration Script
Fixes database schema issues for PythonAnywhere deployment
Handles missing columns and other schema differences
"""

import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

# Database configuration
DB_PATH = 'maindatabase.db'

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

def get_table_columns(cursor, table_name):
    """Get the columns of a table"""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return columns
    except Exception as e:
        logger.error(f"Error getting columns for table {table_name}: {str(e)}")
        return []

def add_missing_columns():
    """Add missing columns to existing tables"""
    try:
        logger.info("Checking for missing columns...")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check outlets table
            outlets_columns = get_table_columns(cursor, 'outlets')
            logger.info(f"Outlets table columns: {outlets_columns}")
            
            missing_outlets_columns = []
            required_outlets_columns = [
                ('is_active', 'INTEGER DEFAULT 1'),
                ('created_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
                ('updated_at', 'TEXT DEFAULT CURRENT_TIMESTAMP')
            ]
            
            for col_name, col_def in required_outlets_columns:
                if col_name not in outlets_columns:
                    missing_outlets_columns.append((col_name, col_def))
            
            # Add missing columns to outlets table
            for col_name, col_def in missing_outlets_columns:
                try:
                    cursor.execute(f"ALTER TABLE outlets ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Added column '{col_name}' to outlets table")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        logger.info(f"Column '{col_name}' already exists in outlets table")
                    else:
                        logger.error(f"Error adding column '{col_name}' to outlets: {str(e)}")
            
            # Check users table
            users_columns = get_table_columns(cursor, 'users')
            logger.info(f"Users table columns: {users_columns}")
            
            missing_users_columns = []
            required_users_columns = [
                ('is_active', 'INTEGER DEFAULT 1'),
                ('created_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
                ('updated_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
                ('last_login', 'TEXT'),
                ('failed_login_attempts', 'INTEGER DEFAULT 0'),
                ('locked_until', 'TEXT'),
                ('email', 'TEXT'),
                ('phone', 'TEXT'),
                ('region', 'TEXT'),
                ('state', 'TEXT'),
                ('lga', 'TEXT')
            ]
            
            for col_name, col_def in required_users_columns:
                if col_name not in users_columns:
                    missing_users_columns.append((col_name, col_def))
            
            # Add missing columns to users table
            for col_name, col_def in missing_users_columns:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                    logger.info(f"Added column '{col_name}' to users table")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        logger.info(f"Column '{col_name}' already exists in users table")
                    else:
                        logger.error(f"Error adding column '{col_name}' to users: {str(e)}")
            
            # Check executions table
            try:
                executions_columns = get_table_columns(cursor, 'executions')
                logger.info(f"Executions table columns: {executions_columns}")
                
                missing_executions_columns = []
                required_executions_columns = [
                    ('created_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
                    ('updated_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
                    ('completion_time', 'TEXT'),
                    ('review_status', 'TEXT DEFAULT "pending"'),
                    ('reviewer_id', 'INTEGER'),
                    ('review_notes', 'TEXT'),
                    ('gps_accuracy', 'REAL'),
                    ('device_info', 'TEXT'),
                    ('upload_method', 'TEXT DEFAULT "manual"')
                ]
                
                for col_name, col_def in required_executions_columns:
                    if col_name not in executions_columns:
                        missing_executions_columns.append((col_name, col_def))
                
                # Add missing columns to executions table
                for col_name, col_def in missing_executions_columns:
                    try:
                        cursor.execute(f"ALTER TABLE executions ADD COLUMN {col_name} {col_def}")
                        logger.info(f"Added column '{col_name}' to executions table")
                    except sqlite3.OperationalError as e:
                        if "duplicate column name" in str(e).lower():
                            logger.info(f"Column '{col_name}' already exists in executions table")
                        else:
                            logger.error(f"Error adding column '{col_name}' to executions: {str(e)}")
                            
            except sqlite3.OperationalError as e:
                if "no such table" in str(e).lower():
                    logger.info("Executions table doesn't exist yet, will be created by init_db")
                else:
                    logger.error(f"Error checking executions table: {str(e)}")
            
            conn.commit()
            logger.info("Database schema migration completed successfully")
            return True
            
    except Exception as e:
        logger.error(f"Schema migration failed: {str(e)}")
        return False

def create_missing_tables():
    """Create any missing tables"""
    try:
        logger.info("Checking for missing tables...")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get existing tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Existing tables: {existing_tables}")
            
            # Create profile table if missing
            if 'profile' not in existing_tables:
                logger.info("Creating profile table...")
                cursor.execute('''
                CREATE TABLE profile (
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
                
                # Insert default profile
                cursor.execute('''
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
                logger.info("Profile table created successfully")
            
            # Create executions table if missing
            if 'executions' not in existing_tables:
                logger.info("Creating executions table...")
                cursor.execute('''
                CREATE TABLE executions (
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
                    products_available TEXT,
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
                    FOREIGN KEY (reviewer_id) REFERENCES users (id)
                )
                ''')
                logger.info("Executions table created successfully")
            
            conn.commit()
            logger.info("Missing tables creation completed")
            return True
            
    except Exception as e:
        logger.error(f"Table creation failed: {str(e)}")
        return False

def create_indexes():
    """Create missing indexes"""
    try:
        logger.info("Creating missing indexes...")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Indexes for outlets table
            indexes_outlets = [
                "CREATE INDEX IF NOT EXISTS idx_outlets_region ON outlets(region)",
                "CREATE INDEX IF NOT EXISTS idx_outlets_state ON outlets(state)",
                "CREATE INDEX IF NOT EXISTS idx_outlets_lga ON outlets(local_govt)",
                "CREATE INDEX IF NOT EXISTS idx_outlets_type ON outlets(outlet_type)",
                "CREATE INDEX IF NOT EXISTS idx_outlets_active ON outlets(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_outlets_urn ON outlets(urn)"
            ]
            
            # Indexes for users table
            indexes_users = [
                "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
                "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
                "CREATE INDEX IF NOT EXISTS idx_users_region ON users(region)",
                "CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)"
            ]
            
            # Indexes for executions table
            indexes_executions = [
                "CREATE INDEX IF NOT EXISTS idx_executions_outlet ON executions(outlet_id)",
                "CREATE INDEX IF NOT EXISTS idx_executions_agent ON executions(agent_id)",
                "CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status)",
                "CREATE INDEX IF NOT EXISTS idx_executions_date ON executions(execution_date)",
                "CREATE INDEX IF NOT EXISTS idx_executions_review ON executions(review_status)",
                "CREATE INDEX IF NOT EXISTS idx_executions_created ON executions(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_executions_coords ON executions(latitude, longitude)"
            ]
            
            all_indexes = indexes_outlets + indexes_users + indexes_executions
            
            for index_sql in all_indexes:
                try:
                    cursor.execute(index_sql)
                    logger.debug(f"Created index: {index_sql}")
                except Exception as e:
                    logger.warning(f"Index creation warning: {str(e)}")
            
            conn.commit()
            logger.info("Index creation completed")
            return True
            
    except Exception as e:
        logger.error(f"Index creation failed: {str(e)}")
        return False

def backup_existing_data():
    """Create a backup of existing data before migration"""
    try:
        backup_path = f"backup_maindatabase_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        if Path(DB_PATH).exists():
            logger.info(f"Creating backup: {backup_path}")
            
            # Simple file copy for SQLite
            import shutil
            shutil.copy2(DB_PATH, backup_path)
            
            logger.info(f"Backup created successfully: {backup_path}")
            return backup_path
        else:
            logger.info("No existing database to backup")
            return None
            
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        return None

def validate_schema():
    """Validate the final schema"""
    try:
        logger.info("Validating database schema...")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check required tables exist
            required_tables = ['users', 'outlets', 'executions', 'profile']
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            
            missing_tables = [table for table in required_tables if table not in existing_tables]
            if missing_tables:
                logger.error(f"Missing tables: {missing_tables}")
                return False
            
            # Check required columns exist
            for table in ['users', 'outlets']:
                columns = get_table_columns(cursor, table)
                if 'is_active' not in columns:
                    logger.error(f"Missing 'is_active' column in {table} table")
                    return False
            
            logger.info("Schema validation passed")
            return True
            
    except Exception as e:
        logger.error(f"Schema validation failed: {str(e)}")
        return False

def clear_duplicate_users():
    """Remove duplicate users that might be causing constraint issues"""
    try:
        logger.info("Checking for duplicate users...")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Find duplicate usernames
            cursor.execute('''
                SELECT username, COUNT(*) as count 
                FROM users 
                GROUP BY username 
                HAVING COUNT(*) > 1
            ''')
            
            duplicates = cursor.fetchall()
            
            if duplicates:
                logger.warning(f"Found {len(duplicates)} duplicate usernames")
                
                for username, count in duplicates:
                    logger.warning(f"Duplicate username '{username}' appears {count} times")
                    
                    # Keep the first occurrence, delete the rest
                    cursor.execute('''
                        DELETE FROM users 
                        WHERE username = ? AND id NOT IN (
                            SELECT MIN(id) FROM users WHERE username = ?
                        )
                    ''', (username, username))
                    
                    deleted_count = cursor.rowcount
                    logger.info(f"Removed {deleted_count} duplicate entries for username '{username}'")
                
                conn.commit()
                logger.info("Duplicate user cleanup completed")
            else:
                logger.info("No duplicate users found")
                
            return True
            
    except Exception as e:
        logger.error(f"Duplicate cleanup failed: {str(e)}")
        return False

def fix_database_schema():
    """Main function to fix database schema issues"""
    try:
        print("🔧 Starting database schema migration...")
        print("=" * 50)
        
        # Check if database exists
        if not Path(DB_PATH).exists():
            logger.info("Database doesn't exist, will be created fresh")
            return True
        
        # Create backup
        backup_path = backup_existing_data()
        if backup_path:
            print(f"✅ Backup created: {backup_path}")
        
        # Clear duplicates first
        print("🧹 Cleaning duplicate users...")
        if not clear_duplicate_users():
            print("❌ Failed to clean duplicates")
            return False
        print("✅ Duplicate cleanup completed")
        
        # Create missing tables
        print("📋 Creating missing tables...")
        if not create_missing_tables():
            print("❌ Failed to create missing tables")
            return False
        print("✅ Missing tables created")
        
        # Add missing columns
        print("🗃️  Adding missing columns...")
        if not add_missing_columns():
            print("❌ Failed to add missing columns")
            return False
        print("✅ Missing columns added")
        
        # Create indexes
        print("📊 Creating database indexes...")
        if not create_indexes():
            print("❌ Failed to create indexes")
            return False
        print("✅ Database indexes created")
        
        # Validate schema
        print("✔️  Validating schema...")
        if not validate_schema():
            print("❌ Schema validation failed")
            return False
        print("✅ Schema validation passed")
        
        print("\n🎉 Database schema migration completed successfully!")
        print("Your database is now ready for PythonAnywhere deployment.")
        return True
        
    except Exception as e:
        logger.error(f"Schema migration failed: {str(e)}")
        print(f"❌ Migration failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("Database Schema Migration Tool")
    print("This will fix schema issues for PythonAnywhere deployment")
    print()
    
    success = fix_database_schema()
    
    if success:
        print("\n📋 Next steps:")
        print("1. Upload your fixed code to PythonAnywhere")
        print("2. Install missing dependencies (see PYTHONANYWHERE_DEPLOYMENT.md)")
        print("3. Restart your web app")
    else:
        print("\n❌ Migration failed. Check the logs above for details.")
