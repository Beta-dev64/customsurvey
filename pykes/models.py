# pykes/models.py
import sqlite3
from datetime import datetime
import os

DB_PATH = 'maindatabase.db'
UPLOAD_FOLDER = 'static/uploads'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Create outlets table
    c.execute('''
    CREATE TABLE IF NOT EXISTS outlets (
        id INTEGER PRIMARY KEY,
        urn TEXT UNIQUE,
        outlet_name TEXT,
        customer_name TEXT,
        address TEXT,
        phone TEXT,
        outlet_type TEXT,
        local_govt TEXT,
        state TEXT,
        region TEXT
    )
    ''')

    # Create users table (execution agents)
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        full_name TEXT,
        role TEXT,
        region TEXT,
        state TEXT,
        lga TEXT
    )
    ''')

    # Create executions table
    c.execute('''
    CREATE TABLE IF NOT EXISTS executions (
        id INTEGER PRIMARY KEY,
        outlet_id INTEGER,
        agent_id INTEGER,
        execution_date TEXT,
        before_image TEXT,
        after_image TEXT,
        latitude REAL,
        longitude REAL,
        notes TEXT,
        products_available TEXT,
        execution_score REAL,
        status TEXT,
        FOREIGN KEY (outlet_id) REFERENCES outlets (id),
        FOREIGN KEY (agent_id) REFERENCES users (id)
    )
    ''')

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

    # Check if outlets are already populated
    c.execute("SELECT COUNT(*) FROM outlets")
    if c.fetchone()[0] == 0:
        # Populate sample data
        outlets = [
            ('DCP/19/SW/ED/1000001', 'FAMS STEEL COMPANY 2', 'FAMOUS EBESUNUN', '156, USELU LAGOS ROAD, BENIN', '7039539773', 'Shop', 'EGOR', 'EDO', 'SW'),
            ('DCP/19/SW/ED/1000002', 'FAMS STEEL COMPANY', 'FAMOUS EBESUNUN', '162, USELU LAGOS ROAD, BENIN', '7039539773', 'Shop', 'EGOR', 'EDO', 'SW'),
            ('DCP/19/SW/ED/1000003', 'IGWE CONSTRUCTION 1', 'IGWE WILFRED', '214, LAGOS/BENIN ROAD, UGBOWO, BENIN', '8052220480', 'Shop', 'EGOR', 'EDO', 'SW'),
            ('DCP/19/SW/ED/1000004', 'ALEXO HOLDING ENT', 'ALEX CHIDIMA', '3,ISIOR VILLAGE, BESIDE PETOM FILLING STATION.BENIN/LAGOS ROAD', '8182728117', 'Shop', 'EGOR', 'EDO', 'SW'),
            ('DCP/19/SW/ED/1000005', 'IFE ENT.', 'IFEANYI OKEKE', 'OPP. KONKON FILLING STATION,EVBUOMORE QTRS ,ISIOR BENIN', '8035551600', 'CONTAINER', 'EGOR', 'EDO', 'SW'),
            ('DCP/19/SW/ED/1000006', 'OGHAS CEMENT', 'TONY UCHE', '13A, LAGOS/BENIN ROAD, ISIOR,BENIN', '8032813962', 'Shop', 'EGOR', 'EDO', 'SW'),
            ('DCP/19/SW/ED/1000007', 'ONOS CEMENT', 'ONOS SAMUEL', 'AGEN JUNCTION, LAGOS BENIN EXPRESS ROAD', '8037208594', 'CONTAINER', 'OVIA NORTH EAST', 'EDO', 'SW'),
            ('DCP/19/SW/ED/1000008', 'OSAS K 1', 'OSAS KELVIN', '112, nitel road, off lagos benin road', '8037455230', 'CONTAINER', 'EGOR', 'EDO', 'SW')
        ]

        for outlet in outlets:
            c.execute('''
            INSERT INTO outlets (urn, outlet_name, customer_name, address, phone, outlet_type, local_govt, state, region)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', outlet)

        # Add sample users
        users = [
            ('admin', 'admin123', 'Admin User', 'admin', 'ALL'),
            ('agent1', 'agent123', 'John Doe', 'field_agent', 'SW'),
            ('agent2', 'agent123', 'Jane Smith', 'field_agent', 'SW')
        ]

        for user in users:
            c.execute('''
            INSERT INTO users (username, password, full_name, role, region)
            VALUES (?, ?, ?, ?, ?)
            ''', user)

    conn.commit()
    conn.close()

    # Ensure upload directory exists
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Profile management functions
def get_profile():
    """Get the current profile settings"""
    conn = get_db_connection()
    profile = conn.execute('SELECT * FROM profile WHERE id = 1').fetchone()
    conn.close()
    return dict(profile) if profile else None

def update_profile(profile_data):
    """Update profile settings"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Update profile
    c.execute('''
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
    conn.close()
    return True