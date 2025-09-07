import sqlite3
from flask import render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory, make_response, send_file
from datetime import datetime
import json
import os
import uuid
from werkzeug.utils import secure_filename
from .models import get_db_connection, UPLOAD_FOLDER, DB_PATH
from .utils import allowed_file, save_base64_image, DANGOTE_PRODUCTS
from functools import wraps
from contextlib import contextmanager
from typing import Optional, Dict, List, Any, Tuple

import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import requests

# Constants
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 1000
DEFAULT_EXPORT_PER_PAGE = 1000
RECENT_EXECUTIONS_LIMIT = 5
RECENT_EXECUTIONS_DAYS = 2




    # Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Not authenticated'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

    # Database context manager
@contextmanager
def get_db_cursor():
    """Context manager for database operations with automatic cleanup"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield conn, cursor
        except Exception as e:
            conn.rollback()
            raise e


    # Helper functions
def get_session_user_info() -> Dict[str, Any]:
    """Get current user information from session"""
    return {
        'user_id': session.get('user_id'),
        'role': session.get('role'),
        'region': session.get('region'),
        'state': session.get('state', ''),
        'lga': session.get('lga', ''),
        'username': session.get('username'),
        'full_name': session.get('full_name')
    }

def build_filter_query(base_query: str, filters: Dict[str, Any], params: List[Any]) -> Tuple[str, List[Any]]:
    """Build dynamic filter query with parameters"""
    query = base_query
    
    for field, value in filters.items():
        if value:
            if field == 'search':
                search_term = f"%{value}%"
                query += """ AND (
                    o.outlet_name LIKE ? OR
                    o.customer_name LIKE ? OR
                    o.address LIKE ? OR
                    o.phone LIKE ? OR
                    o.urn LIKE ?
                )"""
                params.extend([search_term] * 5)
            elif field == 'status' and ',' in str(value):
                status_list = [s.strip() for s in str(value).split(',') if s.strip()]
                placeholders = ','.join('?' for _ in status_list)
                query += f' AND e.status IN ({placeholders})'
                params.extend(status_list)
            else:
                query += f" AND {field} = ?"
                params.append(value)

    return query, params



def handle_image_upload(file_key: str, captured_key: str, prefix: str) -> Optional[str]:
    """Handle both file upload and base64 captured images"""
    filename = None
    
    # Handle file upload
    if file_key in request.files and request.files[file_key].filename:
        image_file = request.files[file_key]
        if allowed_file(image_file.filename):
            filename = f"{uuid.uuid4()}_{secure_filename(image_file.filename)}"
            image_file.save(os.path.join(UPLOAD_FOLDER, filename))
    
    # Handle captured image if no file was uploaded
    if not filename:
        captured_data = request.form.get(captured_key)
        if captured_data:
            filename = save_base64_image(captured_data, prefix)

    return filename


def calculate_pagination(total_count: int, page: int, per_page: int) -> Dict[str, int]:
    """Calculate pagination information"""
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
    return {
        'total_count': total_count,
        'total_pages': total_pages,
        'current_page': page,
        'per_page': per_page
    }






def init_routes(app):
    @app.route('/')
    @login_required
    def index():
        return render_template('dashboard.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            
            if not username or not password:
                flash('Username and password are required', 'danger')
                return render_template('login.html')

            with get_db_cursor() as (conn, cursor):
                cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
                user = cursor.fetchone()

                if user:
                    session.update({
                        'user_id': user['id'],
                        'username': user['username'],
                        'role': user['role'],
                        'full_name': user['full_name'],
                        'region': user['region'],
                        'state': user['state'] or "",
                        'lga': user['lga'] or ""
                    })
                    return redirect(url_for('index'))
                else:
                    flash('Invalid credentials', 'danger')

        return render_template('login.html')
   
    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.route('/outlets')
    @login_required
    def outlets():
        # Get filter and pagination parameters
        filters = {
            'region': request.args.get('region', ''),
            'state': request.args.get('state', ''),
            'local_govt': request.args.get('local_govt', ''),
            'outlet_type': request.args.get('outlet_type', ''),
            'search': request.args.get('search', '')
        }

        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', DEFAULT_PER_PAGE, type=int), MAX_PER_PAGE)
        offset = (page - 1) * per_page

        with get_db_cursor() as (conn, cursor):
            base_query = """
                SELECT o.* FROM outlets o
                WHERE o.id NOT IN (
                    SELECT DISTINCT outlet_id FROM executions
                    WHERE status = 'Completed'
                )
            """
            count_query = """
                SELECT COUNT(*) FROM outlets o
                WHERE o.id NOT IN (
                    SELECT DISTINCT outlet_id FROM executions
                    WHERE status = 'Completed'
                )
            """

            params = []
            count_params = []

            # Role-based filter
            user_info = get_session_user_info()
            if user_info['role'] == 'field_agent':
                base_query += " AND o.region = ?"
                count_query += " AND o.region = ?"
                params.append(user_info['region'])
                count_params.append(user_info['region'])

                if user_info['state']:
                    base_query += " AND o.state = ?"
                    count_query += " AND o.state = ?"
                    params.append(user_info['state'])
                    count_params.append(user_info['state'])

            # User selected filter
            query, params = build_filter_query(base_query, {
                'o.region': filters['region'],
                'o.state': filters['state'],
                'o.local_govt': filters['local_govt'],
                'o.outlet_type': filters['outlet_type'],
                'search': filters['search']
            }, params)

            count_query, count_params = build_filter_query(count_query, {
                'o.region': filters['region'],
                'o.state': filters['state'],
                'o.local_govt': filters['local_govt'],
                'o.outlet_type': filters['outlet_type'],
                'search': filters['search']
            }, count_params)

            cursor.execute(count_query, count_params)
            total_outlets = cursor.fetchone()[0]

            # Pagination
            query += " LIMIT ? OFFSET ?"
            params.extend([per_page, offset])

            cursor.execute(query, params)
            outlets = cursor.fetchall()

        # Your helper probably returns something like:
        # { 'page': page, 'total_pages': X, 'per_page': per_page }
        pagination = calculate_pagination(total_outlets, page, per_page)

        # Build same format as old return
        return render_template('outlets.html',
                            outlets=outlets,
                            page=pagination.get('current_page', page),
                            total_pages=pagination.get('total_pages'),
                            total_outlets=total_outlets,
                            region=filters['region'],
                            state=filters['state'],
                            local_govt=filters['local_govt'],
                            outlet_type=filters['outlet_type']
                            )

  
    @app.route('/execution/new/<int:outlet_id>', methods=['GET', 'POST'])
    @login_required
    def new_execution(outlet_id):
        user_info = get_session_user_info()
        
        if request.method == 'GET':
            with get_db_cursor() as (conn, cursor):
                # Check for existing pending execution
                cursor.execute(
                    "SELECT id FROM executions WHERE outlet_id = ? AND agent_id = ? AND status = 'Pending'",
                    (outlet_id, user_info['user_id'])
                )
                existing = cursor.fetchone()

                if not existing:
                    # Create new pending execution
                    cursor.execute(
                        """INSERT INTO executions (outlet_id, agent_id, execution_date, status)
                           VALUES (?, ?, ?, ?)""",
                        (outlet_id, user_info['user_id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'Pending')
                    )
                    conn.commit()

        elif request.method == 'POST':
            # Handle image uploads
            before_filename = handle_image_upload('before_image', 'before_captured_image', 'before')
            after_filename = handle_image_upload('after_image', 'after_captured_image', 'after')

            # Get form data
            form_data = {
                'latitude': request.form.get('latitude'),
                'longitude': request.form.get('longitude'),
                'notes': request.form.get('notes', '')
            }

            # Process products
            products = {}
            for product in DANGOTE_PRODUCTS:
                field_name = f"product_{product.replace(' ', '_')}"
                products[product] = request.form.get(field_name, "No") == "Yes"
            
            products_json = json.dumps(products)
            execution_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            with get_db_cursor() as (conn, cursor):
                # Check for existing pending execution
                cursor.execute(
                    "SELECT id FROM executions WHERE outlet_id = ? AND agent_id = ? AND status = 'Pending'",
                    (outlet_id, user_info['user_id'])
                )
                existing = cursor.fetchone()

                if existing:
                    # Update existing execution
                    cursor.execute(
                        """UPDATE executions SET before_image = ?, after_image = ?, latitude = ?, 
                           longitude = ?, notes = ?, products_available = ?, status = ?, execution_date = ?
                           WHERE id = ?""",
                        (before_filename, after_filename, form_data['latitude'], form_data['longitude'],
                         form_data['notes'], products_json, 'Completed', execution_date, existing[0])
                    )
                else:
                    # Insert new execution
                    cursor.execute(
                        """INSERT INTO executions (outlet_id, agent_id, execution_date, before_image, 
                           after_image, latitude, longitude, notes, products_available, status)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (outlet_id, user_info['user_id'], execution_date, before_filename, after_filename,
                         form_data['latitude'], form_data['longitude'], form_data['notes'], products_json, 'Completed')
                    )
                
                # After completing the execution, delete any OTHER pending executions for the same outlet by different agents
                # This prevents conflicts when multiple agents start executions for the same outlet
                cursor.execute(
                    """DELETE FROM executions 
                       WHERE outlet_id = ? AND status = 'Pending' AND agent_id != ?""",
                    (outlet_id, user_info['user_id'])
                )
                
                deleted_pending = cursor.rowcount
                if deleted_pending > 0:
                    print(f"Deleted {deleted_pending} pending execution(s) for outlet {outlet_id} by other agents")
                
                conn.commit()

            flash('Visitation recorded successfully', 'success')
            return redirect(url_for('outlets'))

        # GET request - load outlet data
        with get_db_cursor() as (conn, cursor):
            cursor.execute("SELECT * FROM outlets WHERE id = ?", (outlet_id,))
            outlet = cursor.fetchone()

        if not outlet:
            flash('Outlet not found', 'danger')
            return redirect(url_for('outlets'))

        return render_template('new_execution.html', outlet=outlet, products=DANGOTE_PRODUCTS)
    
    @app.route('/executions')
    @login_required
    def executions():
        # Get filter and pagination parameters
        filters = {
            'agent_id': request.args.get('agent_id'),
            'region': request.args.get('region'),
            'status': request.args.get('status'),
            'search': request.args.get('search', '')
        }
        
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', DEFAULT_PER_PAGE, type=int), MAX_PER_PAGE)
        offset = (page - 1) * per_page

        with get_db_cursor() as (conn, cursor):
            base_query = """
                SELECT e.*, o.outlet_name, o.urn, o.state, o.region, o.local_govt, u.full_name as agent_name
                FROM executions e
                JOIN outlets o ON e.outlet_id = o.id
                JOIN users u ON e.agent_id = u.id
                WHERE 1=1
            """
            count_query = """
                SELECT COUNT(*)
                FROM executions e
                JOIN outlets o ON e.outlet_id = o.id
                JOIN users u ON e.agent_id = u.id
                WHERE 1=1
            """
            params = []
            count_params = []
            
            user_info = get_session_user_info()
            
            # Apply role-based filtering
            if filters['agent_id']:
                base_query += ' AND e.agent_id = ?'
                count_query += ' AND e.agent_id = ?'
                params.append(filters['agent_id'])
                count_params.append(filters['agent_id'])
            elif user_info['role'] == 'field_agent':
                base_query += ' AND e.agent_id = ?'
                count_query += ' AND e.agent_id = ?'
                params.append(user_info['user_id'])
                count_params.append(user_info['user_id'])
            
            # Apply other filters
            if filters['region']:
                base_query += ' AND o.region = ?'
                count_query += ' AND o.region = ?'
                params.append(filters['region'])
                count_params.append(filters['region'])
            
            if filters['status']:
                if ',' in filters['status']:
                    status_list = [s.strip() for s in filters['status'].split(',') if s.strip()]
                    placeholders = ','.join('?' for _ in status_list)
                    base_query += f' AND e.status IN ({placeholders})'
                    count_query += f' AND e.status IN ({placeholders})'
                    params.extend(status_list)
                    count_params.extend(status_list)
                else:
                    base_query += ' AND e.status = ?'
                    count_query += ' AND e.status = ?'
                    params.append(filters['status'])
                    count_params.append(filters['status'])
            
            if filters['search']:
                search_term = f"%{filters['search']}%"
                search_condition = """ AND (
                    o.outlet_name LIKE ? OR
                    o.urn LIKE ? OR
                    o.address LIKE ? OR
                    u.full_name LIKE ?
                )"""
                base_query += search_condition
                count_query += search_condition
                search_params = [search_term] * 4
                params.extend(search_params)
                count_params.extend(search_params)
            
            if start_date:
                base_query += ' AND e.execution_date >= ?'
                count_query += ' AND e.execution_date >= ?'
                params.append(start_date)
                count_params.append(start_date)
            
            if end_date:
                base_query += ' AND e.execution_date <= ?'
                count_query += ' AND e.execution_date <= ?'
                params.append(end_date)
                count_params.append(end_date)
            
            # Get total count
            cursor.execute(count_query, count_params)
            total_executions = cursor.fetchone()[0]
            
            # Add ordering and pagination
            base_query += ' ORDER BY e.execution_date DESC LIMIT ? OFFSET ?'
            params.extend([per_page, offset])
            
            cursor.execute(base_query, params)
            executions = cursor.fetchall()

        pagination = calculate_pagination(total_executions, page, per_page)

        return render_template('executions.html', 
                             executions=executions,
                             page=pagination.get('current_page', page),
                             total_pages=pagination.get('total_pages'),
                             total_executions=total_executions,
                             **filters,
                             start_date=start_date,
                             end_date=end_date)

    @app.route('/execution/<int:execution_id>')
    @login_required
    def execution_detail(execution_id):
        with get_db_cursor() as (conn, cursor):
            cursor.execute(
                """SELECT e.*, o.outlet_name, o.urn, o.state, o.region, o.local_govt, 
                   o.customer_name, o.address, o.outlet_type, u.full_name as agent_name
                   FROM executions e
                   JOIN outlets o ON e.outlet_id = o.id
                   JOIN users u ON e.agent_id = u.id
                   WHERE e.id = ?""",
                (execution_id,)
            )
            execution = cursor.fetchone()

        if not execution:
            flash('Visitation not found', 'danger')
            return redirect(url_for('executions'))

        products = json.loads(execution['products_available']) if execution['products_available'] else {}
        return render_template('execution_detail.html', execution=execution, products=products)
    
    @app.route('/dashboard/data')
    @login_required
    def dashboard_data():
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401

        with get_db_cursor() as (conn, c):
            is_admin = session['role'] == 'admin'
            user_id = session['user_id']
            user_region = session['region']
            user_state = session.get('state', '')

            if is_admin:
                c.execute("SELECT COUNT(*) as count FROM outlets")
                total_outlets = c.fetchone()['count']

                c.execute("SELECT COUNT(*) as count FROM executions WHERE status = 'Completed'")
                total_executions = c.fetchone()['count']

                coverage_percentage = round((total_executions / total_outlets * 100), 2) if total_outlets > 0 else 0

                c.execute("SELECT COUNT(DISTINCT agent_id) as count FROM executions WHERE status = 'Completed'")
                active_agents = c.fetchone()['count']
            else:
                if user_state:
                    c.execute("SELECT COUNT(*) as count FROM outlets WHERE state = ?", (user_state,))
                else:
                    c.execute("SELECT COUNT(*) as count FROM outlets WHERE region = ?", (user_region,))
                total_outlets = c.fetchone()['count']

                c.execute("SELECT COUNT(*) as count FROM executions WHERE agent_id = ? AND status = 'Completed'", (user_id,))
                total_executions = c.fetchone()['count']

                c.execute("""
                    SELECT COUNT(DISTINCT outlet_id) as count
                    FROM executions
                    WHERE agent_id = ?
                """, (user_id,))
                assigned_outlets = c.fetchone()['count']

                coverage_percentage = round((total_executions / assigned_outlets * 100), 2) if assigned_outlets > 0 else 0
                active_agents = 1

            if is_admin:
                c.execute("SELECT region, COUNT(*) as count FROM outlets GROUP BY region")
                regions = {row['region']: row['count'] for row in c.fetchall()}

                c.execute("SELECT state, COUNT(*) as count FROM outlets GROUP BY state")
                states = {row['state']: row['count'] for row in c.fetchall()}
            else:
                if user_state:
                    c.execute("SELECT local_govt, COUNT(*) as count FROM outlets WHERE state = ? GROUP BY local_govt",
                            (user_state,))
                else:
                    c.execute("SELECT local_govt, COUNT(*) as count FROM outlets WHERE region = ? GROUP BY local_govt",
                            (user_region,))
                regions = {row['local_govt']: row['count'] for row in c.fetchall()}

                c.execute("SELECT state, COUNT(*) as count FROM outlets WHERE region = ? GROUP BY state",
                         (user_region,))
                states = {row['state']: row['count'] for row in c.fetchall()}

            if is_admin:
                c.execute("SELECT DATE(execution_date) as date, COUNT(*) as count FROM executions WHERE status = 'Completed' GROUP BY DATE(execution_date)")
            else:
                c.execute("SELECT DATE(execution_date) as date, COUNT(*) as count FROM executions WHERE agent_id = ? AND status = 'Completed' GROUP BY DATE(execution_date)",
                         (user_id,))
            executions_by_date = {row['date']: row['count'] for row in c.fetchall()}

            if is_admin:
                c.execute('''
                SELECT u.full_name, COUNT(e.id) as count
                FROM executions e
                JOIN users u ON e.agent_id = u.id
                WHERE e.status = 'Completed'
                GROUP BY e.agent_id
                ''')
                executions_by_agent = {row['full_name']: row['count'] for row in c.fetchall()}
            else:
                c.execute('''
                SELECT u.full_name, COUNT(e.id) as count
                FROM executions e
                JOIN users u ON e.agent_id = u.id
                WHERE e.agent_id = ? AND e.status = 'Completed'
                GROUP BY e.agent_id
                ''', (user_id,))
                executions_by_agent = {row['full_name']: row['count'] for row in c.fetchall()}

            if is_admin:
                c.execute("SELECT outlet_type, COUNT(*) as count FROM outlets GROUP BY outlet_type")
            else:
                if user_state:
                    c.execute("SELECT outlet_type, COUNT(*) as count FROM outlets WHERE state = ? GROUP BY outlet_type",
                            (user_state,))
                else:
                    c.execute("SELECT outlet_type, COUNT(*) as count FROM outlets WHERE region = ? GROUP BY outlet_type",
                            (user_region,))
            outlet_types = {row['outlet_type']: row['count'] for row in c.fetchall()}

        return jsonify({
            'total_outlets': total_outlets,
            'total_executions': total_executions,
            'coverage_percentage': round((total_executions / total_outlets * 100), 2) if total_outlets > 0 else 0,
            'active_agents': active_agents,
            'regions': regions,
            'states': states,
            'executions_by_date': executions_by_date,
            'executions_by_agent': executions_by_agent,
            'outlet_types': outlet_types
        })

    @app.route('/api/outlets')
    def api_outlets():
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401

        conn = get_db_connection()
        c = conn.cursor()

        state = request.args.get('state')
        region = request.args.get('region')
        local_govt = request.args.get('local_govt')

        query = "SELECT * FROM outlets WHERE 1=1"
        params = []

        if region:
            query += " AND region = ?"
            params.append(region)

        if state:
            query += " AND state = ?"
            params.append(state)

        if local_govt:
            query += " AND local_govt = ?"
            params.append(local_govt)

        if session['role'] == 'field_agent':
            query += " AND region = ?"
            params.append(session['region'])

        c.execute(query, params)

        outlets = [dict(row) for row in c.fetchall()]
        conn.close()

        return jsonify(outlets)

    @app.route('/api/posm_deployments')
    def posm_deployments():
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401

        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            region = request.args.get('region')
            state = request.args.get('state')
            date_range = request.args.get('date_range')

            # Base query
            query = '''
                SELECT
                    e.id,
                    e.execution_date,
                    e.before_image,
                    e.after_image,
                    e.latitude,
                    e.longitude,
                    e.products_available,
                    u.full_name as agent_name,
                    u.username,
                    u.role,
                    u.region as user_region,
                    u.state as user_state,
                    u.lga as user_lga,
                    o.region as outlet_region,
                    o.state as outlet_state,
                    o.local_govt as outlet_lga,
                    o.urn,
                    o.outlet_name,
                    o.address,
                    o.phone,
                    o.outlet_type
                FROM executions e
                JOIN users u ON e.agent_id = u.id
                JOIN outlets o ON e.outlet_id = o.id
                WHERE e.status = 'Completed'
            '''

            params = []

            # Add filters
            if region and region.upper() != 'ALL':
                query += " AND o.region = ?"
                params.append(region.upper())

            if state and state.upper() != 'ALL':
                query += " AND o.state = ?"
                params.append(state.upper())

            # Add date range filter
            if date_range:
                if date_range == 'week':
                    query += " AND datetime(e.execution_date) >= datetime('now', '-7 days')"
                elif date_range == 'month':
                    query += " AND datetime(e.execution_date) >= datetime('now', '-1 month')"
                elif date_range == 'quarter':
                    query += " AND datetime(e.execution_date) >= datetime('now', '-3 months')"
                elif date_range == 'year':
                    query += " AND datetime(e.execution_date) >= datetime('now', '-1 year')"

            with get_db_cursor() as (conn, cursor):
                # Get total count for pagination
                count_query = f"SELECT COUNT(*) as count FROM ({query}) as subquery"
                cursor.execute(count_query, params)
                total_count = cursor.fetchone()['count']

                # Add pagination to main query
                query += " ORDER BY e.execution_date DESC LIMIT ? OFFSET ?"
                params.extend([per_page, (page - 1) * per_page])

                # Execute main query
                cursor.execute(query, params)
                executions = cursor.fetchall()

            # Process results
            executions_data = []
            for exec_row in executions:
                execution = dict(exec_row)
                
                # Handle missing/null data - replace with empty strings
                execution['agent_name'] = execution.get('agent_name', '') or ''
                execution['urn'] = execution.get('urn', '') or ''
                execution['outlet_name'] = execution.get('outlet_name', '') or ''
                execution['address'] = execution.get('address', '') or ''
                execution['phone'] = execution.get('phone', '') or ''
                execution['outlet_type'] = execution.get('outlet_type', '') or ''
                execution['outlet_region'] = execution.get('outlet_region', '') or ''
                execution['outlet_state'] = execution.get('outlet_state', '') or ''
                execution['outlet_lga'] = execution.get('outlet_lga', '') or ''
                execution['before_image'] = execution.get('before_image', '') or ''
                execution['after_image'] = execution.get('after_image', '') or ''
                execution['latitude'] = execution.get('latitude', '') or ''
                execution['longitude'] = execution.get('longitude', '') or ''
                
                # Static values for now - could be calculated later
                execution['executions_performed'] = 1  # Each row is one execution
                execution['outlets_assigned'] = 0
                execution['outlets_visited'] = 1
                execution['coverage_percentage'] = 0
                
                executions_data.append(execution)

            return jsonify({
                'executions': executions_data,
                'pagination': {
                    'total_count': total_count,
                    'total_pages': (total_count + per_page - 1) // per_page,
                    'current_page': page,
                    'per_page': per_page
                }
            })

        except Exception as e:
            print(f"Error in posm_deployments: {str(e)}")
            return jsonify({'error': f'Internal server error: {str(e)}'}), 500



 
 


 

    def get_posm_deployments_data(region=None, state=None, date_range=None, start_date=None, end_date=None):
        """Helper function to get POSM deployments data for export"""
        query = '''
            SELECT
                e.*,
                u.full_name as agent_name,
                u.username,
                u.role,
                u.region,
                u.state,
                u.lga,
                o.region as outlet_region,
                o.state as outlet_state,
                o.local_govt as outlet_lga,
                o.urn,
                o.outlet_name,
                o.address,
                o.phone,
                o.outlet_type
            FROM executions e
            JOIN users u ON e.agent_id = u.id
            JOIN outlets o ON e.outlet_id = o.id
            WHERE e.status = 'Completed'
        '''

        params = []
        if region and region != 'ALL':
            query += ' AND o.region = ?'
            params.append(region)

        if state and state != 'ALL':
            query += ' AND o.state = ?'
            params.append(state)

        if date_range:
            if date_range == 'week':
                query += " AND datetime(e.execution_date) >= datetime('now', '-7 days')"
            elif date_range == 'month':
                query += " AND datetime(e.execution_date) >= datetime('now', '-1 month')"
            elif date_range == 'quarter':
                query += " AND datetime(e.execution_date) >= datetime('now', '-3 months')"
            elif date_range == 'year':
                query += " AND datetime(e.execution_date) >= datetime('now', '-1 year')"
            elif date_range == 'custom' and start_date and end_date:
                query += " AND e.execution_date BETWEEN ? AND ?"
                params.extend([start_date, end_date])

        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        executions = conn.execute(query, params).fetchall()
        conn.close()
        
        executions_data = []
        for exec_row in executions:
            execution = dict(exec_row)

            # Parse the JSON string safely
            try:
                products = json.loads(execution.get('products_available', '{}'))
            except (json.JSONDecodeError, TypeError):
                products = {}

            # Map each relevant product field to the execution dict
            execution['table'] = products.get('Table', False)
            execution['chair'] = products.get('Chair', False)
            execution['parasol'] = products.get('Parasol', False)
            execution['tarpaulin'] = products.get('Tarpaulin', False)
            execution['hawker_jacket'] = products.get('Hawker Jacket', False)
            execution['cup'] = products.get('Cup', False)  # Fixed from 'Cups' to 'Cup'

            executions_data.append(execution)

        # Create DataFrame
        df = pd.DataFrame([dict(row) for row in executions_data])
        
        if df.empty:
            return pd.DataFrame()

        # Rename columns
        df = df.rename(columns={
            'agent_name': 'Agent Name',
            'urn': 'URN',
            'outlet_name': 'Retail Point Name',
            'address': 'Address',
            'phone': 'Phone',
            'outlet_type': 'Retail Point Type',
            'outlet_region': 'Region',
            'outlet_state': 'State',
            'outlet_lga': 'LGA',
            'table': 'Table',
            'chair': 'Chair',
            'parasol': 'Parasol',
            'tarpaulin': 'Tarpaulin',
            'hawker_jacket': 'Hawker Jacket',
            'cup': 'Cup',
            'latitude': 'Latitude',
            'longitude': 'Longitude',
            'before_image': 'Before Image',
            'after_image': 'After Image'
        })

        # Define final headers
        headers = [
            'Agent Name', 'URN', 'Retail Point Name', 'Address', 'Phone', 'Retail Point Type',
            'Region', 'State', 'LGA', 'Table', 'Chair', 'Parasol', 'Tarpaulin', 
            'Hawker Jacket', 'Cup', 'Before Image', 'After Image'
        ]

        # Add missing columns
        for col in headers:
            if col not in df.columns:
                df[col] = None

        # Keep only the columns in our headers list
        df = df[headers]

        return df




    @app.route('/api/agent_performance')
    def agent_performance():
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401

        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 20, type=int)
            offset = (page - 1) * per_page

            search_term = request.args.get('search', '')
            region = request.args.get('region', '')
            state = request.args.get('state', '')
            date_range = request.args.get('date_range', '')

            agent_id = request.args.get('agent_id')
            user_role = session.get('role')
            current_user_id = session.get('user_id')

            # Base query - exclude current user and only show field agents
            count_query = '''
            SELECT COUNT(DISTINCT u.id) as total_count
            FROM users u
            WHERE u.role = 'field_agent' AND u.id != ?
            '''

            query = '''
            SELECT
                u.id,
                u.username,
                u.full_name,
                u.role,
                u.region,
                u.state,
                u.lga,
                COUNT(DISTINCT CASE WHEN e.status = 'Completed' THEN e.id ELSE NULL END) as executions_performed,
                COUNT(DISTINCT CASE WHEN e.status = 'Completed' THEN e.outlet_id ELSE NULL END) as outlets_visited
            FROM
                users u
            LEFT JOIN
                executions e ON u.id = e.agent_id
            WHERE
                u.role = 'field_agent' AND u.id != ?
            '''

            params = [current_user_id]
            count_params = [current_user_id]

            if search_term:
                search_condition = '''
                AND (
                    u.username LIKE ? OR
                    u.full_name LIKE ? OR
                    u.region LIKE ? OR
                    u.state LIKE ? OR
                    u.lga LIKE ?
                )
                '''
                search_param = f'%{search_term}%'
                query += search_condition
                count_query += search_condition
                params.extend([search_param, search_param, search_param, search_param, search_param])
                count_params.extend([search_param, search_param, search_param, search_param, search_param])

            if region and region != 'all':
                query += " AND u.region = ? "
                count_query += " AND u.region = ? "
                params.append(region)
                count_params.append(region)

            if state and state != 'all':
                query += " AND u.state = ? "
                count_query += " AND u.state = ? "
                params.append(state)
                count_params.append(state)

            if date_range:
                date_condition = ""
                if date_range == 'week':
                    date_condition = "AND datetime(e.execution_date) >= datetime('now', '-7 days')"
                elif date_range == 'month':
                    date_condition = "AND datetime(e.execution_date) >= datetime('now', '-1 month')"
                elif date_range == 'quarter':
                    date_condition = "AND datetime(e.execution_date) >= datetime('now', '-3 months')"
                elif date_range == 'year':
                    date_condition = "AND datetime(e.execution_date) >= datetime('now', '-1 year')"

                if date_condition:
                    query += " " + date_condition

            if agent_id and agent_id != str(current_user_id):
                query += " AND u.id = ? "
                count_query += " AND u.id = ? "
                params.append(agent_id)
                count_params.append(agent_id)

            with get_db_cursor() as (conn, cursor):
                # Get total count
                cursor.execute(count_query, count_params)
                total_count = cursor.fetchone()['total_count']

                # Add grouping and pagination to main query
                query += " GROUP BY u.id ORDER BY u.full_name LIMIT ? OFFSET ?"
                params.extend([per_page, offset])

                cursor.execute(query, params)
                agent_rows = cursor.fetchall()

                agents = []
                for row in agent_rows:
                    agent_data = dict(row)
                    
                    # Handle missing/null data - replace with empty strings
                    agent_data['full_name'] = agent_data.get('full_name', '') or ''
                    agent_data['username'] = agent_data.get('username', '') or ''
                    agent_data['role'] = agent_data.get('role', '') or 'field_agent'
                    agent_data['region'] = agent_data.get('region', '') or ''
                    agent_data['state'] = agent_data.get('state', '') or ''
                    agent_data['lga'] = agent_data.get('lga', '') or ''

                    # Get assigned outlets count (outlets that have pending executions for this agent)
                    cursor.execute('''
                        SELECT COUNT(DISTINCT outlet_id) as assigned_count
                        FROM executions
                        WHERE agent_id = ?
                    ''', (agent_data['id'],))

                    assigned_result = cursor.fetchone()
                    agent_data['outlets_assigned'] = assigned_result['assigned_count'] if assigned_result else 0

                    # Calculate coverage percentage
                    if agent_data['outlets_assigned'] > 0:
                        agent_data['coverage_percentage'] = round(
                            (agent_data['outlets_visited'] / agent_data['outlets_assigned']) * 100, 2
                        )
                    else:
                        agent_data['coverage_percentage'] = 0

                    agents.append(agent_data)

                total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

            return jsonify({
                'agents': agents,
                'pagination': {
                    'total_count': total_count,
                    'total_pages': total_pages,
                    'current_page': page,
                    'per_page': per_page
                }
            })
            
        except Exception as e:
            print(f"Error in agent_performance: {str(e)}")
            return jsonify({'error': f'Internal server error: {str(e)}'}), 500

    @app.route('/reports')
    def reports():
        if 'user_id' not in session:
            return redirect(url_for('login'))

        return render_template(
            'reports.html',
            role=session.get('role'),
            user_id=session.get('user_id')
        )

    @app.route('/recent_executions')
    def recent_executions():
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401

        with get_db_cursor() as (conn, c):
            if session['role'] == 'admin':
                c.execute('''
                    SELECT e.id, e.execution_date, e.status,
                           o.outlet_name, o.state, o.local_govt,
                           u.full_name as agent_name
                    FROM executions e
                    JOIN outlets o ON e.outlet_id = o.id
                    JOIN users u ON e.agent_id = u.id
                    WHERE datetime(e.execution_date) >= datetime('now', '-2 days')
                    ORDER BY e.execution_date DESC
                    LIMIT 5
                ''')
            else:
                c.execute('''
                    SELECT e.id, e.execution_date, e.status,
                           o.outlet_name, o.state, o.local_govt,
                           u.full_name as agent_name
                    FROM executions e
                    JOIN outlets o ON e.outlet_id = o.id
                    JOIN users u ON e.agent_id = u.id
                    WHERE e.agent_id = ? AND datetime(e.execution_date) >= datetime('now', '-2 days')
                    ORDER BY e.execution_date DESC
                    LIMIT 5
                ''', (session['user_id'],))

            executions = []
            for row in c.fetchall():
                executions.append({
                    'id': row['id'],
                    'date': row['execution_date'].split(' ')[0],
                    'outlet_name': row['outlet_name'],
                    'location': f"{row['state']}, {row['local_govt']}",
                    'agent_name': row['agent_name'],
                    'status': row['status']
                })

        return jsonify({'executions': executions})

    @app.route('/all_visitation')
    @login_required
    def all_visitation():
        # Get filter and pagination parameters
        filters = {
            'region': request.args.get('region', ''),
            'state': request.args.get('state', ''),
            'local_govt': request.args.get('local_govt', ''),
            'outlet_type': request.args.get('outlet_type', ''),
            'search': request.args.get('search', '')
        }

        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', DEFAULT_PER_PAGE, type=int), MAX_PER_PAGE)
        offset = (page - 1) * per_page

        with get_db_cursor() as (conn, cursor):
            # Get outlets that have NOT been visited in the last 7 days
            base_query = """
                SELECT o.* FROM outlets o
                WHERE o.id NOT IN (
                    SELECT DISTINCT outlet_id FROM executions
                    WHERE execution_date >= datetime('now', '-7 days')
                    AND status = 'Completed'
                )
            """
            count_query = """
                SELECT COUNT(*) FROM outlets o
                WHERE o.id NOT IN (
                    SELECT DISTINCT outlet_id FROM executions
                    WHERE execution_date >= datetime('now', '-7 days')
                    AND status = 'Completed'
                )
            """

            params = []
            count_params = []

            # Role-based filter for field agents
            user_info = get_session_user_info()
            if user_info['role'] == 'field_agent':
                base_query += " AND o.region = ?"
                count_query += " AND o.region = ?"
                params.append(user_info['region'])
                count_params.append(user_info['region'])

                if user_info['state']:
                    base_query += " AND o.state = ?"
                    count_query += " AND o.state = ?"
                    params.append(user_info['state'])
                    count_params.append(user_info['state'])

            # User selected filter
            query, params = build_filter_query(base_query, {
                'o.region': filters['region'],
                'o.state': filters['state'],
                'o.local_govt': filters['local_govt'],
                'o.outlet_type': filters['outlet_type'],
                'search': filters['search']
            }, params)

            count_query, count_params = build_filter_query(count_query, {
                'o.region': filters['region'],
                'o.state': filters['state'],
                'o.local_govt': filters['local_govt'],
                'o.outlet_type': filters['outlet_type'],
                'search': filters['search']
            }, count_params)

            cursor.execute(count_query, count_params)
            total_outlets = cursor.fetchone()[0]

            # Pagination
            query += " ORDER BY o.outlet_name ASC LIMIT ? OFFSET ?"
            params.extend([per_page, offset])

            cursor.execute(query, params)
            outlets = cursor.fetchall()

        pagination = calculate_pagination(total_outlets, page, per_page)

        return render_template('all_visitation.html',
                            outlets=outlets,
                            page=pagination.get('current_page', page),
                            total_pages=pagination.get('total_pages'),
                            total_outlets=total_outlets,
                            region=filters['region'],
                            state=filters['state'],
                            local_govt=filters['local_govt'],
                            outlet_type=filters['outlet_type'])

    @app.route('/debug/session')
    @login_required
    def debug_session():
        """Debug route to check session data and role filtering - remove in production"""
        user_info = get_session_user_info()
        
        # Test query for role-based filtering
        with get_db_cursor() as (conn, cursor):
            # Test the same query as all_visitation route
            base_query = """
                SELECT o.id, o.outlet_name, o.region, o.state FROM outlets o
                WHERE o.id NOT IN (
                    SELECT DISTINCT outlet_id FROM executions
                    WHERE execution_date >= datetime('now', '-7 days')
                    AND status = 'Completed'
                )
            """
            
            params = []
            debug_info = {
                'session_data': dict(session),
                'user_info': user_info,
                'original_query': base_query
            }
            
            # Apply role-based filter like in all_visitation
            if user_info['role'] == 'field_agent':
                base_query += " AND o.region = ?"
                params.append(user_info['region'])
                debug_info['role_filter_applied'] = True
                debug_info['filtered_query'] = base_query
                debug_info['filter_params'] = params
                
                if user_info['state']:
                    base_query += " AND o.state = ?"
                    params.append(user_info['state'])
            else:
                debug_info['role_filter_applied'] = False
            
            # Execute and count results
            base_query += " LIMIT 10"  # Limit for debug
            cursor.execute(base_query, params)
            outlets = cursor.fetchall()
            
            debug_info['query_results_count'] = len(outlets)
            debug_info['sample_outlets'] = [dict(row) for row in outlets[:5]]
            
            # Also check total outlets for this user
            if user_info['role'] == 'field_agent':
                cursor.execute("SELECT COUNT(*) FROM outlets WHERE region = ?", (user_info['region'],))
            else:
                cursor.execute("SELECT COUNT(*) FROM outlets")
            
            debug_info['total_outlets_for_user'] = cursor.fetchone()[0]
        
        return jsonify(debug_info)

    @app.route('/assign_execution/<int:outlet_id>')
    def assign_execution(outlet_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        conn = get_db_connection()
        c = conn.cursor()

        c.execute('''
        SELECT id FROM executions
        WHERE outlet_id = ? AND agent_id = ? AND status = 'Pending'
        ''', (outlet_id, session['user_id']))

        existing = c.fetchone()

        if existing:
            execution_id = existing[0]
        else:
            c.execute('''
            INSERT INTO executions
            (outlet_id, agent_id, execution_date, status)
            VALUES (?, ?, ?, ?)
            ''', (
                outlet_id,
                session['user_id'],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Pending'
            ))

            conn.commit()
            execution_id = c.lastrowid

        conn.close()

        return redirect(url_for('new_execution', outlet_id=outlet_id))


   
    @app.route('/api/posm_deployments/export')
    def export_posm_deployments():
        export_type = request.args.get('type', 'csv')
        per_page = int(request.args.get('per_page', 1000))
        region = request.args.get('region')
        state = request.args.get('state')
        date_range = request.args.get('date_range')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        df = get_posm_deployments_data(
            region=region,
            state=state,
            date_range=date_range,
            start_date=start_date,
            end_date=end_date
        )


        # Define columns to remove
        removed_columns = [
            'Region', 
            'LGA', 
            'Executions', 
            'Assigned', 
            'Visited', 
            'Coverage (%)', 
            'Latitude', 
            'Longitude'
        ]

        # Define headers in correct order
        headers = [
            'Agent Name', 'URN', 'Retail Point Name', 'Address', 'Phone', 'Retail Point Type',
            'Region', 'State', 'LGA', 'Executions', 'Assigned', 'Visited', 'Coverage (%)',
            'Table', 'Chair', 'Parasol', 'Tarpaulin', 'Hawker Jacket', 'Cup',
            'Latitude', 'Longitude', 'Before Image', 'After Image'
        ]

        # Create headers list without the removed columns
        filtered_headers = [col for col in headers if col not in removed_columns]
        
        # Rename columns to match headers if needed
        col_mapping = {
            'agent_name': 'Agent Name',
            'urn': 'URN',
            'outlet_name': 'Retail Point Name',
            'address': 'Address',
            'phone': 'Phone',
            'outlet_type': 'Retail Point Type',
            'region': 'Region',
            'state': 'State',
            'local_govt': 'LGA',
            'execution_count': 'Executions',
            'assigned': 'Assigned',
            'visited': 'Visited',
            'coverage': 'Coverage (%)',
            'table': 'Table',
            'chair': 'Chair',
            'parasol': 'Parasol',
            'tarpaulin': 'Tarpaulin',
            'hawker_jacket': 'Hawker Jacket',
            'cup': 'Cup',
            'latitude': 'Latitude',
            'longitude': 'Longitude',
            'before_image': 'Before Image',
            'after_image': 'After Image'
        }

        # Apply column renaming if needed
        for old_col, new_col in col_mapping.items():
            if old_col in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)
        
        # Add missing columns
        for col in filtered_headers:
            if col not in df.columns:
                df[col] = None
                
        # Keep only the columns in our filtered headers list
        df = df[filtered_headers]

        if df.empty:
            return jsonify({'error': 'No data found for the selected filters'}), 404

        # CSV
        if export_type == 'csv':
            output = BytesIO()
            df.to_csv(output, index=False)
            output.seek(0)
            return send_file(output, mimetype='text/csv',
                            download_name='posm_deployments.csv', as_attachment=True)

        # XLSX
        elif export_type == 'xlsx':
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='POSM Deployments')

                workbook = writer.book
                worksheet = writer.sheets['POSM Deployments']
                header_format = workbook.add_format({
                    'bold': True, 'text_wrap': True, 'valign': 'top',
                    'fg_color': '#4472C4', 'font_color': 'white', 'border': 1
                })
                for col_num, col_name in enumerate(df.columns):
                    worksheet.write(0, col_num, col_name, header_format)

                    # Convert all values in the column to string, then compute the max length safely
                    col_data = df[col_name].astype(str)
                    max_val_len = col_data.map(len).max() if not col_data.empty else 0
                    max_len = max(max_val_len, len(str(col_name))) + 2

                    worksheet.set_column(col_num, col_num, max_len)

            output.seek(0)
            return send_file(output,
                            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                            download_name='posm_deployments.xlsx', as_attachment=True)

        elif export_type == 'pdf':
            output = BytesIO()

            from reportlab.lib.pagesizes import landscape, A3
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.lib.utils import ImageReader
            from flask import send_file
            import requests

            # Base image URL to prepend to image filenames
            BASE_IMAGE_URL = "https://betadev.pythonanywhere.com/static/uploads/"
            # BASE_IMAGE_URL = "http://localhost:5000/static/uploads/"

            def fetch_image(url, width=1.0 * inch, height=1.0 * inch):
                try:
                    response = requests.get(url)
                    if response.status_code == 200:
                        return Image(BytesIO(response.content), width=width, height=height)
                    else:
                        return Paragraph("Image not found")
                except:
                    return Paragraph("Error loading image")

            # Prepare PDF document
            doc = SimpleDocTemplate(
                output,
                pagesize=landscape(A3),
                leftMargin=0.4 * inch,
                rightMargin=0.4 * inch,
                topMargin=0.4 * inch,
                bottomMargin=0.4 * inch
            )

            # Create header row
            headers = df.columns.tolist()

            # Calculate column widths dynamically
            col_widths = []
            min_width = 0.7 * inch
            max_width = 2.2 * inch

            for col in headers:
                if col in ['Before Image', 'After Image']:
                    col_widths.append(1.5 * inch)
                else:
                    max_len = max(len(str(val)) for val in df[col][:20])
                    estimated_width = max(min_width, min(max_len * 0.07 * inch, max_width))
                    col_widths.append(estimated_width)

            # Construct table data with image handling
            pdf_data = [headers]
            for idx, row in df.iterrows():
                row_items = []
                for col in headers:
                    if col in ['Before Image', 'After Image']:
                        image_url = f"{BASE_IMAGE_URL}{row[col]}" if pd.notnull(row[col]) else ""
                        row_items.append(fetch_image(image_url))
                    else:
                        row_items.append(Paragraph(str(row[col]), None))
                pdf_data.append(row_items)

            # Create table
            table = Table(pdf_data, repeatRows=1, colWidths=col_widths, hAlign='LEFT')

            # Table styles
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 7),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 4),

                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 6),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('WORDWRAP', (0, 1), (-1, -1), True),

                ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#dddddd')),

                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ])

            # Add alternating row background colors
            for row_idx in range(1, len(pdf_data)):
                if row_idx % 2 == 1:
                    style.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#f8f8f8'))

            table.setStyle(style)

            # Build and return PDF
            doc.build([table])
            output.seek(0)

            return send_file(
                output,
                mimetype='application/pdf',
                download_name='posm_deployments.pdf',
                as_attachment=True
            )

        
        return jsonify({'error': 'Invalid export type'}), 400

   
    @app.context_processor
    def inject_now():
        return {'now': datetime.now()}

    @app.context_processor
    def utility_functions():
        return {
            'min': min,
            'max': max
        }

    @app.context_processor
    def inject_profile():
        """Inject profile data into all templates for dynamic branding"""
        from .models import get_profile
        try:
            profile = get_profile()
            return {'profile': profile} if profile else {'profile': {
                'company_name': 'DANGOTE',
                'app_title': 'POSM Retail Activation 2025',
                'primary_color': '#fdcc03',
                'secondary_color': '#f8f9fa',
                'accent_color': '#343a40',
                'logo_path': 'img/dangote-logo.png',
                'favicon_path': 'img/favicon.png'
            }}
        except Exception:
            # Fallback to default values if profile table doesn't exist yet
            return {'profile': {
                'company_name': 'DANGOTE',
                'app_title': 'POSM Retail Activation 2025',
                'primary_color': '#fdcc03',
                'secondary_color': '#f8f9fa',
                'accent_color': '#343a40',
                'logo_path': 'img/dangote-logo.png',
                'favicon_path': 'img/favicon.png'
            }}