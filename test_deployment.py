#!/usr/bin/env python3
"""
Pre-deployment Test Script
Verifies that your application is ready for PythonAnywhere deployment
"""

import sys
import os
import importlib
from pathlib import Path

def test_imports():
    """Test all required imports"""
    print("🔍 Testing imports...")
    
    required_modules = [
        'flask',
        'sqlite3',
        'json',
        'datetime',
        'pathlib'
    ]
    
    optional_modules = {
        'flask_limiter': 'Flask-Limiter (rate limiting)',
        'flask_caching': 'Flask-Caching (caching)',
        'dotenv': 'python-dotenv (environment variables)',
        'PIL': 'Pillow (image processing)'
    }
    
    # Test required modules
    for module in required_modules:
        try:
            importlib.import_module(module)
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module} (REQUIRED)")
            return False
    
    # Test optional modules
    for module, description in optional_modules.items():
        try:
            importlib.import_module(module)
            print(f"  ✅ {module} ({description})")
        except ImportError:
            print(f"  ⚠️  {module} ({description}) - OPTIONAL")
    
    return True

def test_local_modules():
    """Test local module imports"""
    print("\n📦 Testing local modules...")
    
    try:
        from pykes.models import init_db, get_database_stats
        print("  ✅ pykes.models")
    except ImportError as e:
        print(f"  ❌ pykes.models - {str(e)}")
        return False
    
    try:
        from pykes.config import get_config
        print("  ✅ pykes.config")
    except ImportError:
        print("  ⚠️  pykes.config - using fallback")
    
    try:
        from pykes.routes import init_routes
        print("  ✅ pykes.routes")
    except ImportError:
        print("  ⚠️  pykes.routes - basic routing only")
    
    return True

def test_database_operations():
    """Test database operations"""
    print("\n🗄️  Testing database operations...")
    
    try:
        # Test basic database connection
        import sqlite3
        conn = sqlite3.connect('test_maindatabase.db')
        conn.execute('CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY)')
        conn.execute('INSERT INTO test (id) VALUES (1)')
        conn.commit()
        conn.close()
        
        # Clean up test database
        os.remove('test_maindatabase.db')
        print("  ✅ Database connection and operations")
        return True
        
    except Exception as e:
        print(f"  ❌ Database test failed: {str(e)}")
        return False

def test_flask_app():
    """Test Flask application creation"""
    print("\n🌐 Testing Flask app creation...")
    
    try:
        # Test deployment-ready app
        from flask_app_deploy import create_app
        app = create_app()
        print("  ✅ Deployment Flask app created")
        
        # Test basic routes
        with app.test_client() as client:
            response = client.get('/test')
            if response.status_code == 200:
                print("  ✅ Test endpoint working")
            else:
                print(f"  ⚠️  Test endpoint returned {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Flask app test failed: {str(e)}")
        return False

def test_database_schema():
    """Test current database schema"""
    print("\n📋 Testing database schema...")
    
    try:
        import sqlite3
        
        if not Path('maindatabase.db').exists():
            print("  ⚠️  Database doesn't exist, will be created fresh")
            return True
        
        conn = sqlite3.connect('maindatabase.db')
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['users', 'outlets', 'profile']
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            print(f"  ⚠️  Missing tables: {missing_tables}")
        else:
            print("  ✅ All required tables present")
        
        # Check for is_active columns
        if 'users' in tables:
            cursor.execute("PRAGMA table_info(users)")
            user_columns = [row[1] for row in cursor.fetchall()]
            if 'is_active' in user_columns:
                print("  ✅ Users table has is_active column")
            else:
                print("  ❌ Users table missing is_active column - RUN fix_database_schema.py")
                return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"  ❌ Database schema test failed: {str(e)}")
        return False

def run_all_tests():
    """Run all deployment readiness tests"""
    print("🚀 Pre-deployment Test Suite")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("Local Module Tests", test_local_modules),
        ("Database Operations", test_database_operations),
        ("Database Schema", test_database_schema),
        ("Flask Application", test_flask_app)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  💥 {test_name} crashed: {str(e)}")
            failed += 1
    
    print(f"\n📊 Test Results:")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Your application is ready for deployment.")
        print("\n📋 Next steps:")
        print("1. Upload files to PythonAnywhere")
        print("2. Install dependencies (see PYTHONANYWHERE_DEPLOYMENT.md)")
        print("3. Update WSGI configuration")
        print("4. Restart web app")
        return True
    else:
        print("\n⚠️  Some tests failed. Please fix the issues before deploying.")
        print("See PYTHONANYWHERE_DEPLOYMENT.md for detailed instructions.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
