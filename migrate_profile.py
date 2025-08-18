#!/usr/bin/env python3
"""Migration script to add profile table to existing database"""

import sqlite3
import os
from datetime import datetime

DB_PATH = 'maindatabase.db'

def migrate_add_profile_table():
    """Add profile table to existing database"""
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found. Please run init_db() first.")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        # Check if profile table already exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='profile'")
        if c.fetchone():
            print("Profile table already exists. Skipping migration.")
            return True
        
        print("Creating profile table...")
        
        # Create profile table
        c.execute('''
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
        
        # Insert default profile data
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
        
        conn.commit()
        print("Profile table created successfully with default Dangote branding.")
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    print("Running profile table migration...")
    success = migrate_add_profile_table()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")