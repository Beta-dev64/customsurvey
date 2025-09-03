from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
import json
from datetime import datetime, timedelta
import os
import sqlite3
import csv
import io
import pandas as pd
import uuid
import functools
from werkzeug.utils import secure_filename
from contextlib import contextmanager
import hashlib
import math

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Constants
VALID_ROLES = ['admin', 'field_agent']
VALID_FILE_EXTENSIONS = ['.csv', '.xlsx', '.xls']
REQUIRED_USER_FIELDS = ['username', 'password', 'full_name', 'role', 'region']
REQUIRED_OUTLET_FIELDS = ['urn', 'outlet_name', 'region']
OPTIONAL_USER_FIELDS = ['state', 'lga']
OPTIONAL_OUTLET_FIELDS = ['customer_name', 'address', 'phone', 'outlet_type', 'local_govt', 'state']

# Helper functions
@contextmanager
def get_db_connection():
    """Context manager for database connections with automatic cleanup"""
    conn = sqlite3.connect('maindatabase.db')
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def validate_file_upload(file, allowed_extensions=None):
    """Validate uploaded file"""
    if allowed_extensions is None:
        allowed_extensions = VALID_FILE_EXTENSIONS
    
    if not file or file.filename == '':
        return False, 'No file selected'
    
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        return False, f'Please upload a file with extension: {", ".join(allowed_extensions)}'
    
    return True, None

def get_dashboard_stats():
    """Get dashboard statistics in a single query"""
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # Get all counts in one query for better performance
        c.execute("""
        SELECT 
            (SELECT COUNT(*) FROM users) as user_count,
            (SELECT COUNT(*) FROM outlets) as outlet_count,
            (SELECT COUNT(*) FROM executions) as execution_count
        """)
        stats = c.fetchone()
        
        # Get recent activity
        c.execute("""
        SELECT e.id, e.execution_date, u.full_name as agent, o.outlet_name, o.region
        FROM executions e
        JOIN users u ON e.agent_id = u.id
        JOIN outlets o ON e.outlet_id = o.id
        ORDER BY e.execution_date DESC
        LIMIT 5
        """)
        recent_activity = c.fetchall()
        
        return dict(stats), recent_activity

def process_csv_data(file, required_fields, optional_fields=None):
    """Generic CSV processing function"""
    if optional_fields is None:
        optional_fields = []
    
    try:
        # Read CSV file
        if file.filename.lower().endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # Validate required columns
        if not all(field in df.columns for field in required_fields):
            return None, f'File must contain columns: {", ".join(required_fields)}'
        
        # Fill missing optional columns
        for col in optional_fields:
            if col not in df.columns:
                df[col] = ''
            else:
                df[col] = df[col].fillna('')
        
        return df.to_dict('records'), None
        
    except Exception as e:
        return None, f'Error processing file: {str(e)}'

def bulk_delete_records(table, filter_field, filter_value, skip_conditions=None):
    """Generic bulk delete function"""
    if skip_conditions is None:
        skip_conditions = []
    
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # Build query
        query = f"SELECT id FROM {table} WHERE {filter_field} = ?"
        params = [filter_value]
        
        # Add skip conditions
        for condition in skip_conditions:
            query += f" AND {condition}"
        
        # Don't delete current user if it's users table
        if table == 'users':
            query += f" AND id != {session['user_id']}"
        
        c.execute(query, params)
        record_ids = [row[0] for row in c.fetchall()]
        
        if not record_ids:
            return 0, 'No records found matching the criteria'
        
        # Delete records
        placeholders = ','.join(['?'] * len(record_ids))
        c.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", record_ids)
        
        deleted_count = c.rowcount
        conn.commit()
        
        return deleted_count, None

# Admin dashboard
@admin_bp.route('/')
@admin_required
def admin_dashboard():
    stats, recent_activity = get_dashboard_stats()
    return render_template('admin/dashboard.html', 
                         user_count=stats['user_count'], 
                         outlet_count=stats['outlet_count'], 
                         execution_count=stats['execution_count'],
                         recent_activity=recent_activity)

# User management
@admin_bp.route('/users')
@admin_required
def user_list():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users ORDER BY username")
        users = c.fetchall()
    
    return render_template('admin/user_list.html', users=users)

@admin_bp.route('/users/new', methods=['GET', 'POST'])
@admin_required
def user_new():
    if request.method == 'POST':
        # Extract form data
        form_data = {
            'username': request.form.get('username', '').strip(),
            'password': request.form.get('password', '').strip(),
            'full_name': request.form.get('full_name', '').strip(),
            'role': request.form.get('role', '').strip(),
            'region': request.form.get('region', '').strip(),
            'state': request.form.get('state', '').strip(),
            'lga': request.form.get('lga', '').strip()
        }
        
        # Validate required fields
        if not all(form_data[field] for field in ['username', 'password', 'full_name', 'role']):
            flash('All required fields must be filled', 'danger')
            return render_template('admin/user_form.html')
        
        # Validate role
        if form_data['role'] not in VALID_ROLES:
            flash('Invalid role selected', 'danger')
            return render_template('admin/user_form.html')
        
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Check if username already exists
            c.execute("SELECT id FROM users WHERE username = ?", (form_data['username'],))
            if c.fetchone():
                flash('Username already exists', 'danger')
                return render_template('admin/user_form.html')
            
            # Insert new user
            c.execute('''
            INSERT INTO users (username, password, full_name, role, region, state, lga)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', tuple(form_data.values()))
            
            conn.commit()
        
        flash('User created successfully', 'success')
        return redirect(url_for('admin.user_list'))
    
    return render_template('admin/user_form.html')

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def user_edit(user_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        
        if request.method == 'POST':
            # Prevent admin from changing their own role
            if user_id == session['user_id'] and session['role'] == 'admin':
                if request.form.get('role') != 'admin':
                    flash('Cannot change your own admin role', 'danger')
                    return redirect(url_for('admin.user_list'))
            
            # Extract form data
            password = request.form.get('password', '').strip()
            full_name = request.form.get('full_name', '').strip()
            role = request.form.get('role', '').strip()
            region = request.form.get('region', '').strip()
            state = request.form.get('state', '').strip()
            lga = request.form.get('lga', '').strip()
            
            # Update user details
            if password:
                c.execute('''
                UPDATE users SET password = ?, full_name = ?, role = ?, region = ?, state = ?, lga = ?
                WHERE id = ?
                ''', (password, full_name, role, region, state, lga, user_id))
            else:
                c.execute('''
                UPDATE users SET full_name = ?, role = ?, region = ?, state = ?, lga = ?
                WHERE id = ?
                ''', (full_name, role, region, state, lga, user_id))
            
            conn.commit()
            flash('User updated successfully', 'success')
            return redirect(url_for('admin.user_list'))
        
        # Get user details for editing
        c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            flash('User not found', 'danger')
            return redirect(url_for('admin.user_list'))
    
    return render_template('admin/user_form.html', user=user)

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def user_delete(user_id):
    # Don't allow deleting self
    if user_id == session['user_id']:
        flash('Cannot delete your own account', 'danger')
        return redirect(url_for('admin.user_list'))
    
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # Check if user has executions
        c.execute("SELECT COUNT(*) FROM executions WHERE agent_id = ?", (user_id,))
        execution_count = c.fetchone()[0]
        
        if execution_count > 0:
            flash(f'Cannot delete user with {execution_count} executions', 'danger')
            return redirect(url_for('admin.user_bulk_manage'))
        
        # Delete user
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    
    flash('User deleted successfully', 'success')
    return redirect(url_for('admin.user_list'))

@admin_bp.route('/users/import', methods=['GET', 'POST'])
@admin_required
def user_import():
    if request.method == 'POST':
        file = request.files.get('csv_file')
        is_valid, error_msg = validate_file_upload(file, ['.csv'])
        
        if not is_valid:
            flash(error_msg, 'danger')
            return redirect(request.url)
        
        data, error_msg = process_csv_data(file, REQUIRED_USER_FIELDS, OPTIONAL_USER_FIELDS)
        if error_msg:
            flash(error_msg, 'danger')
            return redirect(request.url)
        
        with get_db_connection() as conn:
            c = conn.cursor()
            success_count = error_count = 0
            
            for row in data:
                try:
                    # Validate role
                    if row['role'] not in VALID_ROLES:
                        error_count += 1
                        continue
                    
                    # Check if username exists
                    c.execute("SELECT id FROM users WHERE username = ?", (row['username'],))
                    if c.fetchone():
                        error_count += 1
                        continue
                    
                    # Insert user
                    c.execute('''
                    INSERT INTO users (username, password, full_name, role, region, state, lga)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (row['username'], row['password'], row['full_name'], 
                         row['role'], row['region'], row.get('state', ''), row.get('lga', '')))
                    success_count += 1
                    
                except Exception as e:
                    print(f"Error inserting user: {str(e)}")
                    error_count += 1
            
            conn.commit()
        
        flash(f'Imported {success_count} users successfully, {error_count} errors', 'success')
        return redirect(url_for('admin.user_list'))
    
    return render_template('admin/user_import.html')

# Bulk User Operations
@admin_bp.route('/users/bulk_manage')
@admin_required
def user_bulk_manage():
    return render_template('admin/user_bulk_manage.html')

@admin_bp.route('/users/preview')
@admin_required
def user_preview():
    delete_by = request.args.get('delete_by')
    value = request.args.get('value')
    
    if not delete_by or not value:
        return jsonify({'users': []})
    
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # Build query based on filter
        query = '''
        SELECT u.*, COUNT(e.id) as executions 
        FROM users u 
        LEFT JOIN executions e ON u.id = e.agent_id
        WHERE u.{} = ?
        GROUP BY u.id
        '''.format(delete_by)
        
        c.execute(query, (value,))
        users = [dict(row) for row in c.fetchall()]
    
    return jsonify({'users': users})

@admin_bp.route('/users/bulk_delete', methods=['POST'])
@admin_required
def user_bulk_delete():
    delete_by = request.form.get('delete_by')
    value = request.form.get(delete_by) if delete_by in ['region', 'state', 'lga'] else None
    
    if not delete_by or not value:
        flash('Invalid criteria or no value specified', 'danger')
        return redirect(url_for('admin.user_bulk_manage'))
    
    # Build skip conditions
    skip_conditions = []
    if 'skip_with_executions' in request.form:
        skip_conditions.append("id NOT IN (SELECT DISTINCT agent_id FROM executions)")
    if 'skip_admins' in request.form:
        skip_conditions.append("role != 'admin'")
    
    try:
        deleted_count, error_msg = bulk_delete_records('users', delete_by, value, skip_conditions)
        if error_msg:
            flash(error_msg, 'warning')
        else:
            flash(f'Successfully deleted {deleted_count} users', 'success')
    except Exception as e:
        flash(f'Error during bulk delete: {str(e)}', 'danger')
    
    return redirect(url_for('admin.user_list'))

# Outlet management
@admin_bp.route('/outlets')
@admin_required
def outlet_list():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM outlets ORDER BY region, state, local_govt, outlet_name")
        outlets = c.fetchall()
    
    return render_template('admin/outlet_list.html', outlets=outlets)

@admin_bp.route('/outlets/new', methods=['GET', 'POST'])
@admin_required
def outlet_new():
    if request.method == 'POST':
        # Extract form data
        form_data = {
            'urn': request.form.get('urn', '').strip(),
            'outlet_name': request.form.get('outlet_name', '').strip(),
            'customer_name': request.form.get('customer_name', '').strip(),
            'address': request.form.get('address', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'outlet_type': request.form.get('outlet_type', '').strip(),
            'local_govt': request.form.get('local_govt', '').strip(),
            'state': request.form.get('state', '').strip(),
            'region': request.form.get('region', '').strip()
        }
        
        # Validate required fields
        if not all(form_data[field] for field in ['urn', 'outlet_name', 'region']):
            flash('URN, Retail Point Name and Region are required', 'danger')
            return render_template('admin/outlet_form.html')
        
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Check if URN already exists
            c.execute("SELECT id FROM outlets WHERE urn = ?", (form_data['urn'],))
            if c.fetchone():
                flash('URN already exists', 'danger')
                return render_template('admin/outlet_form.html')
            
            # Insert new outlet
            c.execute('''
            INSERT INTO outlets (urn, outlet_name, customer_name, address, phone, outlet_type, local_govt, state, region)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', tuple(form_data.values()))
            
            conn.commit()
        
        flash('Outlet created successfully', 'success')
        return redirect(url_for('admin.outlet_list'))
    
    return render_template('admin/outlet_form.html')

@admin_bp.route('/outlets/edit/<int:outlet_id>', methods=['GET', 'POST'])
@admin_required
def outlet_edit(outlet_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        
        if request.method == 'POST':
            form_data = {
                'urn': request.form.get('urn', '').strip(),
                'outlet_name': request.form.get('outlet_name', '').strip(),
                'customer_name': request.form.get('customer_name', '').strip(),
                'address': request.form.get('address', '').strip(),
                'phone': request.form.get('phone', '').strip(),
                'outlet_type': request.form.get('outlet_type', '').strip(),
                'local_govt': request.form.get('local_govt', '').strip(),
                'state': request.form.get('state', '').strip(),
                'region': request.form.get('region', '').strip()
            }
            
            # Validate required fields
            if not all(form_data[field] for field in ['urn', 'outlet_name', 'region']):
                flash('URN, Retail Point Name and Region are required', 'danger')
                c.execute("SELECT * FROM outlets WHERE id = ?", (outlet_id,))
                outlet = c.fetchone()
                return render_template('admin/outlet_form.html', outlet=outlet)
            
            # Check if URN exists on another outlet
            c.execute("SELECT id FROM outlets WHERE urn = ? AND id != ?", (form_data['urn'], outlet_id))
            if c.fetchone():
                flash('URN already exists on another outlet', 'danger')
                c.execute("SELECT * FROM outlets WHERE id = ?", (outlet_id,))
                outlet = c.fetchone()
                return render_template('admin/outlet_form.html', outlet=outlet)
            
            # Update outlet
            c.execute('''
            UPDATE outlets 
            SET urn = ?, outlet_name = ?, customer_name = ?, address = ?, phone = ?, outlet_type = ?, 
            local_govt = ?, state = ?, region = ?
            WHERE id = ?
            ''', (*form_data.values(), outlet_id))
            
            conn.commit()
            flash('Outlet updated successfully', 'success')
            return redirect(url_for('admin.outlet_list'))
        
        # Get outlet for editing
        c.execute("SELECT * FROM outlets WHERE id = ?", (outlet_id,))
        outlet = c.fetchone()
        
        if not outlet:
            flash('Outlet not found', 'danger')
            return redirect(url_for('admin.outlet_list'))
    
    return render_template('admin/outlet_form.html', outlet=outlet)

@admin_bp.route('/outlets/delete/<int:outlet_id>', methods=['POST'])
@admin_required
def outlet_delete(outlet_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # Check if outlet has executions
        c.execute("SELECT COUNT(*) FROM executions WHERE outlet_id = ?", (outlet_id,))
        execution_count = c.fetchone()[0]
        
        if execution_count > 0:
            flash(f'Cannot delete outlet with {execution_count} executions', 'danger')
            return redirect(url_for('admin.outlet_list'))
        
        # Delete outlet
        c.execute("DELETE FROM outlets WHERE id = ?", (outlet_id,))
        conn.commit()
    
    flash('Outlet deleted successfully', 'success')
    return redirect(url_for('admin.outlet_list'))

@admin_bp.route('/outlets/import', methods=['GET', 'POST'])
@admin_required
def outlet_import():
    if request.method == 'POST':
        file = request.files.get('csv_file')
        is_valid, error_msg = validate_file_upload(file)
        
        if not is_valid:
            flash(error_msg, 'danger')
            return redirect(request.url)
        
        data, error_msg = process_csv_data(file, REQUIRED_OUTLET_FIELDS, OPTIONAL_OUTLET_FIELDS)
        if error_msg:
            flash(error_msg, 'danger')
            return redirect(request.url)
        
        with get_db_connection() as conn:
            c = conn.cursor()
            success_count = update_count = error_count = 0
            
            for row in data:
                try:
                    # Check if outlet with URN exists
                    c.execute("SELECT id FROM outlets WHERE urn = ?", (row['urn'],))
                    existing = c.fetchone()
                    
                    if existing:
                        # Update existing outlet
                        c.execute('''
                        UPDATE outlets 
                        SET outlet_name = ?, customer_name = ?, address = ?, phone = ?, outlet_type = ?, 
                        local_govt = ?, state = ?, region = ?
                        WHERE urn = ?
                        ''', (row['outlet_name'], row.get('customer_name', ''), row.get('address', ''), 
                             row.get('phone', ''), row.get('outlet_type', ''), row.get('local_govt', ''), 
                             row.get('state', ''), row['region'], row['urn']))
                        update_count += 1
                    else:
                        # Insert new outlet
                        c.execute('''
                        INSERT INTO outlets (urn, outlet_name, customer_name, address, phone, outlet_type, local_govt, state, region)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (row['urn'], row['outlet_name'], row.get('customer_name', ''), 
                             row.get('address', ''), row.get('phone', ''), row.get('outlet_type', ''), 
                             row.get('local_govt', ''), row.get('state', ''), row['region']))
                        success_count += 1
                
                except Exception as e:
                    print(f"Error processing row: {str(e)}")
                    error_count += 1
            
            conn.commit()
        
        flash(f'Imported {success_count} new outlets, updated {update_count}, {error_count} errors', 'success')
        return redirect(url_for('admin.outlet_list'))
    
    # Provide a sample CSV template
    sample_data = [
        ['urn', 'outlet_name', 'customer_name', 'address', 'phone', 'outlet_type', 'local_govt', 'state', 'region'],
        ['DCP/22/SW/ED/1000009', 'SAMPLE OUTLET', 'JOHN DOE', '123 SAMPLE STREET', '08012345678', 'Shop', 'EGOR', 'EDO', 'SW']
    ]
    
    return render_template('admin/outlet_import.html', sample_data=sample_data)

# Bulk Outlet Operations
@admin_bp.route('/outlets/bulk_manage')
@admin_required
def outlet_bulk_manage():
    return render_template('admin/outlet_bulk_manage.html')

@admin_bp.route('/outlets/preview')
@admin_required
def outlet_preview():
    delete_by = request.args.get('delete_by')
    value = request.args.get('value')
    
    if not delete_by or not value:
        return jsonify({'outlets': []})
    
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # Build query based on filter
        query = '''
        SELECT o.*, COUNT(e.id) as executions 
        FROM outlets o 
        LEFT JOIN executions e ON o.id = e.outlet_id
        WHERE o.{} = ?
        GROUP BY o.id
        '''.format(delete_by)
        
        c.execute(query, (value,))
        outlets = [dict(row) for row in c.fetchall()]
    
    return jsonify({'outlets': outlets})

@admin_bp.route('/outlets/bulk_delete', methods=['POST'])
@admin_required
def outlet_bulk_delete():
    delete_by = request.form.get('delete_by')
    value = request.form.get(delete_by) if delete_by in ['region', 'state', 'local_govt'] else None
    
    if not delete_by or not value:
        flash('Invalid criteria or no value specified', 'danger')
        return redirect(url_for('admin.outlet_bulk_manage'))
    
    # Build skip conditions
    skip_conditions = []
    if 'skip_with_executions' in request.form:
        skip_conditions.append("id NOT IN (SELECT DISTINCT outlet_id FROM executions)")
    
    try:
        deleted_count, error_msg = bulk_delete_records('outlets', delete_by, value, skip_conditions)
        if error_msg:
            flash(error_msg, 'warning')
        else:
            flash(f'Successfully deleted {deleted_count} outlets', 'success')
    except Exception as e:
        flash(f'Error during bulk delete: {str(e)}', 'danger')
    
    return redirect(url_for('admin.outlet_list'))

# Profile management routes
@admin_bp.route('/profile')
@admin_required
def profile_settings():
    """Display profile settings page"""
    from pykes.models import get_profile
    
    profile = get_profile()
    if not profile:
        # Create default profile if none exists
        profile = {
            'company_name': 'DANGOTE',
            'app_title': 'POSM Retail Activation 2025',
            'primary_color': '#fdcc03',
            'secondary_color': '#f8f9fa',
            'accent_color': '#343a40',
            'logo_path': 'img/dangote-logo.png',
            'favicon_path': 'img/favicon.png',
            'address': '',
            'phone': '',
            'email': '',
            'footer_text': ''
        }
    
    return render_template('admin/profile_settings.html', profile=profile)

@admin_bp.route('/profile/update', methods=['POST'])
@admin_required
def profile_update():
    """Update profile settings"""
    from pykes.models import update_profile
    
    try:
        profile_data = {
            'company_name': request.form.get('company_name', '').strip(),
            'app_title': request.form.get('app_title', '').strip(),
            'primary_color': request.form.get('primary_color', '#fdcc03').strip(),
            'secondary_color': request.form.get('secondary_color', '#f8f9fa').strip(),
            'accent_color': request.form.get('accent_color', '#343a40').strip(),
            'logo_path': request.form.get('logo_path', 'img/dangote-logo.png').strip(),
            'favicon_path': request.form.get('favicon_path', 'img/favicon.png').strip(),
            'address': request.form.get('address', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'email': request.form.get('email', '').strip(),
            'footer_text': request.form.get('footer_text', '').strip()
        }
        
        # Validate required fields
        if not profile_data['company_name']:
            flash('Company name is required', 'danger')
            return redirect(url_for('admin.profile_settings'))
            
        if not profile_data['app_title']:
            flash('App title is required', 'danger')
            return redirect(url_for('admin.profile_settings'))
        
        # Validate color formats (basic hex validation)
        color_fields = ['primary_color', 'secondary_color', 'accent_color']
        for field in color_fields:
            color = profile_data[field]
            if not color.startswith('#') or len(color) != 7:
                flash(f'Invalid color format for {field.replace("_", " ").title()}. Use hex format like #fdcc03', 'danger')
                return redirect(url_for('admin.profile_settings'))
        
        success = update_profile(profile_data)
        
        if success:
            flash('Profile settings updated successfully!', 'success')
        else:
            flash('Failed to update profile settings', 'danger')
            
    except Exception as e:
        flash(f'Error updating profile: {str(e)}', 'danger')
    
    return redirect(url_for('admin.profile_settings'))

# Execution Management
@admin_bp.route('/executions')
@admin_required
def execution_list():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''
        SELECT e.id, e.execution_date, o.outlet_name, o.region, o.state, u.full_name as agent_name, e.status
        FROM executions e
        JOIN outlets o ON e.outlet_id = o.id
        JOIN users u ON e.agent_id = u.id
        ORDER BY e.execution_date DESC
        ''')
        executions = c.fetchall()
    
    return render_template('admin/execution_list.html', executions=executions)

@admin_bp.route('/executions/delete/<int:execution_id>', methods=['POST'])
@admin_required
def execution_delete(execution_id):
    with get_db_connection() as conn:
        c = conn.cursor()
        
        # Get execution details to delete images
        c.execute("SELECT before_image, after_image FROM executions WHERE id = ?", (execution_id,))
        execution = c.fetchone()
        
        if execution:
            # Delete execution record
            c.execute("DELETE FROM executions WHERE id = ?", (execution_id,))
            conn.commit()
            
            # Delete associated images
            upload_folder = os.path.join(current_app.static_folder, 'uploads')
            
            for image_field in ['before_image', 'after_image']:
                image_name = execution[image_field]
                if image_name:
                    image_path = os.path.join(upload_folder, image_name)
                    if os.path.exists(image_path):
                        try:
                            os.remove(image_path)
                        except OSError:
                            pass  # Ignore file deletion errors
            
            flash('Execution deleted successfully', 'success')
        else:
            flash('Execution not found', 'danger')
    
    return redirect(url_for('admin.execution_list'))

@admin_bp.route('/executions/upload', methods=['GET', 'POST'])
@admin_required
def execution_upload():
    """Enhanced execution upload with automatic outlet creation"""
    if request.method == 'GET':
        return render_template('admin/execution_upload.html')

    file = request.files.get('file')
    if not file or not file.filename:
        flash('No file selected', 'danger')
        return redirect(request.url)
    
    # Validate file type - support Excel and CSV
    allowed_extensions = ['.csv', '.xlsx', '.xls']
    file_ext = os.path.splitext(file.filename.lower())[1]
    if file_ext not in allowed_extensions:
        flash(f'Invalid file type. Allowed: {", ".join(allowed_extensions)}', 'danger')
        return redirect(request.url)

    try:
        # Read the uploaded file into a DataFrame
        if file_ext == '.csv':
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        # Print columns for debugging
        current_app.logger.info(f"File columns: {list(df.columns)}")
        print(f"Excel columns detected: {list(df.columns)}")

        # Clean column names (remove extra spaces, standardize)
        df.columns = df.columns.str.strip()
        
        # Create column mapping for flexibility
        column_mapping = {
            'URN': ['URN', 'urn', 'Urn', 'URN Code', 'Outlet URN'],
            'Retail Point Name': ['Retail Point Name', 'Outlet Name', 'Shop Name', 'Point Name', 'Name'],
            'Customer Name': ['Customer Name', 'Customer', 'Owner Name', 'Owner'],
            'Address': ['Address', 'Location', 'Full Address'],
            'Phone': ['Phone', 'Phone Number', 'Contact', 'Mobile'],
            'Region': ['Region', 'Zone'],
            'State': ['State'],
            'LGA': ['LGA', 'Local Govt', 'Local Government', 'Local Government Area'],
            'Outlet Type': ['Outlet Type', 'Type', 'Shop Type'],
            'Date': ['Date', 'Execution Date', 'Visit Date'],
            'Status': ['Status', 'Execution Status'],
            'Notes': ['Notes', 'Comments', 'Remarks'],
            'Table': ['Table'],
            'Chair': ['Chair'],
            'Parasol': ['Parasol'],
            'Tarpaulin': ['Tarpaulin'],
            'Hawker Jacket': ['Hawker Jacket']
        }
        
        # Map columns dynamically
        mapped_columns = {}
        for standard_col, possible_cols in column_mapping.items():
            for col in possible_cols:
                if col in df.columns:
                    mapped_columns[standard_col] = col
                    break
        
        # Validate minimal required columns
        required_columns = ['URN', 'Retail Point Name']
        missing_cols = [col for col in required_columns if col not in mapped_columns]
        if missing_cols:
            available_cols = list(df.columns)
            flash(f"Missing required columns: {', '.join(missing_cols)}. Available columns: {', '.join(available_cols)}", 'danger')
            return redirect(request.url)

        # Convert the DataFrame to a list of dicts with mapped columns
        execution_data = []
        for _, row in df.iterrows():
            mapped_row = {}
            for std_col, file_col in mapped_columns.items():
                mapped_row[std_col] = row.get(file_col, '')
            execution_data.append(mapped_row)

        imported = skipped = outlets_created = 0
        errors = []
        duplicates = []
        new_outlets = []

        with get_db_connection() as conn:
            cursor = conn.cursor()

            for i, row in enumerate(execution_data):
                try:
                    urn = str(row.get('URN', '')).strip()
                    outlet_name = str(row.get('Retail Point Name', '')).strip()
                    
                    if not urn or not outlet_name:
                        errors.append({
                            'row': i + 1,
                            'error': f"Missing required data - URN: '{urn}', Outlet Name: '{outlet_name}'"
                        })
                        continue

                    # Check for existing execution in last 7 days (skip duplicate check for new outlets)
                    if 'new' not in urn.lower():
                        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                        cursor.execute('''
                            SELECT COUNT(*) FROM executions e
                            JOIN outlets o ON e.outlet_id = o.id
                            WHERE (o.urn = ? OR o.outlet_name = ?)
                            AND e.execution_date >= ?
                        ''', (urn, outlet_name, seven_days_ago))
                        
                        if cursor.fetchone()[0] > 0:
                            duplicates.append({
                                'row': i + 1,
                                'message': f"Duplicate entry - URN '{urn}' or outlet name '{outlet_name}' has an execution in the last 7 days"
                            })
                            skipped += 1
                            continue

                    # Get or create outlet
                    outlet_id = None
                    
                    # Check if outlet exists
                    cursor.execute('SELECT id FROM outlets WHERE urn = ?', (urn,))
                    outlet = cursor.fetchone()
                    
                    if outlet:
                        outlet_id = outlet[0]
                    elif 'new' in urn.lower() or not outlet:
                        # Create new outlet
                        try:
                            new_outlet_data = {
                                'urn': urn,
                                'outlet_name': outlet_name,
                                'customer_name': str(row.get('Customer Name', '')).strip(),
                                'address': str(row.get('Address', '')).strip(),
                                'phone': str(row.get('Phone', '')).strip(),
                                'outlet_type': str(row.get('Outlet Type', 'Shop')).strip(),
                                'local_govt': str(row.get('LGA', '')).strip(),
                                'state': str(row.get('State', '')).strip(),
                                'region': str(row.get('Region', 'SW')).strip()  # Default to SW if not provided
                            }
                            
                            # Validate required outlet fields
                            if not new_outlet_data['region']:
                                new_outlet_data['region'] = 'SW'  # Default region
                            
                            cursor.execute('''
                                INSERT INTO outlets (
                                    urn, outlet_name, customer_name, address, phone,
                                    outlet_type, local_govt, state, region
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                new_outlet_data['urn'],
                                new_outlet_data['outlet_name'],
                                new_outlet_data['customer_name'],
                                new_outlet_data['address'],
                                new_outlet_data['phone'],
                                new_outlet_data['outlet_type'],
                                new_outlet_data['local_govt'],
                                new_outlet_data['state'],
                                new_outlet_data['region']
                            ))
                            
                            outlet_id = cursor.lastrowid
                            outlets_created += 1
                            
                            new_outlets.append({
                                'row': i + 1,
                                'urn': urn,
                                'name': outlet_name,
                                'region': new_outlet_data['region']
                            })
                            
                            current_app.logger.info(f"Created new outlet: URN={urn}, Name={outlet_name}")
                            
                        except Exception as outlet_error:
                            errors.append({
                                'row': i + 1,
                                'error': f"Failed to create outlet for URN '{urn}': {str(outlet_error)}"
                            })
                            continue
                    
                    if not outlet_id:
                        errors.append({
                            'row': i + 1,
                            'error': f"Could not find or create outlet for URN '{urn}'"
                        })
                        continue

                    # Get agent (prefer admin, fallback to first available user)
                    cursor.execute("SELECT id FROM users WHERE role = 'admin' AND is_active = 1 LIMIT 1")
                    agent = cursor.fetchone()
                    

                    # "SELECT id FROM users WHERE is_active = 1 LIMIT 1"
                    if not agent:
                        cursor.execute("SELECT id FROM users WHERE is_active = 1 LIMIT 1")
                        agent = cursor.fetchone()
                    
                    if not agent:
                        raise ValueError("No active user found to assign as agent")

                    agent_id = agent[0]
                    
                    # Parse execution date
                    execution_date_str = str(row.get('Date', '')).strip()
                    if execution_date_str:
                        try:
                            # Try different date formats
                            for date_format in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S']:
                                try:
                                    execution_date = datetime.strptime(execution_date_str, date_format)
                                    break
                                except ValueError:
                                    continue
                            else:
                                execution_date = datetime.now()
                        except:
                            execution_date = datetime.now()
                    else:
                        execution_date = datetime.now()
                    
                    execution_date_formatted = execution_date.strftime('%Y-%m-%d %H:%M:%S')
                    status = str(row.get('Status', 'Completed')).strip()
                    notes = str(row.get('Notes', '')).strip()

                    # Parse products availability
                    products_available = {}
                    for product in ['Table', 'Chair', 'Parasol', 'Tarpaulin', 'Hawker Jacket']:
                        product_value = str(row.get(product, '')).strip().lower()
                        products_available[product] = product_value in ['true', '1', 'yes', 'y', 'available', 'present']

                    # Insert execution
                    cursor.execute('''
                        INSERT INTO executions (
                            outlet_id, agent_id, execution_date,
                            status, notes, products_available
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        outlet_id, agent_id, execution_date_formatted,
                        status, notes, json.dumps(products_available)
                    ))

                    imported += 1
                    current_app.logger.info(f"Imported execution for URN {urn} (row {i+1})")

                except Exception as e:
                    error_msg = f"Row {i + 1}: {str(e)}"
                    errors.append({'row': i + 1, 'error': str(e)})
                    current_app.logger.error(error_msg)

            conn.commit()

        # Create uploads directory with Windows-compatible path
        uploads_dir = os.path.join(os.getcwd(), 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Save duplicates to file if any
        if duplicates:
            duplicates_file = os.path.join(uploads_dir, 'duplicates.txt')
            with open(duplicates_file, 'w', encoding='utf-8') as f:
                f.write("\n".join([f"Row {d['row']}: {d['message']}" for d in duplicates]))
            flash(f'{len(duplicates)} duplicates detected in the last 7 days. See {duplicates_file} for details.', 'warning')
        
        # Save new outlets info if any
        if new_outlets:
            new_outlets_file = os.path.join(uploads_dir, 'new_outlets.txt')
            with open(new_outlets_file, 'w', encoding='utf-8') as f:
                f.write("New outlets created:\n")
                for outlet in new_outlets:
                    f.write(f"Row {outlet['row']}: URN={outlet['urn']}, Name={outlet['name']}, Region={outlet['region']}\n")
            flash(f'{outlets_created} new outlets created. See {new_outlets_file} for details.', 'info')
        
        # Save errors to file if any
        if errors:
            errors_file = os.path.join(uploads_dir, 'import_errors.txt')
            with open(errors_file, 'w', encoding='utf-8') as f:
                f.write("Import errors:\n")
                for error in errors:
                    f.write(f"Row {error['row']}: {error['error']}\n")
            flash(f'{len(errors)} errors occurred during import. See {errors_file} for details.', 'danger')

        # Flash comprehensive summary message
        summary_parts = []
        if imported > 0:
            summary_parts.append(f'{imported} executions imported')
        if outlets_created > 0:
            summary_parts.append(f'{outlets_created} outlets created')
        if skipped > 0:
            summary_parts.append(f'{skipped} duplicates skipped')
        if errors:
            summary_parts.append(f'{len(errors)} errors')
        
        summary = 'Upload complete: ' + ', '.join(summary_parts) if summary_parts else 'No data processed'
        flash(summary, 'success' if imported > 0 or outlets_created > 0 else 'warning')

        return redirect(url_for('admin.execution_list'))

    except Exception as e:
        current_app.logger.error(f"Error processing file {file.filename}: {str(e)}")
        flash(f"Error processing file: {str(e)}", 'danger')
        return redirect(request.url)

# ===== DATABASE MANAGEMENT INTERFACE =====

# Special decorator for database management access
def db_management_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # First check admin access
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('login'))
        
        # Then check for database management session
        if not session.get('db_management_authenticated', False):
            return redirect(url_for('admin.db_management_auth'))
        
        return f(*args, **kwargs)
    return decorated_function

def hash_password(password):
    """Simple password hashing for database access"""
    return hashlib.sha256(password.encode()).hexdigest()

# Database Management Authentication
@admin_bp.route('/db-management/auth', methods=['GET', 'POST'])
@admin_required
def db_management_auth():
    """Special authentication for database management interface"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        
        # Check the special password
        if password == 'brobotDevMadeThisallTime123?':
            session['db_management_authenticated'] = True
            flash('Database management access granted', 'success')
            return redirect(url_for('admin.db_management_dashboard'))
        else:
            flash('Invalid database management password', 'danger')
    
    return render_template('admin/db_auth.html')

@admin_bp.route('/db-management/logout')
@admin_required
def db_management_logout():
    """Logout from database management"""
    session.pop('db_management_authenticated', None)
    flash('Database management access revoked', 'info')
    return redirect(url_for('admin.admin_dashboard'))

# Database Management Dashboard
@admin_bp.route('/db-management')
@db_management_required
def db_management_dashboard():
    """Database management dashboard"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Get table statistics
        table_stats = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            
            # Get table info
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            
            table_stats[table] = {
                'count': count,
                'columns': len(columns),
                'column_names': [col[1] for col in columns]
            }
    
    return render_template('admin/db_management_dashboard.html', 
                         tables=tables, table_stats=table_stats)

# Database Table Viewer
@admin_bp.route('/db-management/table/<table_name>')
@db_management_required
def db_table_view(table_name):
    """View table data with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 100, type=int)
    search = request.args.get('search', '', type=str)
    sort_by = request.args.get('sort_by', '', type=str)
    order = request.args.get('order', 'ASC', type=str)
    
    # Validate per_page options
    if per_page not in [10, 25, 50, 100, 200, 500]:
        per_page = 100
    
    # Validate order
    if order.upper() not in ['ASC', 'DESC']:
        order = 'ASC'
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Verify table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                flash(f'Table {table_name} does not exist', 'danger')
                return redirect(url_for('admin.db_management_dashboard'))
            
            # Get table structure
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            column_types = {col[1]: col[2] for col in columns}
            
            # Validate sort_by column
            if sort_by and sort_by not in column_names:
                sort_by = ''
            
            # Build base query
            base_query = f"SELECT * FROM {table_name}"
            params = []
            
            # Add search if provided
            if search:
                search_conditions = []
                for col in column_names:
                    search_conditions.append(f"{col} LIKE ?")
                    params.append(f"%{search}%")
                base_query += " WHERE " + " OR ".join(search_conditions)
            
            # Add sorting
            if sort_by:
                base_query += f" ORDER BY {sort_by} {order}"
            elif 'id' in column_names:
                base_query += f" ORDER BY id {order}"
            
            # Get total count
            count_query = f"SELECT COUNT(*) FROM ({base_query})"
            cursor.execute(count_query, params)
            total_records = cursor.fetchone()[0]
            
            # Calculate pagination
            total_pages = math.ceil(total_records / per_page)
            offset = (page - 1) * per_page
            
            # Get paginated results
            paginated_query = f"{base_query} LIMIT ? OFFSET ?"
            cursor.execute(paginated_query, params + [per_page, offset])
            records = cursor.fetchall()
            
            # Convert to list of dicts for easier template handling
            data = []
            for record in records:
                row_dict = {}
                for i, col_name in enumerate(column_names):
                    row_dict[col_name] = record[i]
                data.append(row_dict)
    
    except Exception as e:
        flash(f'Error accessing table {table_name}: {str(e)}', 'danger')
        return redirect(url_for('admin.db_management_dashboard'))
    
    return render_template('admin/db_table_view.html',
                         table_name=table_name,
                         columns=column_names,
                         column_types=column_types,
                         data=data,
                         page=page,
                         per_page=per_page,
                         total_records=total_records,
                         total_pages=total_pages,
                         search=search,
                         sort_by=sort_by,
                         order=order)

# Database Record Edit
@admin_bp.route('/db-management/table/<table_name>/edit/<int:record_id>', methods=['GET', 'POST'])
@db_management_required
def db_record_edit(table_name, record_id):
    """Edit a database record"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get table structure
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            column_info = {col[1]: {'type': col[2], 'pk': col[5] == 1, 'not_null': col[3] == 1} for col in columns}
            
            if request.method == 'POST':
                # Get form data
                update_data = {}
                for col_name in column_info.keys():
                    if not column_info[col_name]['pk']:  # Don't update primary key
                        update_data[col_name] = request.form.get(col_name, '')
                
                # Build update query
                set_clauses = [f"{col} = ?" for col in update_data.keys()]
                update_query = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE id = ?"
                
                cursor.execute(update_query, list(update_data.values()) + [record_id])
                conn.commit()
                
                flash(f'Record {record_id} updated successfully', 'success')
                return redirect(url_for('admin.db_table_view', table_name=table_name))
            
            # Get current record
            cursor.execute(f"SELECT * FROM {table_name} WHERE id = ?", (record_id,))
            record = cursor.fetchone()
            
            if not record:
                flash(f'Record {record_id} not found in table {table_name}', 'danger')
                return redirect(url_for('admin.db_table_view', table_name=table_name))
            
            # Convert to dict
            record_data = {}
            column_names = [col[1] for col in columns]
            for i, col_name in enumerate(column_names):
                record_data[col_name] = record[i]
    
    except Exception as e:
        flash(f'Error editing record: {str(e)}', 'danger')
        return redirect(url_for('admin.db_table_view', table_name=table_name))
    
    return render_template('admin/db_record_edit.html',
                         table_name=table_name,
                         record_id=record_id,
                         record_data=record_data,
                         column_info=column_info)

# Database Record Create
@admin_bp.route('/db-management/table/<table_name>/create', methods=['GET', 'POST'])
@db_management_required
def db_record_create(table_name):
    """Create a new database record"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get table structure
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            column_info = {col[1]: {'type': col[2], 'pk': col[5] == 1, 'not_null': col[3] == 1, 'default': col[4]} for col in columns}
            
            if request.method == 'POST':
                # Get form data
                insert_data = {}
                for col_name, col_props in column_info.items():
                    if not col_props['pk'] or col_props['pk'] and request.form.get(col_name):  # Skip auto-increment PKs unless provided
                        insert_data[col_name] = request.form.get(col_name, '')
                
                # Build insert query
                columns_list = list(insert_data.keys())
                placeholders = ['?' for _ in columns_list]
                insert_query = f"INSERT INTO {table_name} ({', '.join(columns_list)}) VALUES ({', '.join(placeholders)})"
                
                cursor.execute(insert_query, list(insert_data.values()))
                conn.commit()
                
                new_id = cursor.lastrowid
                flash(f'New record created with ID {new_id}', 'success')
                return redirect(url_for('admin.db_table_view', table_name=table_name))
    
    except Exception as e:
        flash(f'Error creating record: {str(e)}', 'danger')
        return redirect(url_for('admin.db_table_view', table_name=table_name))
    
    return render_template('admin/db_record_create.html',
                         table_name=table_name,
                         column_info=column_info)

# Database Record Delete
@admin_bp.route('/db-management/table/<table_name>/delete/<int:record_id>', methods=['POST'])
@db_management_required
def db_record_delete(table_name, record_id):
    """Delete a database record"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Prevent deletion of current user
            if table_name == 'users' and record_id == session.get('user_id'):
                flash('Cannot delete your own user account', 'danger')
                return redirect(url_for('admin.db_table_view', table_name=table_name))
            
            cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (record_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                flash(f'Record {record_id} deleted successfully', 'success')
            else:
                flash(f'Record {record_id} not found', 'warning')
    
    except Exception as e:
        flash(f'Error deleting record: {str(e)}', 'danger')
    
    return redirect(url_for('admin.db_table_view', table_name=table_name))

# Bulk Operations
@admin_bp.route('/db-management/table/<table_name>/bulk-delete', methods=['POST'])
@db_management_required
def db_bulk_delete(table_name):
    """Bulk delete selected records"""
    selected_ids = request.form.getlist('selected_records')
    
    if not selected_ids:
        flash('No records selected', 'warning')
        return redirect(url_for('admin.db_table_view', table_name=table_name))
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Prevent deletion of current user
            if table_name == 'users' and str(session.get('user_id')) in selected_ids:
                selected_ids = [id for id in selected_ids if int(id) != session.get('user_id')]
                flash('Skipped deletion of your own user account', 'warning')
            
            if not selected_ids:
                flash('No valid records to delete', 'warning')
                return redirect(url_for('admin.db_table_view', table_name=table_name))
            
            # Delete records
            placeholders = ','.join(['?' for _ in selected_ids])
            cursor.execute(f"DELETE FROM {table_name} WHERE id IN ({placeholders})", selected_ids)
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            flash(f'Successfully deleted {deleted_count} records', 'success')
    
    except Exception as e:
        flash(f'Error during bulk delete: {str(e)}', 'danger')
    
    return redirect(url_for('admin.db_table_view', table_name=table_name))

# Table Management
@admin_bp.route('/db-management/table/<table_name>/truncate', methods=['POST'])
@db_management_required
def db_table_truncate(table_name):
    """Truncate (delete all data from) a table"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get record count first
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            
            if count == 0:
                flash(f'Table {table_name} is already empty', 'info')
                return redirect(url_for('admin.db_table_view', table_name=table_name))
            
            # Prevent truncating users table if it would delete current user
            if table_name == 'users':
                cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE id != ?", (session.get('user_id'),))
                safe_delete_count = cursor.fetchone()[0]
                if safe_delete_count == 0:
                    flash('Cannot truncate users table - would delete your own account', 'danger')
                    return redirect(url_for('admin.db_table_view', table_name=table_name))
            
            # Delete all records
            cursor.execute(f"DELETE FROM {table_name}")
            
            # Reset auto-increment counter
            cursor.execute("DELETE FROM sqlite_sequence WHERE name=?", (table_name,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            flash(f'Successfully truncated table {table_name} - deleted {deleted_count} records', 'success')
    
    except Exception as e:
        flash(f'Error truncating table {table_name}: {str(e)}', 'danger')
    
    return redirect(url_for('admin.db_table_view', table_name=table_name))

# SQL Query Interface
@admin_bp.route('/db-management/sql-query', methods=['GET', 'POST'])
@db_management_required
def db_sql_query():
    """Execute custom SQL queries"""
    results = None
    error = None
    query = ''
    
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        
        if not query:
            flash('Please enter a SQL query', 'warning')
        else:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Execute query
                    cursor.execute(query)
                    
                    # Check if it's a SELECT query
                    if query.strip().upper().startswith('SELECT'):
                        results = cursor.fetchall()
                        # Get column names
                        columns = [description[0] for description in cursor.description] if cursor.description else []
                        
                        # Convert to list of dicts
                        if results and columns:
                            results = [dict(zip(columns, row)) for row in results]
                        
                        flash(f'Query executed successfully. {len(results)} rows returned.', 'success')
                    else:
                        # For non-SELECT queries
                        affected_rows = cursor.rowcount
                        conn.commit()
                        flash(f'Query executed successfully. {affected_rows} rows affected.', 'success')
            
            except Exception as e:
                error = str(e)
                flash(f'SQL Error: {error}', 'danger')
    
    return render_template('admin/db_sql_query.html',
                         query=query,
                         results=results,
                         error=error)

# Database Export
@admin_bp.route('/db-management/export/<table_name>')
@db_management_required
def db_export_table(table_name):
    """Export table data to CSV"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get all data
            cursor.execute(f"SELECT * FROM {table_name}")
            data = cursor.fetchall()
            
            # Get column names
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(column_names)
            
            # Write data
            for row in data:
                writer.writerow(row)
            
            # Prepare response
            csv_data = output.getvalue()
            output.close()
            
            # Create response
            response = current_app.response_class(
                csv_data,
                mimetype='text/csv',
                headers={"Content-disposition": f"attachment; filename={table_name}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
            )
            
            return response
    
    except Exception as e:
        flash(f'Error exporting table {table_name}: {str(e)}', 'danger')
        return redirect(url_for('admin.db_table_view', table_name=table_name))

# Database Information
@admin_bp.route('/db-management/info')
@db_management_required
def db_info():
    """Show database information and statistics"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Database file info
            import os
            db_path = 'maindatabase.db'
            db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
            db_size_mb = db_size / (1024 * 1024)
            
            # Get SQLite version
            cursor.execute("SELECT sqlite_version()")
            sqlite_version = cursor.fetchone()[0]
            
            # Get page count and size
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            
            # Get all tables with their info
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            
            table_info = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                
                table_info[table] = {
                    'count': count,
                    'columns': len(columns),
                    'column_details': columns
                }
            
            # Get indexes
            cursor.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' ORDER BY tbl_name, name")
            indexes = cursor.fetchall()
            
            db_stats = {
                'file_size': db_size,
                'file_size_mb': db_size_mb,
                'sqlite_version': sqlite_version,
                'page_count': page_count,
                'page_size': page_size,
                'total_pages_mb': (page_count * page_size) / (1024 * 1024)
            }
    
    except Exception as e:
        flash(f'Error getting database info: {str(e)}', 'danger')
        return redirect(url_for('admin.db_management_dashboard'))
    
    return render_template('admin/db_info.html',
                         db_stats=db_stats,
                         table_info=table_info,
                         indexes=indexes)
