# tests/test_models.py
# Unit tests for models module

import pytest
from pykes.models import (
    UserModel, OutletModel, ExecutionModel,
    get_profile, update_profile,
    DatabaseError, ValidationError
)
from tests.conftest import get_db_record_count

@pytest.mark.unit
@pytest.mark.database
class TestUserModel:
    """Test UserModel functionality"""
    
    def test_create_user_success(self, app, sample_user_data):
        """Test successful user creation"""
        with app.app_context():
            success, user_id = UserModel.create_user(sample_user_data)
            
            assert success is True
            assert isinstance(user_id, int)
            assert get_db_record_count('users') == 4  # 3 initial + 1 new

    def test_create_user_validation_error(self, app):
        """Test user creation with missing required fields"""
        with app.app_context():
            invalid_data = {'username': 'test'}  # Missing required fields
            
            success, error_msg = UserModel.create_user(invalid_data)
            
            assert success is False
            assert 'Missing required fields' in error_msg

    def test_create_user_duplicate_username(self, app, sample_user_data):
        """Test user creation with duplicate username"""
        with app.app_context():
            # Create first user
            UserModel.create_user(sample_user_data)
            
            # Try to create user with same username
            success, error_msg = UserModel.create_user(sample_user_data)
            
            assert success is False
            assert 'Username already exists' in error_msg

    def test_create_user_invalid_role(self, app, sample_user_data):
        """Test user creation with invalid role"""
        with app.app_context():
            sample_user_data['role'] = 'invalid_role'
            
            success, error_msg = UserModel.create_user(sample_user_data)
            
            assert success is False
            assert 'Invalid role' in error_msg

    def test_authenticate_user_success(self, app, sample_user_data):
        """Test successful user authentication"""
        with app.app_context():
            # Create user first
            UserModel.create_user(sample_user_data)
            
            # Authenticate
            success, user_data = UserModel.authenticate_user(
                sample_user_data['username'], 
                sample_user_data['password']
            )
            
            assert success is True
            assert user_data is not None
            assert user_data['username'] == sample_user_data['username']

    def test_authenticate_user_invalid_credentials(self, app, sample_user_data):
        """Test authentication with invalid credentials"""
        with app.app_context():
            UserModel.create_user(sample_user_data)
            
            success, user_data = UserModel.authenticate_user(
                sample_user_data['username'], 
                'wrong_password'
            )
            
            assert success is False
            assert user_data is None

    def test_authenticate_nonexistent_user(self, app):
        """Test authentication of non-existent user"""
        with app.app_context():
            success, user_data = UserModel.authenticate_user(
                'nonexistent', 
                'password'
            )
            
            assert success is False
            assert user_data is None

@pytest.mark.unit
@pytest.mark.database
class TestOutletModel:
    """Test OutletModel functionality"""
    
    def test_create_outlet_success(self, app, sample_outlet_data):
        """Test successful outlet creation"""
        with app.app_context():
            success, outlet_id = OutletModel.create_outlet(sample_outlet_data)
            
            assert success is True
            assert isinstance(outlet_id, int)

    def test_create_outlet_validation_error(self, app):
        """Test outlet creation with missing required fields"""
        with app.app_context():
            invalid_data = {'outlet_name': 'Test'}  # Missing URN and region
            
            success, error_msg = OutletModel.create_outlet(invalid_data)
            
            assert success is False
            assert 'Missing required fields' in error_msg

    def test_create_outlet_duplicate_urn(self, app, sample_outlet_data):
        """Test outlet creation with duplicate URN"""
        with app.app_context():
            # Create first outlet
            OutletModel.create_outlet(sample_outlet_data)
            
            # Try to create outlet with same URN
            success, error_msg = OutletModel.create_outlet(sample_outlet_data)
            
            assert success is False
            assert 'URN already exists' in error_msg

@pytest.mark.unit
@pytest.mark.database
class TestExecutionModel:
    """Test ExecutionModel functionality"""
    
    def test_create_execution_success(self, app, sample_execution_data, create_test_user, create_test_outlet):
        """Test successful execution creation"""
        with app.app_context():
            user_id = create_test_user
            outlet_id = create_test_outlet
            
            sample_execution_data['agent_id'] = user_id
            sample_execution_data['outlet_id'] = outlet_id
            
            success, execution_id = ExecutionModel.create_execution(sample_execution_data)
            
            assert success is True
            assert isinstance(execution_id, int)

    def test_create_execution_validation_error(self, app):
        """Test execution creation with missing required fields"""
        with app.app_context():
            invalid_data = {'notes': 'Test'}  # Missing outlet_id and agent_id
            
            success, error_msg = ExecutionModel.create_execution(invalid_data)
            
            assert success is False
            assert 'Missing required fields' in error_msg

    def test_create_execution_invalid_coordinates(self, app, sample_execution_data, create_test_user, create_test_outlet):
        """Test execution creation with invalid coordinates"""
        with app.app_context():
            user_id = create_test_user
            outlet_id = create_test_outlet
            
            sample_execution_data['agent_id'] = user_id
            sample_execution_data['outlet_id'] = outlet_id
            sample_execution_data['latitude'] = 200  # Invalid latitude
            
            success, error_msg = ExecutionModel.create_execution(sample_execution_data)
            
            assert success is False
            assert 'Latitude must be between' in error_msg

@pytest.mark.unit
class TestProfileManagement:
    """Test profile management functions"""
    
    def test_get_profile_success(self, app):
        """Test getting profile data"""
        with app.app_context():
            profile = get_profile()
            
            assert profile is not None
            assert 'company_name' in profile
            assert profile['company_name'] == 'DANGOTE'

    def test_update_profile_success(self, app):
        """Test successful profile update"""
        with app.app_context():
            new_data = {
                'company_name': 'Test Company',
                'app_title': 'Test App'
            }
            
            success = update_profile(new_data)
            assert success is True
            
            # Verify update
            profile = get_profile()
            assert profile['company_name'] == 'Test Company'
            assert profile['app_title'] == 'Test App'

    def test_update_profile_validation_error(self, app):
        """Test profile update with missing required fields"""
        with app.app_context():
            invalid_data = {}  # Missing required fields
            
            success = update_profile(invalid_data)
            assert success is False

@pytest.mark.unit
class TestDatabaseErrorHandling:
    """Test database error handling"""
    
    def test_database_connection_error(self, app, mock_database_error):
        """Test handling of database connection errors"""
        with app.app_context():
            with pytest.raises(DatabaseError):
                UserModel.create_user({'username': 'test'})

@pytest.mark.unit  
class TestDataValidation:
    """Test data validation and sanitization"""
    
    def test_data_sanitization(self, app):
        """Test data sanitization removes whitespace"""
        with app.app_context():
            data = {
                'username': '  testuser  ',
                'full_name': '  Test User  ',
                'role': 'field_agent'
            }
            
            sanitized = UserModel.sanitize_data(data)
            
            assert sanitized['username'] == 'testuser'
            assert sanitized['full_name'] == 'Test User'

    def test_required_fields_validation(self, app):
        """Test required fields validation"""
        with app.app_context():
            data = {'username': 'test'}
            required = ['username', 'password', 'full_name']
            
            is_valid, message = UserModel.validate_required_fields(data, required)
            
            assert is_valid is False
            assert 'password' in message
            assert 'full_name' in message
