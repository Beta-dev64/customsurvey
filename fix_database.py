#!/usr/bin/env python3
"""
Database schema fix script
Adds missing columns to existing database tables
"""

import sqlite3
import os

def check_and_fix_database():
    """Check existing database schema and add missing columns"""
    db_path = 'maindatabase.db'
    
    if not os.path.exists(db_path):
        print("Database file does not exist. It will be created when the app runs.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check outlets table schema
        cursor.execute("PRAGMA table_info(outlets)")
        outlets_columns = cursor.fetchall()
        column_names = [col[1] for col in outlets_columns]
        
        print("Existing outlets table columns:", column_names)
        
        # Add missing columns if they don't exist
        if 'is_active' not in column_names:
            print("Adding is_active column to outlets table...")
            cursor.execute("ALTER TABLE outlets ADD COLUMN is_active INTEGER DEFAULT 1")
            print("✓ Added is_active column to outlets table")
        
        if 'created_at' not in column_names:
            print("Adding created_at column to outlets table...")
            cursor.execute("ALTER TABLE outlets ADD COLUMN created_at TEXT")
            print("✓ Added created_at column to outlets table")
        
        if 'updated_at' not in column_names:
            print("Adding updated_at column to outlets table...")
            cursor.execute("ALTER TABLE outlets ADD COLUMN updated_at TEXT")
            print("✓ Added updated_at column to outlets table")
        
        # Check users table schema
        cursor.execute("PRAGMA table_info(users)")
        users_columns = cursor.fetchall()
        user_column_names = [col[1] for col in users_columns]
        
        print("Existing users table columns:", user_column_names)
        
        # Add missing columns to users table if they don't exist
        missing_user_columns = [
            ('is_active', 'INTEGER DEFAULT 1'),
            ('created_at', 'TEXT'),
            ('updated_at', 'TEXT'),
            ('last_login', 'TEXT'),
            ('failed_login_attempts', 'INTEGER DEFAULT 0'),
            ('locked_until', 'TEXT'),
            ('email', 'TEXT'),
            ('phone', 'TEXT')
        ]
        
        for col_name, col_def in missing_user_columns:
            if col_name not in user_column_names:
                print(f"Adding {col_name} column to users table...")
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                print(f"✓ Added {col_name} column to users table")
        
        # Check executions table schema
        cursor.execute("PRAGMA table_info(executions)")
        executions_columns = cursor.fetchall()
        execution_column_names = [col[1] for col in executions_columns]
        
        print("Existing executions table columns:", execution_column_names)
        
        # Add missing columns to executions table if they don't exist
        missing_execution_columns = [
            ('before_image_thumbnail', 'TEXT'),
            ('after_image_thumbnail', 'TEXT'),
            ('execution_score', 'REAL DEFAULT 0'),
            ('created_at', 'TEXT'),
            ('updated_at', 'TEXT'),
            ('completion_time', 'TEXT'),
            ('review_status', 'TEXT'),
            ('reviewer_id', 'INTEGER'),
            ('review_notes', 'TEXT'),
            ('gps_accuracy', 'REAL'),
            ('device_info', 'TEXT'),
            ('upload_method', 'TEXT')
        ]
        
        for col_name, col_def in missing_execution_columns:
            if col_name not in execution_column_names:
                print(f"Adding {col_name} column to executions table...")
                cursor.execute(f"ALTER TABLE executions ADD COLUMN {col_name} {col_def}")
                print(f"✓ Added {col_name} column to executions table")
        
        conn.commit()
        print("✓ Database schema updated successfully!")
        
    except Exception as e:
        print(f"Error updating database schema: {str(e)}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    check_and_fix_database()
