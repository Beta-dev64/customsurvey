#!/usr/bin/env python3
"""
Demo Users Creation Script
Creates demo users for testing: one admin and one field agent
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

def check_user_exists(cursor, username):
    """Check if a username already exists"""
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    return cursor.fetchone() is not None

def create_demo_users():
    """Create demo users: one admin and one field agent"""
    try:
        logger.info("Creating demo users...")
        
        # Check if database file exists
        if not Path(DB_PATH).exists():
            logger.error(f"Database file '{DB_PATH}' not found. Please run init_db_clean.py first.")
            return False
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if users table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cursor.fetchone():
                logger.error("Users table not found. Please run init_db_clean.py first.")
                return False
            
            created_users = []
            
            # Demo Admin User
            admin_data = {
                'username': 'admin',
                'password': 'admin123',  # In production, this would be hashed
                'full_name': 'System Administrator',
                'role': 'admin',
                'region': 'ALL',
                'state': 'ALL',
                'lga': 'ALL',
                'email': 'admin@surveytray.com',
                'phone': '+234-800-123-4567'
            }
            
            # Check if admin already exists
            if not check_user_exists(cursor, admin_data['username']):
                cursor.execute('''
                INSERT INTO users (username, password, full_name, role, region, state, lga, email, phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    admin_data['username'],
                    admin_data['password'],
                    admin_data['full_name'],
                    admin_data['role'],
                    admin_data['region'],
                    admin_data['state'],
                    admin_data['lga'],
                    admin_data['email'],
                    admin_data['phone']
                ))
                
                admin_id = cursor.lastrowid
                created_users.append(f"Admin user '{admin_data['username']}' (ID: {admin_id})")
                logger.info(f"Created admin user: {admin_data['username']} (ID: {admin_id})")
            else:
                logger.info(f"Admin user '{admin_data['username']}' already exists, skipping...")
            
            # Demo Field Agent User
            agent_data = {
                'username': 'field_agent_demo',
                'password': 'agent123',  # In production, this would be hashed
                'full_name': 'John Field Agent',
                'role': 'field_agent',
                'region': 'SW',
                'state': 'LAGOS',
                'lga': 'IKEJA',
                'email': 'john.agent@surveytray.com',
                'phone': '+234-803-555-0123'
            }
            
            # Check if field agent already exists
            if not check_user_exists(cursor, agent_data['username']):
                cursor.execute('''
                INSERT INTO users (username, password, full_name, role, region, state, lga, email, phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    agent_data['username'],
                    agent_data['password'],
                    agent_data['full_name'],
                    agent_data['role'],
                    agent_data['region'],
                    agent_data['state'],
                    agent_data['lga'],
                    agent_data['email'],
                    agent_data['phone']
                ))
                
                agent_id = cursor.lastrowid
                created_users.append(f"Field agent '{agent_data['username']}' (ID: {agent_id})")
                logger.info(f"Created field agent user: {agent_data['username']} (ID: {agent_id})")
            else:
                logger.info(f"Field agent '{agent_data['username']}' already exists, skipping...")
            
            # Commit all changes
            conn.commit()
            
            # Show summary
            if created_users:
                logger.info(f"Demo users created successfully:")
                for user in created_users:
                    logger.info(f"  - {user}")
            else:
                logger.info("No new users created (all demo users already exist)")
            
            # Show all current users
            cursor.execute("SELECT id, username, full_name, role, region, is_active FROM users ORDER BY role, username")
            all_users = cursor.fetchall()
            
            print("\n=== Current Users in Database ===")
            print(f"{'ID':<4} {'Username':<20} {'Full Name':<25} {'Role':<15} {'Region':<10} {'Active':<8}")
            print("-" * 90)
            for user in all_users:
                print(f"{user['id']:<4} {user['username']:<20} {user['full_name']:<25} {user['role']:<15} {user['region'] or 'N/A':<10} {'Yes' if user['is_active'] else 'No':<8}")
            
            print(f"\nTotal users: {len(all_users)}")
            return True
            
    except Exception as e:
        logger.error(f"Failed to create demo users: {str(e)}")
        return False

def show_login_credentials():
    """Display login credentials for demo users"""
    print("\n=== Demo User Login Credentials ===")
    print("Admin User:")
    print("  Username: admin")
    print("  Password: admin123")
    print("  Role: admin")
    print("  Access: All regions")
    print()
    print("Field Agent User:")
    print("  Username: field_agent_demo")
    print("  Password: agent123")
    print("  Role: field_agent")
    print("  Region: SW (Southwest)")
    print()
    print("⚠️  IMPORTANT: Change these default passwords in production!")

if __name__ == "__main__":
    print("Creating demo users for SurveyTray application...")
    print("=" * 50)
    
    success = create_demo_users()
    
    if success:
        show_login_credentials()
        print("\n✅ Demo users creation completed successfully!")
    else:
        print("\n❌ Failed to create demo users. Check the logs for details.")
        print("Make sure you've run 'python init_db_clean.py' first to create the database tables.")
