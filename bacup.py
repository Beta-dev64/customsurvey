from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
import os
import sqlite3
import json
import base64
import re
from datetime import datetime
import pandas as pd
import uuid
from werkzeug.utils import secure_filename
from app_reports import reports_bp
from app_admin import admin_bp

app = Flask(__name__)
app.secret_key = 'dangote_cement_execution_tracker'

# Register blueprints
app.register_blueprint(reports_bp)
app.register_blueprint(admin_bp)

# Database setup
DB_PATH = 'maindatabase.db'

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
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Define allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Define Dangote product list
# DANGOTE_PRODUCTS = [
#     "Dangote Ordinary Portland Cement 42.5R",
#     "Dangote Ordinary Portland Cement 42.5N",
#     "Dangote Falcon Portland Cement",
#     "Dangote 3X Cement",
#     "Dangote BlocMaster Cement"
# ]

DANGOTE_PRODUCTS = [
    "Table",
    "Chair",
    "Parasol",
    "Parasol Stand",
    "Tarpaulin",
    "Hawker Jacket",
    "Cups"
]


# Routes
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

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name']
            session['region'] = user['region']

            # Add state and lga to session, handling cases where they might not exist
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
    search = request.args.get('search', '')  # Get search parameter

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
        # Filter by region for field agents
        query += " AND o.region = ?"
        count_query += " AND o.region = ?"
        params.append(session['region'])

        # Also filter by state if agent has a state assigned
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

def save_base64_image(image_data, prefix):
    # Check if the image data is a Data URL
    if image_data and image_data.startswith('data:image'):
        # Extract the base64 data
        format, base64_str = image_data.split(';base64,')

        # Get the file extension
        ext = format.split('/')[-1]

        # Generate a unique filename
        filename = f"{prefix}_{uuid.uuid4()}.{ext}"

        # Convert base64 to binary
        try:
            binary_data = base64.b64decode(base64_str)

            # Save the file
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            with open(filepath, 'wb') as f:
                f.write(binary_data)

            return filename
        except Exception as e:
            print(f"Error saving base64 image: {e}")
            return None

    return None

@app.route('/execution/new/<int:outlet_id>', methods=['GET', 'POST'])
def new_execution(outlet_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Create a pending execution record when the page is first loaded (GET request)
    if request.method == 'GET':
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Check if there's already a pending execution for this outlet and agent
        c.execute('''
        SELECT id FROM executions
        WHERE outlet_id = ? AND agent_id = ? AND status = 'Pending'
        ''', (outlet_id, session['user_id']))

        existing = c.fetchone()

        if not existing:
            # Create a new pending execution
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
        # Initialize filenames
        before_filename = None
        after_filename = None

        # Handle file uploads
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

        # Handle base64 images (from camera capture)
        before_captured = request.form.get('before_captured_image')
        if before_captured and not before_filename:
            before_filename = save_base64_image(before_captured, 'before')

        after_captured = request.form.get('after_captured_image')
        if after_captured and not after_filename:
            after_filename = save_base64_image(after_captured, 'after')

        # Get form data
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        notes = request.form.get('notes')

        # Get product availability as JSON
        products = {}
        for product in DANGOTE_PRODUCTS:
            products[product] = request.form.get(f"product_{product.replace(' ', '_')}", "No") == "Yes"

        products_json = json.dumps(products)

        # Save to database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Check if there's a pending execution to update
        c.execute('''
        SELECT id FROM executions
        WHERE outlet_id = ? AND agent_id = ? AND status = 'Pending'
        ''', (outlet_id, session['user_id']))

        existing = c.fetchone()

        if existing:
            # Update the existing pending execution
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
            # Create a new execution record if somehow there's no pending one
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

        flash('Execution recorded successfully', 'success')
        return redirect(url_for('outlets'))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM outlets WHERE id = ?", (outlet_id,))
    outlet = c.fetchone()

    conn.close()

    if not outlet:
        flash('Outlet not found', 'danger')
        return redirect(url_for('outlets'))

    return render_template('new_execution.html', outlet=outlet, products=DANGOTE_PRODUCTS)

@app.route('/executions')
def executions():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    agent_id = request.args.get('agent_id')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = '''
    SELECT e.*, o.outlet_name, o.urn, o.state, o.region, o.local_govt, u.full_name as agent_name
    FROM executions e
    JOIN outlets o ON e.outlet_id = o.id
    JOIN users u ON e.agent_id = u.id
    '''
    params = []
    if agent_id:
        query += " WHERE e.agent_id = ?"
        params.append(agent_id)
    elif session['role'] == 'field_agent':
        query += " WHERE e.agent_id = ?"
        params.append(session['user_id'])
    query += " ORDER BY e.execution_date DESC"

    c.execute(query, params)
    executions = c.fetchall()
    conn.close()

    return render_template('executions.html', executions=executions)

@app.route('/execution/<int:execution_id>')
def execution_detail(execution_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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

    # Parse product availability
    products = json.loads(execution['products_available']) if execution['products_available'] else {}

    return render_template('execution_detail.html', execution=execution, products=products)

@app.route('/dashboard/data')
def dashboard_data():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Filter data based on user role
    is_admin = session['role'] == 'admin'
    user_id = session['user_id']
    user_region = session['region']
    user_state = session.get('state', '')

    # Get summary metrics
    if is_admin:
        # Admin sees all outlets
        c.execute("SELECT COUNT(*) as count FROM outlets")
        total_outlets = c.fetchone()['count']

        # Get total completed executions
        c.execute("SELECT COUNT(*) as count FROM executions WHERE status = 'Completed'")
        total_executions = c.fetchone()['count']

        # Calculate coverage percentage
        coverage_percentage = round((total_executions / total_outlets * 100), 2) if total_outlets > 0 else 0

        # Get active agents count
        c.execute("SELECT COUNT(DISTINCT agent_id) as count FROM executions WHERE status = 'Completed'")
        active_agents = c.fetchone()['count']
    else:
        # Agent sees outlets in their state
        if user_state:
            c.execute("SELECT COUNT(*) as count FROM outlets WHERE state = ?", (user_state,))
        else:
            c.execute("SELECT COUNT(*) as count FROM outlets WHERE region = ?", (user_region,))
        total_outlets = c.fetchone()['count']

        # Get total completed executions by this agent
        c.execute("SELECT COUNT(*) as count FROM executions WHERE agent_id = ? AND status = 'Completed'", (user_id,))
        total_executions = c.fetchone()['count']

        # Get total outlets assigned to this agent (including completed and pending)
        c.execute("""
            SELECT COUNT(DISTINCT outlet_id) as count
            FROM executions
            WHERE agent_id = ?
        """, (user_id,))
        assigned_outlets = c.fetchone()['count']

        # Calculate coverage percentage based on assigned outlets
        coverage_percentage = round((total_executions / assigned_outlets * 100), 2) if assigned_outlets > 0 else 0

        # For agents, active_agents is always 1 (themselves)
        active_agents = 1

    # Get outlet counts by region or LGA based on role
    if is_admin:
        # Admin sees outlets by region
        c.execute("SELECT region, COUNT(*) as count FROM outlets GROUP BY region")
        regions = {row['region']: row['count'] for row in c.fetchall()}

        # Get outlet counts by state
        c.execute("SELECT state, COUNT(*) as count FROM outlets GROUP BY state")
        states = {row['state']: row['count'] for row in c.fetchall()}
    else:
        # Agents see outlets by LGA within their region
        if user_state:
            c.execute("SELECT local_govt, COUNT(*) as count FROM outlets WHERE state = ? GROUP BY local_govt",
                    (user_state,))
        else:
            c.execute("SELECT local_govt, COUNT(*) as count FROM outlets WHERE region = ? GROUP BY local_govt",
                    (user_region,))
        regions = {row['local_govt']: row['count'] for row in c.fetchall()}

        # Get outlet counts by state (filtered by region for agents)
        c.execute("SELECT state, COUNT(*) as count FROM outlets WHERE region = ? GROUP BY state",
                 (user_region,))
        states = {row['state']: row['count'] for row in c.fetchall()}

    # Get execution counts by day (filtered for agents)
    if is_admin:
        c.execute("SELECT DATE(execution_date) as date, COUNT(*) as count FROM executions WHERE status = 'Completed' GROUP BY DATE(execution_date)")
    else:
        c.execute("SELECT DATE(execution_date) as date, COUNT(*) as count FROM executions WHERE agent_id = ? AND status = 'Completed' GROUP BY DATE(execution_date)",
                 (user_id,))
    executions_by_date = {row['date']: row['count'] for row in c.fetchall()}

    # Get execution count by agent (admin sees all, agents see only themselves)
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

    # Get outlet type distribution (filtered for agents)
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
        'coverage_percentage': (total_executions / total_outlets) * 100, #coverage_percentage,
        'active_agents': active_agents,
        'regions': regions,  # For agents, this will be LGAs instead of regions
        'states': states,
        'executions_by_date': executions_by_date,
        'executions_by_agent': executions_by_agent,
        'outlet_types': outlet_types
    })

@app.route('/api/outlets')
def api_outlets():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Filter parameters
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

    # Restrict by region for agents
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

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Build base query with additional outlet details
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

    # Apply filters
    params = []
    if request.args.get('region'):
        query += " AND o.region = ?"
        params.append(request.args.get('region'))
    if request.args.get('state'):
        query += " AND o.state = ?"
        params.append(request.args.get('state'))

    # Count total records
    count_query = f"SELECT COUNT(*) FROM ({query})"
    conn = sqlite3.connect(DB_PATH)
    total_count = conn.execute(count_query, params).fetchone()[0]

    # Apply pagination
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])

    # Execute query
    conn.row_factory = sqlite3.Row
    executions = conn.execute(query, params).fetchall()
    conn.close()

    # Format response
    executions_data = []
    for exec_row in executions:
        execution = dict(exec_row)
        # Calculate coverage percentage
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


    

@app.route('/api/agent_performance')
def agent_performance():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    offset = (page - 1) * per_page

    # Get search and filter parameters
    search_term = request.args.get('search', '')
    region = request.args.get('region', '')
    state = request.args.get('state', '')
    date_range = request.args.get('date_range', '')

    # Check if we're filtering for a specific agent
    agent_id = request.args.get('agent_id')
    user_role = session.get('role')
    current_user_id = session.get('user_id')

    # Base query for counting total records
    count_query = '''
    SELECT COUNT(DISTINCT u.id) as total_count
    FROM users u
    WHERE u.role = 'field_agent'
    '''

    # Base query for fetching data
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

    # Add search condition if provided
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

    # Add region filter if provided
    if region and region != 'all':
        query += " AND u.region = ? "
        count_query += " AND u.region = ? "
        params.append(region)
        count_params.append(region)

    # Add state filter if provided
    if state and state != 'all':
        query += " AND u.state = ? "
        count_query += " AND u.state = ? "
        params.append(state)
        count_params.append(state)

    # Add date range filter if provided
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

    # Filter by specific agent if requested or if current user is a field agent
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

    # Group by user id
    query += " GROUP BY u.id"

    # Add pagination
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, offset])

    # Get total count for pagination
    c.execute(count_query, count_params)
    total_count = c.fetchone()['total_count']

    # Execute the main query
    c.execute(query, params)

    agents = []
    for row in c.fetchall():
        agent_data = dict(row)

        # Get assigned outlets count for this specific agent (pending executions)
        c.execute('''
            SELECT COUNT(DISTINCT outlet_id) as assigned_count
            FROM executions
            WHERE agent_id = ? AND status = 'Pending'
        ''', (agent_data['id'],))

        assigned_result = c.fetchone()
        agent_data['outlets_assigned'] = assigned_result['assigned_count'] if assigned_result else 0

        # Calculate percentage of outlets visited
        if agent_data['outlets_assigned'] > 0:
            agent_data['coverage_percentage'] = round((agent_data['outlets_visited'] / agent_data['outlets_assigned']) * 100, 2)
        else:
            agent_data['coverage_percentage'] = 0

        agents.append(agent_data)

    # Calculate total pages
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

    # Pass role and user_id to the template
    return render_template(
        'reports.html',
        role=session.get('role'),
        user_id=session.get('user_id')
    )

# Add a context processor to make current date available to all templates
@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# Add a context processor to make min and max functions available to templates
@app.context_processor
def utility_functions():
    return {
        'min': min,
        'max': max
    }

@app.route('/recent_executions')
def recent_executions():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get executions from the last 48 hours
    # For agents, only show their own executions
    # For admins, show all executions
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
            'date': row['execution_date'].split(' ')[0],  # Just the date part
            'outlet_name': row['outlet_name'],
            'location': f"{row['state']}, {row['local_govt']}",
            'agent_name': row['agent_name'],
            'status': row['status']
        })

    conn.close()

    return jsonify({'executions': executions})

# Initialize database and start the app
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)


@app.route('/assign_execution/<int:outlet_id>')
def assign_execution(outlet_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Create a pending execution record
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Check if there's already a pending execution for this outlet and agent
    c.execute('''
    SELECT id FROM executions
    WHERE outlet_id = ? AND agent_id = ? AND status = 'Pending'
    ''', (outlet_id, session['user_id']))

    existing = c.fetchone()

    if existing:
        # If there's already a pending execution, use that one
        execution_id = existing[0]
    else:
        # Create a new pending execution
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

    # Redirect to the execution form
    return redirect(url_for('new_execution', outlet_id=outlet_id))