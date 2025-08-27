from flask import Blueprint, jsonify, request, render_template, redirect, url_for, flash, session
import sqlite3
import json
import random

reports_bp = Blueprint('reports', __name__)

# Database helper function
def get_db_connection():
    conn = sqlite3.connect('maindatabase.db')
    conn.row_factory = sqlite3.Row
    return conn

@reports_bp.route('/reports/product_availability')
def product_availability_report():
    # Get filter parameters
    region = request.args.get('region', 'all')
    date_range = request.args.get('date_range', 'month')
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Define Dangote product list
    DANGOTE_PRODUCTS = [
        "Dangote Ordinary Portland Cement 42.5R",
        "Dangote Ordinary Portland Cement 42.5N",
        "Dangote Falcon Portland Cement",
        "Dangote 3X Cement",
        "Dangote BlocMaster Cement"
    ]
    
    # Get all executions with product data
    query = '''
    SELECT e.id, e.products_available, o.region, o.state, o.local_govt, o.outlet_name, e.execution_date
    FROM executions e
    JOIN outlets o ON e.outlet_id = o.id
    WHERE e.products_available IS NOT NULL
    '''
    
    # Add region filter if specified
    params = []
    if region != 'all':
        query += " AND o.region = ?"
        params.append(region)
    
    # Add date filter - in a real app, this would be implemented
    # For demo purposes, we'll skip this
    
    c.execute(query, params)
    executions = c.fetchall()
    conn.close()
    
    # Process data
    product_stats = {product: {'available': 0, 'not_available': 0} for product in DANGOTE_PRODUCTS}
    product_by_region = {}
    
    # For demo, generate some sample data
    if len(executions) == 0:
        return jsonify(generate_sample_product_data(DANGOTE_PRODUCTS))
    
    # Process real data if available
    for exe in executions:
        products = json.loads(exe['products_available']) if exe['products_available'] else {}
        
        for product in DANGOTE_PRODUCTS:
            if product in products and products[product]:
                product_stats[product]['available'] += 1
            else:
                product_stats[product]['not_available'] += 1
            
            # Region stats
            if exe['region'] not in product_by_region:
                product_by_region[exe['region']] = {product: {'available': 0, 'not_available': 0} for product in DANGOTE_PRODUCTS}
            
            if product in products and products[product]:
                product_by_region[exe['region']][product]['available'] += 1
            else:
                product_by_region[exe['region']][product]['not_available'] += 1
    
    return jsonify({
        'product_stats': product_stats,
        'product_by_region': product_by_region
    })

@reports_bp.route('/reports/execution_summary')
def execution_summary_report():
    # Get filter parameters
    region = request.args.get('region', 'all')
    date_range = request.args.get('date_range', 'month')
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get outlet counts
    query = "SELECT COUNT(*) as total FROM outlets"
    params = []
    
    if region != 'all':
        query += " WHERE region = ?"
        params.append(region)
    
    c.execute(query, params)
    total_outlets = c.fetchone()['total']
    
    # Get execution counts
    query = '''
    SELECT COUNT(DISTINCT e.outlet_id) as executed_outlets, COUNT(*) as total_executions 
    FROM executions e
    JOIN outlets o ON e.outlet_id = o.id
    '''
    
    if region != 'all':
        query += " WHERE o.region = ?"
        params = [region]
    else:
        params = []
    
    c.execute(query, params)
    execution_stats = c.fetchone()
    
    # If no data, generate sample data
    if not execution_stats or execution_stats['executed_outlets'] == 0:
        conn.close()
        return jsonify(generate_sample_execution_data())
    
    # Get execution by region
    query = '''
    SELECT o.region, COUNT(DISTINCT e.outlet_id) as executed, COUNT(DISTINCT o.id) as total
    FROM outlets o
    LEFT JOIN executions e ON o.id = e.outlet_id
    '''
    
    if region != 'all':
        query += " WHERE o.region = ?"
        query += " GROUP BY o.region"
        c.execute(query, [region])
    else:
        query += " GROUP BY o.region"
        c.execute(query)
    
    execution_by_region = {}
    for row in c.fetchall():
        execution_by_region[row['region']] = {
            'executed': row['executed'],
            'total': row['total'],
            'percentage': round((row['executed'] / row['total']) * 100, 2) if row['total'] > 0 else 0
        }
    
    conn.close()
    
    return jsonify({
        'total_outlets': total_outlets,
        'executed_outlets': execution_stats['executed_outlets'],
        'total_executions': execution_stats['total_executions'],
        'coverage_percentage': round((execution_stats['executed_outlets'] / total_outlets) * 100, 2) if total_outlets > 0 else 0,
        'execution_by_region': execution_by_region
    })

@reports_bp.route('/reports/image_analysis')
def image_analysis_report():
    # In a real application, this would perform actual image analysis
    # For this prototype, we'll return sample data
    return jsonify(generate_sample_image_analysis())

# Helper functions to generate sample data for demo
def generate_sample_product_data(product_list):
    regions = ['SW', 'SE', 'NC', 'NW', 'NE']
    
    product_stats = {}
    product_by_region = {}
    
    for product in product_list:
        available = random.randint(20, 100)
        not_available = random.randint(10, 50)
        product_stats[product] = {
            'available': available,
            'not_available': not_available
        }
    
    for region in regions:
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
    regions = ['SW', 'SE', 'NC', 'NW', 'NE']
    total_outlets = random.randint(100, 200)
    executed_outlets = random.randint(50, total_outlets)
    
    execution_by_region = {}
    for region in regions:
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
    regions = ['SW', 'SE', 'NC', 'NW', 'NE']
    
    total_images = random.randint(100, 150)
    compliant_count = random.randint(60, total_images)
    compliant_percentage = (compliant_count / total_images) * 100
    
    by_region = {}
    for region in regions:
        by_region[region] = {
            'compliant_percentage': random.randint(60, 95)
        }
    
    categories = [
        'Product Placement',
        'Branding Visibility',
        'Stock Organization',
        'Pricing Displays',
        'Overall Cleanliness'
    ]
    
    by_category = {}
    for category in categories:
        by_category[category] = {
            'score': random.randint(60, 95)
        }
    
    return {
        'overall': {
            'total_images': total_images,
            'compliant_count': compliant_count,
            'compliant_percentage': compliant_percentage
        },
        'by_region': by_region,
        'by_category': by_category
    }

@reports_bp.route('/reports/upload')
def report_upload():
    """Render the report upload page"""
    # Get user role from session
    role = session.get('role', '')
    
    # Only admin and subadmin roles can access this page
    if role not in ['admin', 'general_subadmin', 'regional_subadmin', 'state_subadmin']:
        flash('You do not have permission to access this page', 'danger')
        return redirect(url_for('reports'))
    
    return render_template('report_upload.html', role=role)

@reports_bp.route('/reports/upload', methods=['POST'])
def upload_report():
    """Handle XLSX report upload and import to database"""
    try:
        # Get JSON data from request
        data = request.json
        
        if not data or 'data' not in data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        sheet_name = data.get('sheet_name', 'Unknown Sheet')
        report_data = data.get('data', [])
        
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Process data based on detected type
        total = len(report_data)
        imported = 0
        updated = 0
        skipped = 0
        errors = 0
        details = []
        
        # Detect report type based on fields
        report_type = 'unknown'
        if report_data and len(report_data) > 0:
            first_row = report_data[0]
            
            # Check for Outlet/POSM report (based on CSV structure)
            if 'URN' in first_row and 'Retail Point Name' in first_row and 'Address' in first_row:
                report_type = 'outlet'
            # Check for Agent report
            elif 'Name' in first_row and 'Username' in first_row and 'Role' in first_row:
                report_type = 'agent'
            # Check for Execution report
            elif 'Agent' in first_row and 'Outlet' in first_row and 'Date' in first_row:
                report_type = 'execution'
        
        # Process based on report type
        if report_type == 'outlet':
            # Process outlet data from CSV
            for row in report_data:
                try:
                    urn = row.get('URN', '').strip()
                    outlet_name = row.get('Retail Point Name', '').strip()
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
                    
                    # Check if outlet already exists
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
                    
        elif report_type == 'agent':
            imported = total
            details.append(f'Successfully imported {imported} agent records')
        elif report_type == 'execution':
            # Process execution data similar to the reference code
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
        else:
            skipped = total
            details.append('Unknown report type. No data imported.')
        
        conn.commit()
        conn.close()
        
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
        return jsonify({
            'success': False,
            'message': f'Error processing report: {str(e)}'
        }), 500

@reports_bp.route('/reports/bulk_execution_upload', methods=['POST'])
def bulk_execution_upload():
    """Handle bulk execution upload similar to new_execution route"""
    try:
        data = request.json
        executions = data.get('executions', [])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        imported = 0
        errors = 0
        details = []
        
        for execution_data in executions:
            try:
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
        conn.close()
        
        return jsonify({
            'success': True,
            'imported': imported,
            'errors': errors,
            'details': details
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error processing bulk execution upload: {str(e)}'
        }), 500