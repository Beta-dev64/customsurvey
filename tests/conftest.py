# tests/conftest.py
# Pytest configuration and shared fixtures

import os
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

# Set test environment before importing app
os.environ['FLASK_ENV'] = 'testing'

from app import create_app
from pykes.models import init_db, get_db_connection
from pykes.config import TestingConfig

@pytest.fixture(scope='session')
def app():
    """Create application for testing"""
    
    # Create temporary directory for test database and uploads
    test_dir = tempfile.mkdtemp(prefix='surveytray_test_')
    
    # Override configuration for testing
    TestingConfig.DB_PATH = os.path.join(test_dir, 'test.db')
    TestingConfig.UPLOAD_FOLDER = os.path.join(test_dir, 'uploads')
    
    # Create the app with testing config
    app = create_app('testing')
    
    # Setup application context
    with app.app_context():
        init_db()
        yield app
    
    # Cleanup
    shutil.rmtree(test_dir, ignore_errors=True)

@pytest.fixture(scope='function')
def client(app):
    """Create test client"""
    return app.test_client()

@pytest.fixture(scope='function')
def runner(app):
    """Create test CLI runner"""
    return app.test_cli_runner()

@pytest.fixture(scope='function')
def db(app):
    """Create clean database for each test"""
    with app.app_context():
        # Clear all tables
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM executions')
            cursor.execute('DELETE FROM outlets')
            cursor.execute('DELETE FROM users WHERE username != "admin"')
            conn.commit()
        
        yield

@pytest.fixture
def auth_headers(client):
    """Create authentication headers for testing"""
    # Login as admin user
    response = client.post('/login', data={
        'username': 'admin',
        'password': 'admin123'
    })
    
    # Extract session cookie
    return {'Cookie': response.headers.get('Set-Cookie', '')}

@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        'username': 'testuser',
        'password': 'testpass123',
        'full_name': 'Test User',
        'role': 'field_agent',
        'region': 'SW',
        'state': 'Lagos',
        'lga': 'Ikeja'
    }

@pytest.fixture
def sample_outlet_data():
    """Sample outlet data for testing"""
    return {
        'urn': 'TEST/2024/SW/LA/000001',
        'outlet_name': 'Test Outlet',
        'customer_name': 'Test Customer',
        'address': '123 Test Street, Lagos',
        'phone': '08012345678',
        'outlet_type': 'Shop',
        'local_govt': 'Ikeja',
        'state': 'Lagos',
        'region': 'SW'
    }

@pytest.fixture
def sample_execution_data():
    """Sample execution data for testing"""
    return {
        'outlet_id': 1,
        'agent_id': 1,
        'latitude': 6.5244,
        'longitude': 3.3792,
        'notes': 'Test execution notes',
        'products_available': {
            'Table': True,
            'Chair': False,
            'Parasol': True
        },
        'status': 'Completed'
    }

@pytest.fixture
def upload_folder(app):
    """Create temporary upload folder"""
    upload_dir = Path(app.config['UPLOAD_FOLDER'])
    upload_dir.mkdir(parents=True, exist_ok=True)
    yield upload_dir
    # Cleanup handled by app fixture

@pytest.fixture
def sample_image_file():
    """Create a sample image file for testing uploads"""
    from PIL import Image
    import io
    
    # Create a small test image
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    
    return img_bytes

@pytest.fixture
def mock_file_upload(sample_image_file):
    """Mock file upload for testing"""
    from werkzeug.datastructures import FileStorage
    
    return FileStorage(
        stream=sample_image_file,
        filename='test_image.jpg',
        content_type='image/jpeg'
    )

# Database fixtures
@pytest.fixture
def create_test_user(app, sample_user_data):
    """Create a test user in database"""
    from pykes.models import UserModel
    
    with app.app_context():
        success, user_id = UserModel.create_user(sample_user_data)
        if success:
            yield user_id
        else:
            pytest.fail(f"Failed to create test user: {user_id}")

@pytest.fixture
def create_test_outlet(app, sample_outlet_data):
    """Create a test outlet in database"""
    from pykes.models import OutletModel
    
    with app.app_context():
        success, outlet_id = OutletModel.create_outlet(sample_outlet_data)
        if success:
            yield outlet_id
        else:
            pytest.fail(f"Failed to create test outlet: {outlet_id}")

# Mock fixtures
@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent testing"""
    from datetime import datetime
    
    fixed_datetime = datetime(2024, 1, 15, 10, 30, 0)
    
    with patch('pykes.models.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_datetime
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        yield mock_dt

@pytest.fixture
def mock_uuid():
    """Mock UUID for consistent testing"""
    with patch('uuid.uuid4') as mock_uuid4:
        mock_uuid4.return_value.hex = 'test-uuid-12345'
        yield mock_uuid4

# Error simulation fixtures
@pytest.fixture
def mock_database_error():
    """Mock database error for testing error handling"""
    with patch('pykes.models.get_db_connection') as mock_conn:
        mock_conn.side_effect = Exception("Database connection failed")
        yield mock_conn

# Logging fixtures
@pytest.fixture
def mock_logger():
    """Mock logger for testing log calls"""
    with patch('pykes.models.logger') as mock_log:
        yield mock_log

# Custom assertion helpers
def assert_valid_response(response, expected_status=200):
    """Assert response is valid with expected status"""
    assert response.status_code == expected_status
    if response.is_json:
        assert response.json is not None

def assert_redirect(response, expected_location=None):
    """Assert response is a redirect"""
    assert 300 <= response.status_code < 400
    if expected_location:
        assert expected_location in response.location

def assert_flash_message(response, message_text, category='message'):
    """Assert flash message was set"""
    # This would need to be implemented based on how flash messages are tested
    pass

# Database helpers
def get_db_record_count(table_name):
    """Get count of records in table"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        return cursor.fetchone()[0]

def clear_db_table(table_name):
    """Clear all records from table"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM {table_name}')
        conn.commit()
