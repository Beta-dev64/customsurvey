# Database Setup Instructions

This document explains how to set up the database for the SurveyTray application.

## Files Created

1. **`init_db_clean.py`** - Initializes the database with empty tables only
2. **`create_demo_users.py`** - Creates demo users for testing (1 admin + 1 field agent)
3. **Modified `pykes/models.py`** - Removed automatic sample data creation

## Setup Process

### Step 1: Initialize Clean Database
Run this command to create the database tables without any data:

```bash
python init_db_clean.py
```

This will:
- Create all required tables (users, outlets, executions, profile)
- Set up proper indexes and constraints
- Create the default company profile
- Leave all data tables empty

### Step 2: Create Demo Users
Run this command to add demo users:

```bash
python create_demo_users.py
```

This will create:

**Admin User:**
- Username: `admin`
- Password: `admin123`
- Role: `admin` 
- Access: All regions

**Field Agent User:**
- Username: `field_agent_demo`
- Password: `agent123`
- Role: `field_agent`
- Region: SW (Southwest)

## Database Tables Created

1. **users** - User accounts with authentication and role management
2. **outlets** - Retail outlet information
3. **executions** - Field execution records with images and GPS data
4. **profile** - Application branding and configuration

## Important Notes

⚠️ **Security Warning**: The demo passwords are simple and should be changed in production!

✅ **Clean Start**: The database initialization now creates empty tables, giving you full control over your data.

✅ **Separate Demo Data**: Demo users are created separately, so you can choose when and if to add them.

## Usage Examples

```bash
# Fresh database setup
python init_db_clean.py

# Add demo users for testing
python create_demo_users.py

# Check what's in the database
sqlite3 maindatabase.db "SELECT username, role, region FROM users;"
```

## Next Steps

After running these scripts, you can:
1. Import your actual outlet data
2. Create additional users as needed
3. Start using the application with clean, empty tables
4. Test with the demo users provided
