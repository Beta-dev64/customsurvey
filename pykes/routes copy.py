import sqlite3  # Add this line at the top with other imports
from flask import render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory, make_response, send_file
from datetime import datetime
import json
import os
import uuid
from werkzeug.utils import secure_filename
from .models import get_db_connection, UPLOAD_FOLDER, DB_PATH
from .utils import allowed_file, save_base64_image, DANGOTE_PRODUCTS

import pandas as pd
from io import BytesIO
# import xlsxwriter
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
import requests

def init_routes(app):
    @app.route('/')
    def index():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return render_template('dashboard.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            conn = get_db_connection()
            c = conn.cursor()

            c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            user = c.fetchone()

            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['full_name'] = user['full_name']
                session['region'] = user['region']
                session['state'] = user['state'] if user['state'] is not None else ""
                session['lga'] = user['lga'] if user['lga'] is not None else ""

                return redirect(url_for('index'))
            else:
                flash('Invalid credentials', 'danger')

            conn.close()

        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.route('/outlets')
    def outlets():
        if 'user_id' not in session:
            return redirect(url_for('login'))

        # Get filter parameters from request
        region = request.args.get('region', '')
        state = request.args.get('state', '')
        local_govt = request.args.get('local_govt', '')
        outlet_type = request.args.get('outlet_type', '')
        search = request.args.get('search', '')

        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page

        conn = get_db_connection()
        c = conn.cursor()

        # Build the query with filter conditions
        query = """
            SELECT o.* FROM outlets o
            WHERE 1=1
            AND o.id NOT IN (
                SELECT DISTINCT outlet_id FROM executions
                WHERE status = 'Completed'
            )
        """
        count_query = """
            SELECT COUNT(*) FROM outlets o
            WHERE 1=1
            AND o.id NOT IN (
                SELECT DISTINCT outlet_id FROM executions
                WHERE status = 'Completed'
            )
        """
        params = []

        # Add search condition if search parameter is provided
        if search:
            search_term = f"%{search}%"
            query += """ AND (
                o.outlet_name LIKE ? OR
                o.customer_name LIKE ? OR
                o.address LIKE ? OR
                o.phone LIKE ? OR
                o.urn LIKE ?
            )"""
            count_query += """ AND (
                o.outlet_name LIKE ? OR
                o.customer_name LIKE ? OR
                o.address LIKE ? OR
                o.phone LIKE ? OR
                o.urn LIKE ?
            )"""
            params.extend([search_term, search_term, search_term, search_term, search_term])

        # Add role-based filtering
        if session['role'] == 'field_agent':
            query += " AND o.region = ?"
            count_query += " AND o.region = ?"
            params.append(session['region'])

            if session['state']:
                query += " AND o.state = ?"
                count_query += " AND o.state = ?"
                params.append(session['state'])

        # Add user-selected filters
        if region:
            query += " AND o.region = ?"
            count_query += " AND o.region = ?"
            params.append(region)

        if state:
            query += " AND o.state = ?"
            count_query += " AND o.state = ?"
            params.append(state)

        if local_govt:
            query += " AND o.local_govt = ?"
            count_query += " AND o.local_govt = ?"
            params.append(local_govt)

        if outlet_type:
            query += " AND o.outlet_type = ?"
            count_query += " AND o.outlet_type = ?"
            params.append(outlet_type)

        # Get total count for pagination
        c.execute(count_query, params)
        total_outlets = c.fetchone()[0]

        # Add pagination to the main query
        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, offset])

        # Execute the query
        c.execute(query, params)
        outlets = c.fetchall()

        # Calculate total pages
        total_pages = (total_outlets + per_page - 1) // per_page

        conn.close()

        return render_template('outlets.html',
                            outlets=outlets,
                            page=page,
                            total_pages=total_pages,
                            total_outlets=total_outlets,
                            region=region,
                            state=state,
                            local_govt=local_govt,
                            outlet_type=outlet_type)

    @app.route('/execution/new/<int:outlet_id>', methods=['GET', 'POST'])
    def new_execution(outlet_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        if request.method == 'GET':
            conn = get_db_connection()
            c = conn.cursor()

            c.execute('''
            SELECT id FROM executions
            WHERE outlet_id = ? AND agent_id = ? AND status = 'Pending'
            ''', (outlet_id, session['user_id']))

            existing = c.fetchone()

            if not existing:
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
            conn.close()

        if request.method == 'POST':
            before_filename = None
            after_filename = None


            if 'before_image' in request.files and request.files['before_image'].filename:
                before_image = request.files['before_image']
                if allowed_file(before_image.filename):
                    before_filename = f"{uuid.uuid4()}_{secure_filename(before_image.filename)}"
                    before_image.save(os.path.join(UPLOAD_FOLDER, before_filename))

            if 'after_image' in request.files and request.files['after_image'].filename:
                after_image = request.files['after_image']
                if allowed_file(after_image.filename):
                    after_filename = f"{uuid.uuid4()}_{secure_filename(after_image.filename)}"
                    after_image.save(os.path.join(UPLOAD_FOLDER, after_filename))

            before_captured = request.form.get('before_captured_image')
            if before_captured and not before_filename:
                before_filename = save_base64_image(before_captured, 'before')

            after_captured = request.form.get('after_captured_image')
            if after_captured and not after_filename:
                after_filename = save_base64_image(after_captured, 'after')

            latitude = request.form.get('latitude')
            longitude = request.form.get('longitude')
            notes = request.form.get('notes')

            products = {}
            for product in DANGOTE_PRODUCTS:
                products[product] = request.form.get(f"product_{product.replace(' ', '_')}", "No") == "Yes"

            products_json = json.dumps(products)

            conn = get_db_connection()
            c = conn.cursor()

            c.execute('''
            SELECT id FROM executions
            WHERE outlet_id = ? AND agent_id = ? AND status = 'Pending'
            ''', (outlet_id, session['user_id']))

            existing = c.fetchone()

            if existing:
                c.execute('''
                UPDATE executions
                SET before_image = ?, after_image = ?, latitude = ?, longitude = ?,
                    notes = ?, products_available = ?, status = ?, execution_date = ?
                WHERE id = ?
                ''', (
                    before_filename,
                    after_filename,
                    latitude,
                    longitude,
                    notes,
                    products_json,
                    'Completed',
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    existing[0]
                ))
            else:
                c.execute('''
                INSERT INTO executions
                (outlet_id, agent_id, execution_date, before_image, after_image, latitude, longitude, notes, products_available, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    outlet_id,
                    session['user_id'],
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    before_filename,
                    after_filename,
                    latitude,
                    longitude,
                    notes,
                    products_json,
                    'Completed'
                ))

            conn.commit()
            conn.close()

            flash('Visitation recorded successfully', 'success')
            return redirect(url_for('outlets'))

        conn = get_db_connection()
        c = conn.cursor()

        c.execute("SELECT * FROM outlets WHERE id = ?", (outlet_id,))
        outlet = c.fetchone()

        conn.close()

        if not outlet:
            flash('Retail Point not found', 'danger')
            return redirect(url_for('outlets'))

        return render_template('new_execution.html', outlet=outlet, products=DANGOTE_PRODUCTS)

    @app.route('/executions')
    def executions():
        if 'user_id' not in session:
            return redirect(url_for('login'))

        conn = get_db_connection()
        c = conn.cursor()

        # Collect filters from query parameters
        agent_id = request.args.get('agent_id')
        region = request.args.get('region')
        status = request.args.get('status')  # Can be a single status or comma-separated
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        query = '''
        SELECT e.*, o.outlet_name, o.urn, o.state, o.region, o.local_govt, u.full_name as agent_name
        FROM executions e
        JOIN outlets o ON e.outlet_id = o.id
        JOIN users u ON e.agent_id = u.id
        WHERE 1=1
        '''
        params = []

        # Apply filters based on role or passed agent_id
        if agent_id:
            query += ' AND e.agent_id = ?'
            params.append(agent_id)
        elif session['role'] == 'field_agent':
            query += ' AND e.agent_id = ?'
            params.append(session['user_id'])

        if region:
            query += ' AND o.region = ?'
            params.append(region)

        if status:
            status_list = [s.strip() for s in status.split(',') if s.strip()]
            placeholders = ','.join('?' for _ in status_list)
            query += f' AND e.status IN ({placeholders})'
            params.extend(status_list)

        if start_date:
            query += ' AND e.execution_date >= ?'
            params.append(start_date)

        if end_date:
            query += ' AND e.execution_date <= ?'
            params.append(end_date)

        query += ' ORDER BY e.execution_date DESC'

        c.execute(query, params)
        executions = c.fetchall()
        conn.close()

        return render_template('executions.html', executions=executions)
        

    @app.route('/execution/<int:execution_id>')
    def execution_detail(execution_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        conn = get_db_connection()
        c = conn.cursor()

        c.execute('''
        SELECT e.*, o.outlet_name, o.urn, o.state, o.region, o.local_govt, o.customer_name, o.address, o.outlet_type, u.full_name as agent_name
        FROM executions e
        JOIN outlets o ON e.outlet_id = o.id
        JOIN users u ON e.agent_id = u.id
        WHERE e.id = ?
        ''', (execution_id,))

        execution = c.fetchone()
        conn.close()

        if not execution:
            flash('Execution not found', 'danger')
            return redirect(url_for('executions'))

        products = json.loads(execution['products_available']) if execution['products_available'] else {}

        return render_template('execution_detail.html', execution=execution, products=products)

    @app.route('/dashboard/data')
    def dashboard_data():
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401

        conn = get_db_connection()
        c = conn.cursor()

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

        conn.close()

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

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

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
        if request.args.get('region'):
            query += " AND o.region = ?"
            params.append(request.args.get('region'))
        if request.args.get('state'):
            query += " AND o.state = ?"
            params.append(request.args.get('state'))

        count_query = f"SELECT COUNT(*) FROM ({query})"
        conn = get_db_connection()
        total_count = conn.execute(count_query, params).fetchone()[0]

        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])

        conn.row_factory = sqlite3.Row
        executions = conn.execute(query, params).fetchall()
        conn.close()

        executions_data = []
        for exec_row in executions:
            execution = dict(exec_row)
            execution['coverage_percentage'] = round((execution.get('outlets_visited', 0) / execution.get('outlets_assigned', 1)) * 100, 2)
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



 
 


 

    def get_posm_deployments_data(region=None, state=None, date_range=None, start_date=None, end_date=None):

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

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

        # count_query = f"SELECT COUNT(*) FROM ({query})"
        conn = get_db_connection()
        # total_count = conn.execute(count_query, params).fetchone()[0]

        # query += " LIMIT ? OFFSET ?"
        # params.extend([per_page, (page - 1) * per_page])

        conn.row_factory = sqlite3.Row
        executions = conn.execute(query, params).fetchall()
        conn.close()

        # executions_data = []
        # for exec_row in executions:
        #     execution = dict(exec_row)
        #     execution['coverage_percentage'] = round((execution.get('outlets_visited', 0) / execution.get('outlets_assigned', 1)) * 100, 2)
        #     executions_data.append(execution)

 
        # df = pd.DataFrame([dict(row) for row in executions_data])
        
        executions_data = []
        for exec_row in executions:
            execution = dict(exec_row)

            # Parse the JSON string safely
            products = json.loads(execution.get('products_available', '{}'))

            # Map each relevant product field to the execution dict
            execution['table'] = products.get('Table', False)
            execution['chair'] = products.get('Chair', False)
            execution['parasol'] = products.get('Parasol', False)
            execution['tarpaulin'] = products.get('Tarpaulin', False)
            execution['hawker_jacket'] = products.get('Hawker Jacket', False)
            execution['cup'] = products.get('Cups', False)

            # Add calculated field
            execution['coverage_percentage'] = round(
                (execution.get('outlets_visited', 0) / execution.get('outlets_assigned', 1)) * 100, 2
            )

            executions_data.append(execution)

        # Create DataFrame
        df = pd.DataFrame([dict(row) for row in executions_data])

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
            'outlets_visited': 'Visited',
            'outlets_assigned': 'Assigned',
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

        # Full list of columns (for reference if we need to add back removed columns)
        all_headers = [
            'Agent Name', 'URN', 'Retail Point Name', 'Address', 'Phone', 'Retail Point Type',
            'Region', 'State', 'LGA', 'Executions', 'Assigned', 'Visited', 'Coverage (%)',
            'Table', 'Chair', 'Parasol', 'Tarpaulin', 'Hawker Jacket', 'Cup',
            'Latitude', 'Longitude', 'Before Image', 'After Image'
        ]

        # Create headers list without the removed columns
        headers = [col for col in all_headers if col not in removed_columns]

        #subset_df = df[['Table', 'Chair', 'Parasol', 'Tarpaulin', 'Hawker Jacket', 'Cup']]
        # print(df.columns)

        # Add missing columns
        for col in headers:
            if col not in df.columns:
                df[col] = None

        # Keep only the columns in our headers list
        df = df[headers]

        # return df

        # Rename columns
        # df = df.rename(columns={
        #     'agent_name': 'Agent Name',
        #     'urn': 'URN',
        #     'outlet_name': 'Outlet Name',
        #     'address': 'Address',
        #     'phone': 'Phone',
        #     'outlet_type': 'Outlet Type',
        #     'outlet_region': 'Region',
        #     'outlet_state': 'State',
        #     'outlet_lga': 'LGA',
        #     'outlets_visited': 'Visited',
        #     'outlets_assigned': 'Assigned',
        #     'table': 'Table',
        #     'chair': 'Chair',
        #     'parasol': 'Parasol',
        #     'tarpaulin': 'Tarpaulin',
        #     'hawker_jacket': 'Hawker Jacket',
        #     'cup': 'Cup',
        #     'latitude': 'Latitude',
        #     'longitude': 'Longitude',
        #     'before_image': 'Before Image',
        #     'after_image': 'After Image'
        # })

        # # Final column structure
        # headers = [
        #     'Agent Name', 'URN', 'Outlet Name', 'Address', 'Phone', 'Outlet Type',
        #     'Region', 'State', 'LGA', 'Executions', 'Assigned', 'Visited', 'Coverage (%)',
        #     'Table', 'Chair', 'Parasol', 'Tarpaulin', 'Hawker Jacket', 'Cup',
        #     'Latitude', 'Longitude', 'Before Image', 'After Image'
        # ]

        # for col in headers:
        #     if col not in df.columns:
        #         df[col] = None


        return df

        # return jsonify({
        #     'executions': executions_data,
        #     'pagination': {
        #         'total_count': total_count,
        #         # 'total_pages': (total_count + per_page - 1) // per_page,
        #         'current_page': page,
        #         'per_page': per_page
        #     }
        # })



    def get_posm_deployments_datad(per_page=1000, region=None, state=None):
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = '''
            SELECT
                u.full_name AS agent_name,
                o.urn, o.outlet_name, o.address, o.phone, o.outlet_type,
                o.region AS outlet_region,
                o.state AS outlet_state,
                o.local_govt AS outlet_lga,
                e.[table], e.chair, e.parasol, e.tarpaulin, e.[hawker_jacket], e.cup,
                e.before_image, e.after_image
            FROM executions e
            JOIN users u ON e.agent_id = u.id
            JOIN outlets o ON e.outlet_id = o.id
            WHERE e.status = 'Completed'
        '''

        params = []

        if region:
            query += ' AND o.region = ?'
            params.append(region)

        if state:
            query += ' AND o.state = ?'
            params.append(state)

        query += ' LIMIT ?'
        params.append(per_page)

        # Execute and fetch
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        # Convert to DataFrame
        df = pd.DataFrame([dict(row) for row in rows])

        # Compute Coverage
        df['Coverage (%)'] = round((df.get('outlets_visited', 0) / df.get('outlets_assigned', 1)) * 100, 2)

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
            'outlets_visited': 'Visited',
            'outlets_assigned': 'Assigned',
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

        # Final column structure
        headers = [
            'Agent Name', 'URN', 'Retail Point Name', 'Address', 'Phone', 'Retail Point Type',
            'Region', 'State', 'LGA', 'Executions', 'Assigned', 'Visited', 'Coverage (%)',
            'Table', 'Chair', 'Parasol', 'Tarpaulin', 'Hawker Jacket', 'Cup',
            'Latitude', 'Longitude', 'Before Image', 'After Image'
        ]

        # Add missing columns if necessary
        for col in headers:
            if col not in df.columns:
                df[col] = None

        df['Executions'] = df['Visited']  # You can adjust this as needed
        df = df[headers]
        return df




    @app.route('/api/agent_performance')
    def agent_performance():
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401

        conn = get_db_connection()
        c = conn.cursor()

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

        count_query = '''
        SELECT COUNT(DISTINCT u.id) as total_count
        FROM users u
        WHERE u.role = 'field_agent'
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
            COUNT(DISTINCT CASE WHEN e.status = 'Completed' THEN e.outlet_id ELSE NULL END) as outlets_visited,
            (SELECT COUNT(*) FROM outlets o WHERE o.region = u.region) as outlets_in_region
        FROM
            users u
        LEFT JOIN
            executions e ON u.id = e.agent_id
        WHERE
            u.role = 'field_agent'
        '''

        params = []
        count_params = []

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
                query += date_condition

        if agent_id:
            query += " AND u.id = ? "
            count_query += " AND u.id = ? "
            params.append(agent_id)
            count_params.append(agent_id)
        elif user_role == 'field_agent':
            query += " AND u.id = ? "
            count_query += " AND u.id = ? "
            params.append(current_user_id)
            count_params.append(current_user_id)

        query += " GROUP BY u.id"

        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, offset])

        c.execute(count_query, count_params)
        total_count = c.fetchone()['total_count']

        c.execute(query, params)

        agents = []
        for row in c.fetchall():
            agent_data = dict(row)

            c.execute('''
                SELECT COUNT(DISTINCT outlet_id) as assigned_count
                FROM executions
                WHERE agent_id = ? AND status = 'Pending'
            ''', (agent_data['id'],))

            assigned_result = c.fetchone()
            agent_data['outlets_assigned'] = assigned_result['assigned_count'] if assigned_result else 0

            if agent_data['outlets_assigned'] > 0:
                agent_data['coverage_percentage'] = round((agent_data['outlets_visited'] / agent_data['outlets_assigned']) * 100, 2)
            else:
                agent_data['coverage_percentage'] = 0

            agents.append(agent_data)

        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

        conn.close()

        return jsonify({
            'agents': agents,
            'pagination': {
                'total_count': total_count,
                'total_pages': total_pages,
                'current_page': page,
                'per_page': per_page
            }
        })

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

        conn = get_db_connection()
        c = conn.cursor()

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

        conn.close()

        return jsonify({'executions': executions})

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