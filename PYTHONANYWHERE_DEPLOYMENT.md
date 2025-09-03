# PythonAnywhere Deployment Fix Guide

This guide will fix the errors you're encountering with your SurveyTray deployment on PythonAnywhere.

## 🔍 Issues Identified

From your logs, I identified two main problems:

1. **Missing Dependencies**: `flask_limiter` and other packages are not installed
2. **Database Schema Issues**: Missing `is_active` columns causing database initialization to fail
3. **Duplicate Users**: UNIQUE constraint violations due to duplicate usernames

## 🛠️ Solution Steps

### Step 1: Fix Local Database (Run Before Upload)

1. **Run the database migration script** to fix schema issues:
   ```bash
   python fix_database_schema.py
   ```

2. **Test locally** to ensure everything works:
   ```bash
   python flask_app_deploy.py
   ```
   Visit `http://localhost:5000/health` to check status.

### Step 2: Upload Fixed Files to PythonAnywhere

Upload these new/updated files to your PythonAnywhere account:

- `fix_database_schema.py`
- `flask_app_deploy.py` 
- `requirements.txt` (updated)
- `pykes/models.py` (updated - no sample data)
- `create_demo_users.py`
- `init_db_clean.py`

### Step 3: Install Missing Dependencies on PythonAnywhere

1. **Open a Bash console** on PythonAnywhere
2. **Navigate to your project directory**:
   ```bash
   cd /home/betadev/customdesign/customsurvey
   ```

3. **Install missing packages**:
   ```bash
   pip3.10 install --user Flask-Limiter==3.5.0
   pip3.10 install --user Flask-Caching==2.1.0
   pip3.10 install --user python-dotenv==1.0.0
   pip3.10 install --user Pillow==10.2.0
   ```

4. **Or install all requirements** (if you uploaded the updated requirements.txt):
   ```bash
   pip3.10 install --user -r requirements.txt
   ```

### Step 4: Fix Database Schema on PythonAnywhere

1. **In your PythonAnywhere bash console**, run the migration:
   ```bash
   cd /home/betadev/customdesign/customsurvey
   python3.10 fix_database_schema.py
   ```

2. **Check the database status**:
   ```bash
   sqlite3 maindatabase.db "SELECT name FROM sqlite_master WHERE type='table';"
   ```

### Step 5: Update Your WSGI Configuration

1. **Go to your Web tab** on PythonAnywhere
2. **Edit your WSGI configuration file** (`/var/www/grandpro_innovateprotech_online_wsgi.py`)
3. **Update it to use the new deployment-ready app**:

```python
# This file contains the WSGI configuration required to serve up your
# web application at http://grandpro.innovateprotech.online
# It has been auto-generated for you.

import os
import sys

# Add your project directory to the sys.path
path = '/home/betadev/customdesign/customsurvey'
if path not in sys.path:
    sys.path.insert(0, path)

# Change working directory to your project
os.chdir(path)

try:
    from flask_app_deploy import application
except ImportError:
    # Fallback to original app if deploy version fails
    try:
        from flask_app import app as application
    except ImportError:
        # Last resort: create minimal app
        from flask import Flask
        application = Flask(__name__)
        
        @application.route('/')
        def error():
            return "Application failed to load. Check error logs.", 500
```

### Step 6: Create Demo Users

1. **After fixing the schema**, create demo users:
   ```bash
   python3.10 create_demo_users.py
   ```

### Step 7: Restart Your Web App

1. Go to your **Web tab** on PythonAnywhere
2. Click **"Reload"** to restart your web application

## ✅ Verification Steps

1. **Check the health endpoint**: Visit `https://grandpro.innovateprotech.online/health`
2. **Check the main page**: Visit `https://grandpro.innovateprotech.online/`
3. **Test login** with demo users:
   - Admin: `admin` / `admin123`
   - Field Agent: `field_agent_demo` / `agent123`

## 🚨 Alternative: Clean Fresh Start

If the migration doesn't work, you can start fresh:

1. **Backup your current database**:
   ```bash
   cp maindatabase.db maindatabase_backup_$(date +%Y%m%d).db
   ```

2. **Remove old database**:
   ```bash
   rm maindatabase.db
   ```

3. **Create fresh database**:
   ```bash
   python3.10 init_db_clean.py
   python3.10 create_demo_users.py
   ```

## 📋 Key Files Summary

- **`flask_app_deploy.py`**: Robust Flask app with graceful error handling
- **`fix_database_schema.py`**: Fixes existing database schema issues
- **`requirements.txt`**: Updated dependencies list
- **`init_db_clean.py`**: Clean database initialization (tables only)
- **`create_demo_users.py`**: Creates demo users for testing

## 🐛 Debugging Tips

1. **Check error logs**: Monitor `/var/log/` files on PythonAnywhere
2. **Test endpoints**:
   - `/health` - Application health status
   - `/test` - Simple functionality test
   - `/database-error` - Database error details (if any)

3. **Check Python path**: Ensure your project directory is in Python path
4. **Verify file permissions**: Make sure uploaded files are readable

## 📞 If You Still Have Issues

1. Check that all files uploaded correctly
2. Verify Python version compatibility (should use Python 3.10)
3. Ensure database file permissions are correct
4. Check that the working directory is set correctly in WSGI

## 🔐 Security Notes

- Change default passwords after deployment
- Set proper SECRET_KEY environment variable
- Review file upload permissions
- Enable HTTPS in production

Your deployment should work after following these steps!
