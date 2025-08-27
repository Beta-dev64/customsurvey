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

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Helper functions
def get_db_connection():
    conn = sqlite3.connect('maindatabase.db')
    conn.row_factory = sqlite3.Row
    return conn

def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin dashboard
@admin_bp.route('/')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get counts for dashboard
    c.execute("SELECT COUNT(*) FROM users")
    user_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM outlets")
    outlet_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM executions")
    execution_count = c.fetchone()[0]
    
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
    
    conn.close()
    
    return render_template('admin/dashboard.html', 
                           user_count=user_count, 
                           outlet_count=outlet_count, 
                           execution_count=execution_count,
                           recent_activity=recent_activity)

# User management
@admin_bp.route('/users')
@admin_required
def user_list():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get all users
    c.execute("SELECT * FROM users ORDER BY username")
    users = c.fetchall()
    
    conn.close()
    
    return render_template('admin/user_list.html', users=users)

@admin_bp.route('/users/new', methods=['GET', 'POST'])
@admin_required
def user_new():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        role = request.form.get('role')
        region = request.form.get('region')
        state = request.form.get('state')
        lga = request.form.get('lga')
        
        # Validate input
        if not username or not password or not full_name or not role:
            flash('All fields are required', 'danger')
            return render_template('admin/user_form.html')
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Check if username already exists
        c.execute("SELECT id FROM users WHERE username = ?", (username,))
        if c.fetchone():
            flash('Username already exists', 'danger')
            conn.close()
            return render_template('admin/user_form.html')
        
        # Insert new user
        c.execute('''
        INSERT INTO users (username, password, full_name, role, region, state, lga)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (username, password, full_name, role, region, state, lga))
        
        conn.commit()
        conn.close()
        
        flash('User created successfully', 'success')
        return redirect(url_for('admin.user_list'))
    
    return render_template('admin/user_form.html')

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def user_edit(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    
    if request.method == 'POST':
        # Don't allow editing the admin user
        if user_id == session['user_id'] and session['role'] == 'admin':
            if request.form.get('role') != 'admin':
                flash('Cannot change your own admin role', 'danger')
                return redirect(url_for('admin.user_list'))
        
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        role = request.form.get('role')
        region = request.form.get('region')
        state = request.form.get('state')
        lga = request.form.get('lga')
        
        # Update user details
        if password:  # Only update password if provided
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
    
    conn.close()
    
    return render_template('admin/user_form.html', user=user)

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def user_delete(user_id):
    # Don't allow deleting self
    if user_id == session['user_id']:
        flash('Cannot delete your own account', 'danger')
        return redirect(url_for('admin.user_list'))
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check if user has executions
    c.execute("SELECT COUNT(*) FROM executions WHERE agent_id = ?", (user_id,))
    execution_count = c.fetchone()[0]
    
    if execution_count > 0:
        flash(f'Cannot delete user with {execution_count} executions', 'danger')
        conn.close()
        return redirect(url_for('admin.user_bulk_manage'))
    
    # Delete user
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    flash('User deleted successfully', 'success')
    return redirect(url_for('admin.user_list'))

@admin_bp.route('/users/import', methods=['GET', 'POST'])
@admin_required
def user_import():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file', 'danger')
            return redirect(request.url)
        
        try:
            # Read CSV file
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_data = csv.reader(stream)
            
            # Skip header
            header = next(csv_data)
            
            # Validate header
            required_fields = ['username', 'password', 'full_name', 'role', 'region']
            if not all(field in header for field in required_fields):
                flash(f'CSV file must contain: {", ".join(required_fields)}', 'danger')
                return redirect(request.url)
            
            # Get field indices
            username_idx = header.index('username')
            password_idx = header.index('password')
            full_name_idx = header.index('full_name')
            role_idx = header.index('role')
            region_idx = header.index('region')
            
            # Optional fields
            state_idx = header.index('state') if 'state' in header else -1
            lga_idx = header.index('lga') if 'lga' in header else -1
            
            conn = get_db_connection()
            c = conn.cursor()
            
            success_count = 0
            error_count = 0
            
            for row in csv_data:
                if len(row) < 5:  # Skip incomplete rows
                    continue
                
                username = row[username_idx].strip()
                password = row[password_idx].strip()
                full_name = row[full_name_idx].strip()
                role = row[role_idx].strip()
                region = row[region_idx].strip()
                
                # Optional fields
                state = row[state_idx].strip() if state_idx >= 0 and state_idx < len(row) else ''
                lga = row[lga_idx].strip() if lga_idx >= 0 and lga_idx < len(row) else ''
                
                # Validate role
                if role not in ['admin', 'field_agent']:
                    error_count += 1
                    continue
                
                # Check if username exists
                c.execute("SELECT id FROM users WHERE username = ?", (username,))
                if c.fetchone():
                    error_count += 1
                    continue
                
                # Insert user
                try:
                    c.execute('''
                    INSERT INTO users (username, password, full_name, role, region, state, lga)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (username, password, full_name, role, region, state, lga))
                    success_count += 1
                except Exception as e:
                    print(f"Error inserting user: {str(e)}")
                    error_count += 1
            
            conn.commit()
            conn.close()
            
            flash(f'Imported {success_count} users successfully, {error_count} errors', 'success')
            return redirect(url_for('admin.user_list'))
            
        except Exception as e:
            flash(f'Error processing CSV file: {str(e)}', 'danger')
            return redirect(request.url)
    
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
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Build query based on filter
    query = '''
    SELECT u.*, COUNT(e.id) as executions 
    FROM users u 
    LEFT JOIN executions e ON u.id = e.agent_id
    '''
    
    params = []
    
    if delete_by == 'region':
        query += " WHERE u.region = ?"
        params.append(value)
    elif delete_by == 'state':
        query += " WHERE u.state = ?"
        params.append(value)
    elif delete_by == 'lga':
        query += " WHERE u.lga = ?"
        params.append(value)
    
    query += " GROUP BY u.id"
    
    c.execute(query, params)
    users = [dict(row) for row in c.fetchall()]
    
    conn.close()
    
    return jsonify({'users': users})

@admin_bp.route('/users/bulk_delete', methods=['POST'])
@admin_required
def user_bulk_delete():
    delete_by = request.form.get('delete_by')
    
    # Get value based on delete_by
    if delete_by == 'region':
        value = request.form.get('region')
    elif delete_by == 'state':
        value = request.form.get('state')
    elif delete_by == 'lga':
        value = request.form.get('lga')
    else:
        flash('Invalid criteria', 'danger')
        return redirect(url_for('admin.user_bulk_manage'))
    
    if not value:
        flash('No value specified', 'danger')
        return redirect(url_for('admin.user_bulk_manage'))
    
    # Options
    skip_with_executions = 'skip_with_executions' in request.form
    skip_admins = 'skip_admins' in request.form
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Find users to delete
    query = f"SELECT id FROM users WHERE {delete_by} = ?"
    
    # Additional conditions
    if skip_with_executions:
        query += " AND id NOT IN (SELECT DISTINCT agent_id FROM executions)"
    
    if skip_admins:
        query += " AND role != 'admin'"
    
    # Don't delete current user
    query += f" AND id != {session['user_id']}"
    
    c.execute(query, (value,))
    user_ids = [row[0] for row in c.fetchall()]
    
    if not user_ids:
        flash('No users found matching the criteria or all users have executions/are admins', 'warning')
        conn.close()
        return redirect(url_for('admin.user_bulk_manage'))
    
    # Delete the users
    c.execute(f"DELETE FROM users WHERE id IN ({','.join(['?'] * len(user_ids))})", user_ids)
    
    deleted_count = c.rowcount
    conn.commit()
    conn.close()
    
    flash(f'Successfully deleted {deleted_count} users', 'success')
    return redirect(url_for('admin.user_list'))

# Outlet management
@admin_bp.route('/outlets')
@admin_required
def outlet_list():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get all outlets
    c.execute("SELECT * FROM outlets ORDER BY region, state, local_govt, outlet_name")
    outlets = c.fetchall()
    
    conn.close()
    
    return render_template('admin/outlet_list.html', outlets=outlets)

@admin_bp.route('/outlets/new', methods=['GET', 'POST'])
@admin_required
def outlet_new():
    if request.method == 'POST':
        urn = request.form.get('urn')
        outlet_name = request.form.get('outlet_name')
        customer_name = request.form.get('customer_name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        outlet_type = request.form.get('outlet_type')
        local_govt = request.form.get('local_govt')
        state = request.form.get('state')
        region = request.form.get('region')
        
        # Validate input
        if not urn or not outlet_name or not region:
            flash('URN, Retail Point Name and Region are required', 'danger')
            return render_template('admin/outlet_form.html')
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Check if URN already exists
        c.execute("SELECT id FROM outlets WHERE urn = ?", (urn,))
        if c.fetchone():
            flash('URN already exists', 'danger')
            conn.close()
            return render_template('admin/outlet_form.html')
        
        # Insert new outlet
        c.execute('''
        INSERT INTO outlets (urn, outlet_name, customer_name, address, phone, outlet_type, local_govt, state, region)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (urn, outlet_name, customer_name, address, phone, outlet_type, local_govt, state, region))
        
        conn.commit()
        conn.close()
        
        flash('Outlet created successfully', 'success')
        return redirect(url_for('admin.outlet_list'))
    
    return render_template('admin/outlet_form.html')

@admin_bp.route('/outlets/edit/<int:outlet_id>', methods=['GET', 'POST'])
@admin_required
def outlet_edit(outlet_id):
    conn = get_db_connection()
    c = conn.cursor()
    
    if request.method == 'POST':
        urn = request.form.get('urn')
        outlet_name = request.form.get('outlet_name')
        customer_name = request.form.get('customer_name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        outlet_type = request.form.get('outlet_type')
        local_govt = request.form.get('local_govt')
        state = request.form.get('state')
        region = request.form.get('region')
        
        # Validate input
        if not urn or not outlet_name or not region:
            flash('URN, Retail Point Name and Region are required', 'danger')
            c.execute("SELECT * FROM outlets WHERE id = ?", (outlet_id,))
            outlet = c.fetchone()
            conn.close()
            return render_template('admin/outlet_form.html', outlet=outlet)
        
        # Check if URN exists on another outlet
        c.execute("SELECT id FROM outlets WHERE urn = ? AND id != ?", (urn, outlet_id))
        if c.fetchone():
            flash('URN already exists on another outlet', 'danger')
            c.execute("SELECT * FROM outlets WHERE id = ?", (outlet_id,))
            outlet = c.fetchone()
            conn.close()
            return render_template('admin/outlet_form.html', outlet=outlet)
        
        # Update outlet
        c.execute('''
        UPDATE outlets 
        SET urn = ?, outlet_name = ?, customer_name = ?, address = ?, phone = ?, outlet_type = ?, 
        local_govt = ?, state = ?, region = ?
        WHERE id = ?
        ''', (urn, outlet_name, customer_name, address, phone, outlet_type, local_govt, state, region, outlet_id))
        
        conn.commit()
        flash('Outlet updated successfully', 'success')
        
        # Get updated outlet
        c.execute("SELECT * FROM outlets WHERE id = ?", (outlet_id,))
        outlet = c.fetchone()
        
        conn.close()
        return redirect(url_for('admin.outlet_list'))
    
    # Get outlet for editing
    c.execute("SELECT * FROM outlets WHERE id = ?", (outlet_id,))
    outlet = c.fetchone()
    
    if not outlet:
        flash('Outlet not found', 'danger')
        return redirect(url_for('admin.outlet_list'))
    
    conn.close()
    
    return render_template('admin/outlet_form.html', outlet=outlet)

@admin_bp.route('/outlets/delete/<int:outlet_id>', methods=['POST'])
@admin_required
def outlet_delete(outlet_id):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check if outlet has executions
    c.execute("SELECT COUNT(*) FROM executions WHERE outlet_id = ?", (outlet_id,))
    execution_count = c.fetchone()[0]
    
    if execution_count > 0:
        flash(f'Cannot delete outlet with {execution_count} executions', 'danger')
        conn.close()
        return redirect(url_for('admin.outlet_list'))
    
    # Delete outlet
    c.execute("DELETE FROM outlets WHERE id = ?", (outlet_id,))
    conn.commit()
    conn.close()
    
    flash('Outlet deleted successfully', 'success')
    return redirect(url_for('admin.outlet_list'))

@admin_bp.route('/outlets/import', methods=['GET', 'POST'])
@admin_required
def outlet_import():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        # Check for valid file extensions
        if not (file.filename.endswith('.csv') or file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            flash('Please upload a CSV or Excel file', 'danger')
            return redirect(request.url)
        
        try:
            # Read file based on extension
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:  # Excel file
                df = pd.read_excel(file)
            
            # Validate required columns
            required_columns = ['urn', 'outlet_name', 'region']
            if not all(col in df.columns for col in required_columns):
                flash(f'File must contain columns: {", ".join(required_columns)}', 'danger')
                return redirect(request.url)
            
            # Fill missing values with empty strings
            optional_columns = ['customer_name', 'address', 'phone', 'outlet_type', 'local_govt', 'state']
            for col in optional_columns:
                if col not in df.columns:
                    df[col] = ''
                else:
                    df[col] = df[col].fillna('')
            
            conn = get_db_connection()
            c = conn.cursor()
            
            success_count = 0
            update_count = 0
            error_count = 0
            
            # Process each row
            for _, row in df.iterrows():
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
                        ''', (
                            row['outlet_name'], row['customer_name'], row['address'], row['phone'], 
                            row['outlet_type'], row['local_govt'], row['state'], row['region'], row['urn']
                        ))
                        update_count += 1
                    else:
                        # Insert new outlet
                        c.execute('''
                        INSERT INTO outlets (urn, outlet_name, customer_name, address, phone, outlet_type, local_govt, state, region)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            row['urn'], row['outlet_name'], row['customer_name'], row['address'], row['phone'], 
                            row['outlet_type'], row['local_govt'], row['state'], row['region']
                        ))
                        success_count += 1
                
                except Exception as e:
                    print(f"Error processing row: {str(e)}")
                    error_count += 1
            
            conn.commit()
            conn.close()
            
            flash(f'Imported {success_count} new outlets, updated {update_count}, {error_count} errors', 'success')
            return redirect(url_for('admin.outlet_list'))
            
        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'danger')
            return redirect(request.url)
    
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
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Build query based on filter
    query = '''
    SELECT o.*, COUNT(e.id) as executions 
    FROM outlets o 
    LEFT JOIN executions e ON o.id = e.outlet_id
    '''
    
    params = []
    
    if delete_by == 'region':
        query += " WHERE o.region = ?"
        params.append(value)
    elif delete_by == 'state':
        query += " WHERE o.state = ?"
        params.append(value)
    elif delete_by == 'local_govt':
        query += " WHERE o.local_govt = ?"
        params.append(value)
    
    query += " GROUP BY o.id"
    
    c.execute(query, params)
    outlets = [dict(row) for row in c.fetchall()]
    
    conn.close()
    
    return jsonify({'outlets': outlets})

@admin_bp.route('/outlets/bulk_delete', methods=['POST'])
@admin_required
def outlet_bulk_delete():
    delete_by = request.form.get('delete_by')
    
    # Get value based on delete_by
    if delete_by == 'region':
        value = request.form.get('region')
    elif delete_by == 'state':
        value = request.form.get('state')
    elif delete_by == 'local_govt':
        value = request.form.get('local_govt')
    else:
        flash('Invalid criteria', 'danger')
        return redirect(url_for('admin.outlet_bulk_manage'))
    
    if not value:
        flash('No value specified', 'danger')
        return redirect(url_for('admin.outlet_bulk_manage'))
    
    # Options
    skip_with_executions = 'skip_with_executions' in request.form
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Find outlets to delete
    query = f"SELECT id FROM outlets WHERE {delete_by} = ?"
    
    # Additional conditions
    if skip_with_executions:
        query += " AND id NOT IN (SELECT DISTINCT outlet_id FROM executions)"
    
    c.execute(query, (value,))
    outlet_ids = [row[0] for row in c.fetchall()]
    
    if not outlet_ids:
        flash('No outlets found matching the criteria or all outlets have executions', 'warning')
        conn.close()
        return redirect(url_for('admin.outlet_bulk_manage'))
    
    # Delete the outlets
    c.execute(f"DELETE FROM outlets WHERE id IN ({','.join(['?'] * len(outlet_ids))})", outlet_ids)
    
    deleted_count = c.rowcount
    conn.commit()
    conn.close()
    
    flash(f'Successfully deleted {deleted_count} outlets', 'success')
    return redirect(url_for('admin.outlet_list'))

# Execution Management
@admin_bp.route('/executions')
@admin_required
def execution_list():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
    SELECT e.id, e.execution_date, o.outlet_name, o.region, o.state, u.full_name as agent_name, e.status
    FROM executions e
    JOIN outlets o ON e.outlet_id = o.id
    JOIN users u ON e.agent_id = u.id
    ORDER BY e.execution_date DESC
    ''')
    
    executions = c.fetchall()
    conn.close()
    
    return render_template('admin/execution_list.html', executions=executions)

@admin_bp.route('/executions/delete/<int:execution_id>', methods=['POST'])
@admin_required
def execution_delete(execution_id):
    conn = get_db_connection()
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
        
        if execution['before_image'] and os.path.exists(os.path.join(upload_folder, execution['before_image'])):
            try:
                os.remove(os.path.join(upload_folder, execution['before_image']))
            except:
                pass
        
        if execution['after_image'] and os.path.exists(os.path.join(upload_folder, execution['after_image'])):
            try:
                os.remove(os.path.join(upload_folder, execution['after_image']))
            except:
                pass
        
        flash('Execution deleted successfully', 'success')
    else:
        flash('Execution not found', 'danger')
    
    conn.close()
    return redirect(url_for('admin.execution_list'))


@admin_bp.route('/executions/upload', methods=['GET', 'POST'])
@admin_required
def execution_upload():
    if request.method == 'GET':
        return render_template('admin/execution_list.html')  # We'll define this next

    if 'file' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(request.url)

    filename = file.filename.lower()
    if not (filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.xls')):
        flash('Invalid file format. Only .csv, .xlsx, .xls allowed.', 'danger')
        return redirect(request.url)

    try:
        # Read the uploaded file into a DataFrame
        if filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        # Validate minimal required columns
        required_columns = ['URN', 'Retail Point Name']
        if not all(col in df.columns for col in required_columns):
            flash(f"Missing required columns: {', '.join(required_columns)}", 'danger')
            return redirect(request.url)

        # Convert the DataFrame to a JSON-like list of dicts
        execution_data = df.fillna('').to_dict(orient='records')

        # Now reuse the original logic that accepts JSON data
        imported = 0
        skipped = 0
        errors = []
        duplicates = []

        conn = get_db_connection()
        cursor = conn.cursor()

        for i, row in enumerate(execution_data):
            try:
                urn = str(row.get('URN', '')).strip()
                outlet_name = str(row.get('Retail Point Name', '')).strip()
                if not urn:
                    raise ValueError("Missing URN")

                # Check for existing execution in last 7 days
                seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                    SELECT COUNT(*) FROM executions e
                    JOIN outlets o ON e.outlet_id = o.id
                    WHERE (o.urn = ? OR o.outlet_name = ?)
                    AND e.execution_date >= ?
                ''', (urn, outlet_name, seven_days_ago))
                existing_count = cursor.fetchone()[0]

                if existing_count > 0:
                    duplicates.append({
                        'row': i + 1,
                        'message': f"Duplicate entry - URN '{urn}' or outlet name '{outlet_name}' has an execution in the last 7 days"
                    })
                    skipped += 1
                    continue

                # Get outlet ID
                cursor.execute('SELECT id FROM outlets WHERE urn = ?', (urn,))
                outlet = cursor.fetchone()
                if not outlet:
                    raise ValueError(f"No outlet found for URN '{urn}'")

                outlet_id = outlet[0]

                # Agent (first admin)
                cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
                agent = cursor.fetchone()
                agent_id = agent[0] if agent else None
                if not agent_id:
                    raise ValueError("No admin user found to assign as agent")

                execution_date = row.get('Date', '').strip() or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                status = row.get('Status', 'Completed').strip()
                notes = row.get('Notes', '').strip()

                products_available = {
                    'Table': str(row.get('Table', '')).lower() in ['true', '1', 'yes'],
                    'Chair': str(row.get('Chair', '')).lower() in ['true', '1', 'yes'],
                    'Parasol': str(row.get('Parasol', '')).lower() in ['true', '1', 'yes'],
                    'Tarpaulin': str(row.get('Tarpaulin', '')).lower() in ['true', '1', 'yes'],
                    'Hawker Jacket': str(row.get('Hawker Jacket', '')).lower() in ['true', '1', 'yes']
                }

                cursor.execute('''
                    INSERT INTO executions (
                        outlet_id, agent_id, execution_date,
                        status, notes, products_available
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (outlet_id, agent_id, execution_date, status, notes, json.dumps(products_available)))

                imported += 1

            except Exception as e:
                errors.append({'row': i + 1, 'error': str(e)})

        conn.commit()
        conn.close()

        # Save duplicates to file if any
        if duplicates:
            os.makedirs('savest', exist_ok=True)
            with open(os.path.join('uploads', 'duplicates.txt'), 'w') as f:
                f.write("\n".join([f"Row {d['row']}: {d['message']}" for d in duplicates]))
            flash(f'{len(duplicates)} duplicates detected in the last 7 days. See uploads/duplicates.txt for details.', 'warning')

        # Flash summary message
        flash(f'Upload complete: {imported} imported, {skipped} skipped, {len(errors)} errors.', 'success')

        if errors:
            flash(f'{len(errors)} errors occurred during import. Check logs for details.', 'danger')

        return redirect(url_for('admin.execution_list'))

        # flash(f'Upload complete: {imported} imported, {skipped} skipped, {len(errors)} errors.', 'success')
        # if duplicates:
        #     with open(os.path.join('savest', 'duplicates.txt'), 'w') as f:
        #         f.write("\n".join(duplicates))

        #     flash(f'{len(duplicates)} duplicates detected in the last 7 days.', 'warning')
        # return redirect(url_for('admin.execution_list'))

    except Exception as e:
        flash(f"Error processing file: {str(e)}", 'danger')
        return redirect(request.url)





























    """Handle execution CSV upload with enhanced validation and data processing"""
    try:
        data = request.json

        if not data or 'data' not in data:
            return jsonify({
                'success': False,
                'message': 'No data provided in request body.'
            }), 400

        execution_data = data.get('data', [])
        if not isinstance(execution_data, list) or not execution_data:
            return jsonify({
                'success': False,
                'message': 'Execution data must be a non-empty list.'
            }), 400

        # Setup required fields for outlet validation
        required_fields = ['URN', 'Retail Point Name', 'Phone', 'Region', 'State', 'LGA']
        validation_errors = []

        # Preprocess and validate data
        for i, row in enumerate(execution_data):
            row_errors = []
            for field in required_fields:
                if not str(row.get(field, '')).strip():
                    row_errors.append(f"Missing {field}")

            # Clean and validate phone number
            phone = str(row.get('Phone', '')).strip()
            if phone:
                cleaned_phone = ''.join(c for c in phone if c.isdigit())
                row['Phone'] = cleaned_phone

            # URN validation
            urn = str(row.get('URN', '')).strip()
            if urn and not urn.startswith('DCP/'):
                row_errors.append("URN must start with 'DCP/'")

            if row_errors:
                validation_errors.append({'row': i + 1, 'errors': row_errors})

        if validation_errors:
            return jsonify({
                'success': False,
                'message': 'Validation errors found in uploaded data.',
                'validation_errors': validation_errors
            }), 400

        # Initialize counters
        total = len(execution_data)
        imported_outlets = updated_outlets = imported_exec = updated_exec = errors = 0
        error_details = []

        conn = get_db_connection()
        cursor = conn.cursor()

        for i, row in enumerate(execution_data):
            try:
                # OUTLET processing
                urn = row.get('URN', '').strip()
                outlet_name = row.get('Retail Point Name', '').strip()
                address = row.get('Address', '').strip()
                phone = row.get('Phone', '').strip()
                outlet_type = row.get('Outlet Type', 'Shop').strip()
                region = row.get('Region', '').strip()
                state = row.get('State', '').strip()
                lga = row.get('LGA', '').strip()

                cursor.execute('SELECT id FROM outlets WHERE urn = ?', (urn,))
                existing_outlet = cursor.fetchone()

                if existing_outlet:
                    cursor.execute('''
                        UPDATE outlets 
                        SET outlet_name = ?, address = ?, phone = ?, outlet_type = ?, 
                            region = ?, state = ?, local_govt = ?
                        WHERE urn = ?
                    ''', (outlet_name, address, phone, outlet_type, region, state, lga, urn))
                    updated_outlets += 1
                    outlet_id = existing_outlet[0]
                else:
                    cursor.execute('''
                        INSERT INTO outlets (urn, outlet_name, address, phone, outlet_type, region, state, local_govt)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (urn, outlet_name, address, phone, outlet_type, region, state, lga))
                    outlet_id = cursor.lastrowid
                    imported_outlets += 1

                # EXECUTION processing
                execution_date = row.get('Date', '').strip() or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                status = row.get('Status', 'Completed').strip()
                notes = row.get('Notes', '').strip()

                # Sample agent selection logic (first admin)
                cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
                agent = cursor.fetchone()
                agent_id = agent[0] if agent else None

                products_available = {
                    'Table': str(row.get('Table', '')).lower() in ['true', '1', 'yes'],
                    'Chair': str(row.get('Chair', '')).lower() in ['true', '1', 'yes'],
                    'Parasol': str(row.get('Parasol', '')).lower() in ['true', '1', 'yes'],
                    'Tarpaulin': str(row.get('Tarpaulin', '')).lower() in ['true', '1', 'yes'],
                    'Hawker Jacket': str(row.get('Hawker Jacket', '')).lower() in ['true', '1', 'yes']
                }

                cursor.execute('''
                    INSERT INTO executions (
                        outlet_id, agent_id, execution_date,
                        status, notes, products_available
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(outlet_id, execution_date) DO UPDATE SET
                        status = excluded.status,
                        notes = excluded.notes,
                        products_available = excluded.products_available
                ''', (outlet_id, agent_id, execution_date, status, notes, json.dumps(products_available)))

                if cursor.rowcount == 1:
                    imported_exec += 1
                else:
                    updated_exec += 1

            except Exception as e:
                errors += 1
                error_details.append({
                    'row': i + 1,
                    'error': str(e)
                })

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Execution upload processed successfully.',
            'summary': {
                'total_rows': total,
                'outlets_imported': imported_outlets,
                'outlets_updated': updated_outlets,
                'executions_imported': imported_exec,
                'executions_updated': updated_exec,
                'errors': errors,
                'error_details': error_details if error_details else None
            }
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Unexpected server error: {str(e)}'
        }), 500

    """Handle execution CSV upload with enhanced validation"""
    try:
        data = request.json
        
        if not data or 'data' not in data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        execution_data = data.get('data', [])
        
        # Enhanced validation
        required_fields = ['URN', 'Retail Point Name', 'Phone', 'Region', 'State', 'LGA']
        validation_errors = []
        
        for i, row in enumerate(execution_data):
            row_errors = []
            
            # Check required fields
            for field in required_fields:
                if not row.get(field, '').strip():
                    row_errors.append(f"Missing {field}")
            
            # Validate phone number format
            phone = row.get('Phone', '').strip()
            if phone:
                # Remove quotes and clean phone number
                phone = phone.replace("'", "").replace('"', '').replace('+', '').replace('-', '').replace('(', '').replace(')', '').replace(' ', '').replace('.','')
                # phone = int(phone)
                # if not phone.isdigit() or len(phone) not in [10, 11]:
                #     row_errors.append("Invalid phone number format")
                row['Phone'] = phone  # Update cleaned phone
            
            # Validate URN format
            urn = row.get('URN', '').strip()
            if urn and not urn.startswith('DCP/'):
                row_errors.append("Invalid URN format")
            
            if row_errors:
                validation_errors.append({
                    'row': i + 1,
                    'errors': row_errors
                })
        
        if validation_errors:
            return jsonify({
                'success': False,
                'message': 'Validation errors found',
                'validation_errors': validation_errors
            }), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        total = len(execution_data)
        imported = 0
        updated = 0
        skipped = 0
        errors = 0
        error_details = []
        
        for i, row in enumerate(execution_data):
            try:
                urn = row.get('URN', '').strip()
                outlet_name = row.get('Retail Point Name', '').strip()
                address = row.get('Address', '').strip()
                phone = row.get('Phone', '').strip()
                outlet_type = row.get('Outlet Type', '').strip()
                region = row.get('Region', '').strip()
                state = row.get('State', '').strip()
                lga = row.get('LGA', '').strip()
                
                # Check if outlet exists
                cursor.execute('SELECT id FROM outlets WHERE urn = ?', (urn,))
                existing_outlet = cursor.fetchone()
                
                if existing_outlet:
                    # Update existing outlet
                    cursor.execute('''
                    UPDATE outlets 
                    SET outlet_name = ?, address = ?, phone = ?, outlet_type = ?, 
                        region = ?, state = ?, outlet_lga = ?
                    WHERE urn = ?
                    ''', (outlet_name, address, phone, outlet_type, region, state, lga, urn))
                    updated += 1
                else:
                    # Insert new outlet
                    cursor.execute('''
                    INSERT INTO outlets (urn, outlet_name, address, phone, outlet_type, region, state, outlet_lga)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (urn, outlet_name, address, phone, outlet_type, region, state, lga))
                    imported += 1
                    
            except Exception as e:
                errors += 1
                error_details.append({
                    'row': i + 1,
                    'error': str(e)
                })
        
        conn.commit()
        conn.close()
        
        print(errors)

        return jsonify({
            'success': True,
            'message': f'Successfully processed outlet data',
            'total': total,
            'imported': imported,
            'updated': updated,
            'skipped': skipped,
            'errors': errors,
            'error_details': error_details if errors > 0 else None
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error processing upload: {str(e)}'
        }), 500

    """Handle execution CSV upload"""
    try:
        data = request.json
        
        if not data or 'data' not in data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        execution_data = data.get('data', [])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        total = len(execution_data)
        imported = 0
        updated = 0
        skipped = 0
        errors = 0
        
        # Validate required fields
        required_fields = ['URN', 'Retail Point Name', 'Region', 'State', 'LGA']
        validation_errors = []
        
        for i, row in enumerate(execution_data):
            row_errors = []
            for field in required_fields:
                if not row.get(field, '').strip():
                    row_errors.append(f"Missing {field}")
            if row_errors:
                validation_errors.append({'row': i+1, 'errors': row_errors})
        
        if validation_errors:
            return jsonify({
                'success': False,
                'message': 'Validation errors',
                'validation_errors': validation_errors
            }), 400

        # Process valid data
        imported = 0
        updated = 0
        errors = 0
        
        for row in execution_data:
            try:
                outlet_urn = row['URN'].strip()
                execution_date = row.get('Date', '').strip() or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                status = row.get('Status', 'Completed').strip()
                notes = row.get('Notes', '').strip()

                # Get outlet
                cursor.execute('SELECT id FROM outlets WHERE urn = ?', (outlet_urn,))
                outlet = cursor.fetchone()
                if not outlet:
                    continue

                # Get agent (assuming first admin)
                cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
                agent = cursor.fetchone()

                # Process products
                products_available = {
                    'Table': row.get('Table', '').lower() in ['true', '1', 'yes'],
                    'Chair': row.get('Chair', '').lower() in ['true', '1', 'yes'],
                    'Parasol': row.get('Parasol', '').lower() in ['true', '1', 'yes'],
                    'Tarpaulin': row.get('Tarpaulin', '').lower() in ['true', '1', 'yes'],
                    'Hawker Jacket': row.get('Hawker Jacket', '').lower() in ['true', '1', 'yes']
                }

                # Insert/update execution
                cursor.execute('''
                    INSERT INTO executions (
                        outlet_id, agent_id, execution_date,
                        status, notes, products_available
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(outlet_id, execution_date) DO UPDATE SET
                        status = excluded.status,
                        notes = excluded.notes,
                        products_available = excluded.products_available
                ''', (outlet[0], agent[0], execution_date, status, notes, json.dumps(products_available)))

                if cursor.rowcount > 0:
                    imported += 1
                else:
                    updated += 1

            except Exception as e:
                errors += 1

        conn.commit()
        conn.close()

        print(errors)

        return jsonify({
            'success': True,
            'execution_data': {
                'imported': imported,
                'updated': updated,
                'errors': errors
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error processing execution upload: {str(e)}'
        }), 500