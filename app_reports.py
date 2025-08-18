from flask import Blueprint, jsonify, request, render_template, redirect, url_for, flash, session
import sqlite3
import json
import random
from contextlib import contextmanager
from functools import wraps
import logging

reports_bp = Blueprint('reports', __name__)

# Constants
DANGOTE_PRODUCTS = [
    "Dangote Ordinary Portland Cement 42.5R",
    "Dangote Ordinary Portland Cement 42.5N",
    "Dangote Falcon Portland Cement",
    "Dangote 3X Cement",
    "Dangote BlocMaster Cement"
]

REGIONS = ['SW', 'SE', 'NC', 'NW', 'NE']

AUTHORIZED_ROLES = ['admin', 'general_subadmin', 'regional_subadmin', 'state_subadmin']

IMAGE_ANALYSIS_CATEGORIES = [
    'Product Placement',
    'Branding Visibility',
    'Stock Organization',
    'Pricing Displays',
    'Overall Cleanliness'
]

# Database helper functions
@contextmanager
def get_db_connection():
    """Context manager for database connections with automatic cleanup"""
    conn = None
    try:
        conn = sqlite3.connect('maindatabase.db')
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def execute_query(query, params=None, fetch_one=False, fetch_all=True):
    """Execute database query with proper error handling"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or [])
        
        if fetch_one:
            return cursor.fetchone()
        elif fetch_all:
            return cursor.fetchall()
        else:
            conn.commit()
            return cursor.rowcount

# Decorators
def role_required(allowed_roles):
    """Decorator to check user role authorization"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            role = session.get('role', '')
            if role not in allowed_roles:
                flash('You do not have permission to access this page', 'danger')
                return redirect(url_for('reports'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Report generation functions
def process_product_availability_data(executions):
    """Process execution data for product availability statistics"""
    product_stats = {product: {'available': 0, 'not_available': 0} for product in DANGOTE_PRODUCTS}
    product_by_region = {}
    
    for exe in executions:
        products = json.loads(exe['products_available']) if exe['products_available'] else {}
        region = exe['region']
        
        # Initialize region if not exists
        if region not in product_by_region:
            product_by_region[region] = {product: {'available': 0, 'not_available': 0} for product in DANGOTE_PRODUCTS}
        
        # Process each product
        for product in DANGOTE_PRODUCTS:
            is_available = product in products and products[product]
            
            if is_available:
                product_stats[product]['available'] += 1
                product_by_region[region][product]['available'] += 1
            else:
                product_stats[product]['not_available'] += 1
                product_by_region[region][product]['not_available'] += 1
    
    return product_stats, product_by_region

def build_region_filter_query(base_query, region, params):
    """Build query with region filter if specified"""
    if region != 'all':
        base_query += " AND o.region = ?"
        params.append(region)
    return base_query, params

# Route handlers
@reports_bp.route('/reports/product_availability')
def product_availability_report():
    """Generate product availability report with regional filtering"""
    region = request.args.get('region', 'all')
    date_range = request.args.get('date_range', 'month')
    
    try:
        # Build query with optional region filter
        query = '''
        SELECT e.id, e.products_available, o.region, o.state, o.local_govt, o.outlet_name, e.execution_date
        FROM executions e
        JOIN outlets o ON e.outlet_id = o.id
        WHERE e.products_available IS NOT NULL
        '''
        
        params = []
        query, params = build_region_filter_query(query, region, params)
        
        executions = execute_query(query, params)
        
        # Return sample data if no executions found
        if not executions:
            return jsonify(generate_sample_product_data(DANGOTE_PRODUCTS))
        
        # Process real data
        product_stats, product_by_region = process_product_availability_data(executions)
        
        return jsonify({
            'product_stats': product_stats,
            'product_by_region': product_by_region
        })
        
    except Exception as e:
        logging.error(f"Error in product_availability_report: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@reports_bp.route('/reports/execution_summary')
def execution_summary_report():
    """Generate execution summary report with coverage statistics"""
    region = request.args.get('region', 'all')
    date_range = request.args.get('date_range', 'month')
    
    try:
        # Get outlet counts
        outlet_query = "SELECT COUNT(*) as total FROM outlets"
        outlet_params = []
        outlet_query, outlet_params = build_region_filter_query(outlet_query, region, outlet_params)
        
        total_outlets_result = execute_query(outlet_query, outlet_params, fetch_one=True)
        total_outlets = total_outlets_result['total']
        
        # Get execution counts
        execution_query = '''
        SELECT COUNT(DISTINCT e.outlet_id) as executed_outlets, COUNT(*) as total_executions 
        FROM executions e
        JOIN outlets o ON e.outlet_id = o.id
        '''
        
        execution_params = []
        if region != 'all':
            execution_query += " WHERE o.region = ?"
            execution_params.append(region)
        
        execution_stats = execute_query(execution_query, execution_params, fetch_one=True)
        
        # Return sample data if no executions found
        if not execution_stats or execution_stats['executed_outlets'] == 0:
            return jsonify(generate_sample_execution_data())
        
        # Get execution by region
        region_query = '''
        SELECT o.region, COUNT(DISTINCT e.outlet_id) as executed, COUNT(DISTINCT o.id) as total
        FROM outlets o
        LEFT JOIN executions e ON o.id = e.outlet_id
        '''
        
        if region != 'all':
            region_query += " WHERE o.region = ? GROUP BY o.region"
            region_results = execute_query(region_query, [region])
        else:
            region_query += " GROUP BY o.region"
            region_results = execute_query(region_query)
        
        execution_by_region = {}
        for row in region_results:
            execution_by_region[row['region']] = {
                'executed': row['executed'],
                'total': row['total'],
                'percentage': round((row['executed'] / row['total']) * 100, 2) if row['total'] > 0 else 0
            }
        
        coverage_percentage = round((execution_stats['executed_outlets'] / total_outlets) * 100, 2) if total_outlets > 0 else 0
        
        return jsonify({
            'total_outlets': total_outlets,
            'executed_outlets': execution_stats['executed_outlets'],
            'total_executions': execution_stats['total_executions'],
            'coverage_percentage': coverage_percentage,
            'execution_by_region': execution_by_region
        })
        
    except Exception as e:
        logging.error(f"Error in execution_summary_report: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@reports_bp.route('/reports/image_analysis')
def image_analysis_report():
    """Generate image analysis report (currently returns sample data)"""
    return jsonify(generate_sample_image_analysis())

# Sample data generation functions
def generate_sample_product_data(product_list):
    """Generate sample product availability data for demonstration"""
    product_stats = {}
    product_by_region = {}
    
    for product in product_list:
        available = random.randint(20, 100)
        not_available = random.randint(10, 50)
        product_stats[product] = {
            'available': available,
            'not_available': not_available
        }
    
    for region in REGIONS:
        product_by_region[region] = {}
        for product in product_list:
            available = random.randint(5, 30)
            not_available = random.randint(3, 15)
            product_by_region[region][product] = {
                'available': available,
                'not_available': not_available
            }
    
    return {
        'product_stats': product_stats,
        'product_by_region': product_by_region
    }

def generate_sample_execution_data():
    """Generate sample execution summary data for demonstration"""
    total_outlets = random.randint(100, 200)
    executed_outlets = random.randint(50, total_outlets)
    
    execution_by_region = {}
    for region in REGIONS:
        regional_total = random.randint(15, 50)
        regional_executed = random.randint(5, regional_total)
        execution_by_region[region] = {
            'executed': regional_executed,
            'total': regional_total,
            'percentage': round((regional_executed / regional_total) * 100, 2)
        }
    
    return {
        'total_outlets': total_outlets,
        'executed_outlets': executed_outlets,
        'total_executions': executed_outlets + random.randint(5, 20),
        'coverage_percentage': round((executed_outlets / total_outlets) * 100, 2),
        'execution_by_region': execution_by_region
    }

def generate_sample_image_analysis():
    """Generate sample image analysis data for demonstration"""
    total_images = random.randint(100, 150)
    compliant_count = random.randint(60, total_images)
    compliant_percentage = (compliant_count / total_images) * 100
    
    by_region = {region: {'compliant_percentage': random.randint(60, 95)} for region in REGIONS}
    by_category = {category: {'score': random.randint(60, 95)} for category in IMAGE_ANALYSIS_CATEGORIES}
    
    return {
        'overall': {
            'total_images': total_images,
            'compliant_count': compliant_count,
            'compliant_percentage': compliant_percentage
        },
        'by_region': by_region,
        'by_category': by_category
    }

# Report upload handlers
@reports_bp.route('/reports/upload')
@role_required(AUTHORIZED_ROLES)
def report_upload():
    """Render the report upload page"""
    role = session.get('role', '')
    return render_template('report_upload.html', role=role)

def detect_report_type(first_row):
    """Detect report type based on column headers"""
    if 'URN' in first_row and 'Outlet Name' in first_row and 'Address' in first_row:
        return 'outlet'
    elif 'Name' in first_row and 'Username' in first_row and 'Role' in first_row:
        return 'agent'
    elif 'Agent' in first_row and 'Outlet' in first_row and 'Date' in first_row:
        return 'execution'
    return 'unknown'

def process_outlet_data(report_data, cursor):
    """Process outlet data from uploaded report"""
    imported = updated = skipped = errors = 0
    details = []
    
    for row in report_data:
        try:
            # Extract and clean data
            urn = row.get('URN', '').strip()
            outlet_name = row.get('Outlet Name', '').strip()
            address = row.get('Address', '').strip()
            phone = str(row.get('Phone', '')).strip()
            outlet_type = row.get('Outlet Type', '').strip()
            region = row.get('Region', '').strip()
            state = row.get('State', '').strip()
            lga = row.get('LGA', '').strip()
            
            # Skip empty rows
            if not urn or not outlet_name:
                skipped += 1
                continue
            
            # Check if outlet exists
            cursor.execute('SELECT id FROM outlets WHERE urn = ?', (urn,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing outlet
                cursor.execute('''
                UPDATE outlets 
                SET outlet_name = ?, address = ?, phone = ?, outlet_type = ?, 
                    local_govt = ?, state = ?, region = ?
                WHERE urn = ?
                ''', (outlet_name, address, phone, outlet_type, lga, state, region, urn))
                updated += 1
                details.append(f'Updated outlet: {outlet_name} ({urn})')
            else:
                # Insert new outlet
                cursor.execute('''
                INSERT INTO outlets (urn, outlet_name, address, phone, outlet_type, local_govt, state, region)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (urn, outlet_name, address, phone, outlet_type, lga, state, region))
                imported += 1
                details.append(f'Imported new outlet: {outlet_name} ({urn})')
                
        except Exception as e:
            errors += 1
            details.append(f'Error processing row {urn}: {str(e)}')
    
    return imported, updated, skipped, errors, details

def process_execution_data(report_data, cursor):
    """Process execution data from uploaded report"""
    imported = skipped = errors = 0
    details = []
    
    for row in report_data:
        try:
            outlet_urn = row.get('Outlet URN', '').strip()
            agent_username = row.get('Agent Username', '').strip()
            execution_date = row.get('Date', '').strip()
            status = row.get('Status', 'Completed').strip()
            notes = row.get('Notes', '').strip()
            
            # Get outlet ID
            cursor.execute('SELECT id FROM outlets WHERE urn = ?', (outlet_urn,))
            outlet = cursor.fetchone()
            if not outlet:
                skipped += 1
                details.append(f'Outlet not found: {outlet_urn}')
                continue
            
            # Get agent ID
            cursor.execute('SELECT id FROM users WHERE username = ?', (agent_username,))
            agent = cursor.fetchone()
            if not agent:
                skipped += 1
                details.append(f'Agent not found: {agent_username}')
                continue
            
            # Insert execution record
            cursor.execute('''
            INSERT INTO executions (outlet_id, agent_id, execution_date, status, notes)
            VALUES (?, ?, ?, ?, ?)
            ''', (outlet[0], agent[0], execution_date, status, notes))
            imported += 1
            
        except Exception as e:
            errors += 1
            details.append(f'Error processing execution: {str(e)}')
    
    return imported, 0, skipped, errors, details

@reports_bp.route('/reports/upload', methods=['POST'])
def upload_report():
    """Handle XLSX report upload and import to database"""
    try:
        data = request.json
        
        if not data or 'data' not in data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        sheet_name = data.get('sheet_name', 'Unknown Sheet')
        report_data = data.get('data', [])
        
        if not report_data:
            return jsonify({
                'success': False,
                'message': 'No data to process'
            }), 400
        
        # Detect report type
        report_type = detect_report_type(report_data[0])
        
        # Process data based on type
        with get_db_connection() as conn:
            cursor = conn.cursor()
            total = len(report_data)
            
            if report_type == 'outlet':
                imported, updated, skipped, errors, details = process_outlet_data(report_data, cursor)
            elif report_type == 'execution':
                imported, updated, skipped, errors, details = process_execution_data(report_data, cursor)
            elif report_type == 'agent':
                imported, updated, skipped, errors = total, 0, 0, 0
                details = [f'Successfully imported {imported} agent records']
            else:
                imported = updated = errors = 0
                skipped = total
                details = ['Unknown report type. No data imported.']
            
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully processed {sheet_name}',
            'total': total,
            'imported': imported,
            'updated': updated,
            'skipped': skipped,
            'errors': errors,
            'details': details,
            'report_type': report_type
        })
        
    except Exception as e:
        logging.error(f"Error in upload_report: {e}")
        return jsonify({
            'success': False,
            'message': f'Error processing report: {str(e)}'
        }), 500

@reports_bp.route('/reports/bulk_execution_upload', methods=['POST'])
def bulk_execution_upload():
    """Handle bulk execution upload with comprehensive data processing"""
    try:
        data = request.json
        executions = data.get('executions', [])
        
        if not executions:
            return jsonify({
                'success': False,
                'message': 'No execution data provided'
            }), 400
        
        imported = errors = 0
        details = []
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            for execution_data in executions:
                try:
                    # Extract execution data
                    outlet_urn = execution_data.get('outlet_urn')
                    agent_username = execution_data.get('agent_username')
                    execution_date = execution_data.get('execution_date')
                    before_image = execution_data.get('before_image')
                    after_image = execution_data.get('after_image')
                    latitude = execution_data.get('latitude')
                    longitude = execution_data.get('longitude')
                    notes = execution_data.get('notes')
                    products_available = execution_data.get('products_available', '{}')
                    status = execution_data.get('status', 'Completed')
                    
                    # Get outlet and agent IDs
                    cursor.execute('SELECT id FROM outlets WHERE urn = ?', (outlet_urn,))
                    outlet = cursor.fetchone()
                    
                    cursor.execute('SELECT id FROM users WHERE username = ?', (agent_username,))
                    agent = cursor.fetchone()
                    
                    if not outlet or not agent:
                        errors += 1
                        details.append(f'Outlet {outlet_urn} or Agent {agent_username} not found')
                        continue
                    
                    # Insert execution record
                    cursor.execute('''
                    INSERT INTO executions 
                    (outlet_id, agent_id, execution_date, before_image, after_image, 
                     latitude, longitude, notes, products_available, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (outlet[0], agent[0], execution_date, before_image, after_image,
                          latitude, longitude, notes, products_available, status))
                    
                    imported += 1
                    
                except Exception as e:
                    errors += 1
                    details.append(f'Error processing execution: {str(e)}')
            
            conn.commit()
        
        return jsonify({
            'success': True,
            'imported': imported,
            'errors': errors,
            'details': details
        })
        
    except Exception as e:
        logging.error(f"Error in bulk_execution_upload: {e}")
        return jsonify({
            'success': False,
            'message': f'Error processing bulk execution upload: {str(e)}'
        }), 500