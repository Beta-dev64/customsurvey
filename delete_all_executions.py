#!/usr/bin/env python3
"""
Delete All Executions Script
Safely removes all execution records from the database with backup option
"""

import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
import shutil

# Database configuration
DB_PATH = 'maindatabase.db'

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseError(Exception):
    """Custom database exception"""
    pass

@contextmanager
def get_db_connection():
    """Context manager for database connections with proper error handling"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row

        # Enable foreign key constraints
        conn.execute('PRAGMA foreign_keys = ON')

        yield conn

    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {str(e)}")
        raise DatabaseError(f"Database operation failed: {str(e)}")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected error in database operation: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def create_backup():
    """Create a backup of the database before deletion"""
    try:
        if not Path(DB_PATH).exists():
            logger.warning("Database file doesn't exist, no backup needed")
            return None

        backup_name = f"backup_before_execution_delete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(DB_PATH, backup_name)
        logger.info(f"Backup created: {backup_name}")
        return backup_name
    except Exception as e:
        logger.error(f"Backup creation failed: {str(e)}")
        return None

def get_execution_count():
    """Get the current count of executions"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM executions")
            count = cursor.fetchone()[0]
            return count
    except Exception as e:
        logger.error(f"Error getting execution count: {str(e)}")
        return 0

def get_execution_summary():
    """Get a summary of executions by status"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM executions
                GROUP BY status
                ORDER BY count DESC
            """)
            results = cursor.fetchall()
            return dict(results) if results else {}
    except Exception as e:
        logger.error(f"Error getting execution summary: {str(e)}")
        return {}

def delete_all_executions():
    """Delete all execution records from the database"""
    try:
        logger.info("Starting execution deletion process...")

        # Check if database exists
        if not Path(DB_PATH).exists():
            logger.error("Database file doesn't exist")
            return False

        # Get current count
        initial_count = get_execution_count()
        if initial_count == 0:
            logger.info("No executions found to delete")
            return True

        # Get summary before deletion
        summary = get_execution_summary()
        logger.info(f"Found {initial_count} executions to delete:")
        for status, count in summary.items():
            logger.info(f"  - {status}: {count} records")

        # Perform deletion
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Delete all executions
            cursor.execute("DELETE FROM executions")
            deleted_count = cursor.rowcount

            # Reset the auto-increment counter
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='executions'")

            conn.commit()

            logger.info(f"Successfully deleted {deleted_count} execution records")

            # Verify deletion
            final_count = get_execution_count()
            if final_count == 0:
                logger.info("✅ All executions deleted successfully")
                return True
            else:
                logger.warning(f"⚠️  {final_count} executions still remain")
                return False

    except Exception as e:
        logger.error(f"Error deleting executions: {str(e)}")
        return False

def get_related_data_info():
    """Get information about data that might reference executions"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check for any tables that might reference executions
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name != 'executions'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            info = {}
            for table in tables:
                try:
                    # Check if table has any columns that might reference executions
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    execution_refs = [col[1] for col in columns if 'execution' in col[1].lower()]
                    if execution_refs:
                        info[table] = execution_refs
                except Exception:
                    pass

            return info
    except Exception as e:
        logger.error(f"Error getting related data info: {str(e)}")
        return {}

def main():
    """Main function to delete all executions with safety checks"""
    print("🗑️  Delete All Executions")
    print("=" * 40)

    try:
        # Check database exists
        if not Path(DB_PATH).exists():
            print("❌ Database file not found!")
            return False

        # Get current status
        initial_count = get_execution_count()
        summary = get_execution_summary()

        if initial_count == 0:
            print("ℹ️  No executions found in the database.")
            return True

        # Show current status
        print(f"📊 Current executions in database: {initial_count}")
        if summary:
            print("📋 Breakdown by status:")
            for status, count in summary.items():
                print(f"   - {status}: {count}")

        # Check for related data
        related_info = get_related_data_info()
        if related_info:
            print("⚠️  Tables with potential execution references:")
            for table, refs in related_info.items():
                print(f"   - {table}: {', '.join(refs)}")

        # Confirmation
        print(f"\n⚠️  WARNING: This will permanently delete ALL {initial_count} execution records!")
        print("This action cannot be undone.")

        response = input("\nDo you want to continue? (type 'DELETE' to confirm): ").strip()

        if response != 'DELETE':
            print("❌ Operation cancelled.")
            return False

        # Create backup
        print("\n💾 Creating backup...")
        backup_file = create_backup()
        if backup_file:
            print(f"✅ Backup created: {backup_file}")
        else:
            print("⚠️  Backup creation failed!")
            confirm_no_backup = input("Continue without backup? (y/N): ").strip().lower()
            if confirm_no_backup != 'y':
                print("❌ Operation cancelled.")
                return False

        # Perform deletion
        print("\n🗑️  Deleting executions...")
        success = delete_all_executions()

        if success:
            print("✅ All executions deleted successfully!")
            print(f"📁 Backup saved as: {backup_file}")
            return True
        else:
            print("❌ Deletion failed! Check the logs for details.")
            return False

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        print(f"❌ Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
=======
#!/usr/bin/env python3
"""
Delete All Executions Script
Safely removes all execution records from the database with backup option
"""

import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
import shutil

# Database configuration
DB_PATH = 'maindatabase.db'

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseError(Exception):
    """Custom database exception"""
    pass

@contextmanager
def get_db_connection():
    """Context manager for database connections with proper error handling"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row

        # Enable foreign key constraints
        conn.execute('PRAGMA foreign_keys = ON')

        yield conn

    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {str(e)}")
        raise DatabaseError(f"Database operation failed: {str(e)}")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected error in database operation: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def create_backup():
    """Create a backup of the database before deletion"""
    try:
        if not Path(DB_PATH).exists():
            logger.warning("Database file doesn't exist, no backup needed")
            return None

        backup_name = f"backup_before_execution_delete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(DB_PATH, backup_name)
        logger.info(f"Backup created: {backup_name}")
        return backup_name
    except Exception as e:
        logger.error(f"Backup creation failed: {str(e)}")
        return None

def get_execution_count():
    """Get the current count of executions"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM executions")
            count = cursor.fetchone()[0]
            return count
    except Exception as e:
        logger.error(f"Error getting execution count: {str(e)}")
        return 0

def get_execution_summary():
    """Get a summary of executions by status"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM executions
                GROUP BY status
                ORDER BY count DESC
            """)
            results = cursor.fetchall()
            return dict(results) if results else {}
    except Exception as e:
        logger.error(f"Error getting execution summary: {str(e)}")
        return {}

def delete_all_executions():
    """Delete all execution records from the database"""
    try:
        logger.info("Starting execution deletion process...")

        # Check if database exists
        if not Path(DB_PATH).exists():
            logger.error("Database file doesn't exist")
            return False

        # Get current count
        initial_count = get_execution_count()
        if initial_count == 0:
            logger.info("No executions found to delete")
            return True

        # Get summary before deletion
        summary = get_execution_summary()
        logger.info(f"Found {initial_count} executions to delete:")
        for status, count in summary.items():
            logger.info(f"  - {status}: {count} records")

        # Perform deletion
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Delete all executions
            cursor.execute("DELETE FROM executions")
            deleted_count = cursor.rowcount

            # Reset the auto-increment counter
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='executions'")

            conn.commit()

            logger.info(f"Successfully deleted {deleted_count} execution records")

            # Verify deletion
            final_count = get_execution_count()
            if final_count == 0:
                logger.info("✅ All executions deleted successfully")
                return True
            else:
                logger.warning(f"⚠️  {final_count} executions still remain")
                return False

    except Exception as e:
        logger.error(f"Error deleting executions: {str(e)}")
        return False

def get_related_data_info():
    """Get information about data that might reference executions"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check for any tables that might reference executions
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name != 'executions'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            info = {}
            for table in tables:
                try:
                    # Check if table has any columns that might reference executions
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    execution_refs = [col[1] for col in columns if 'execution' in col[1].lower()]
                    if execution_refs:
                        info[table] = execution_refs
                except Exception:
                    pass

            return info
    except Exception as e:
        logger.error(f"Error getting related data info: {str(e)}")
        return {}

def main():
    """Main function to delete all executions with safety checks"""
    print("🗑️  Delete All Executions")
    print("=" * 40)

    try:
        # Check database exists
        if not Path(DB_PATH).exists():
            print("❌ Database file not found!")
            return False

        # Get current status
        initial_count = get_execution_count()
        summary = get_execution_summary()

        if initial_count == 0:
            print("ℹ️  No executions found in the database.")
            return True

        # Show current status
        print(f"📊 Current executions in database: {initial_count}")
        if summary:
            print("📋 Breakdown by status:")
            for status, count in summary.items():
                print(f"   - {status}: {count}")

        # Check for related data
        related_info = get_related_data_info()
        if related_info:
            print("⚠️  Tables with potential execution references:")
            for table, refs in related_info.items():
                print(f"   - {table}: {', '.join(refs)}")

        # Confirmation
        print(f"\n⚠️  WARNING: This will permanently delete ALL {initial_count} execution records!")
        print("This action cannot be undone.")

        response = input("\nDo you want to continue? (type 'DELETE' to confirm): ").strip()

        if response != 'DELETE':
            print("❌ Operation cancelled.")
            return False

        # Create backup
        print("\n💾 Creating backup...")
        backup_file = create_backup()
        if backup_file:
            print(f"✅ Backup created: {backup_file}")
        else:
            print("⚠️  Backup creation failed!")
            confirm_no_backup = input("Continue without backup? (y/N): ").strip().lower()
            if confirm_no_backup != 'y':
                print("❌ Operation cancelled.")
                return False

        # Perform deletion
        print("\n🗑️  Deleting executions...")
        success = delete_all_executions()

        if success:
            print("✅ All executions deleted successfully!")
            print(f"📁 Backup saved as: {backup_file}")
            return True
        else:
            print("❌ Deletion failed! Check the logs for details.")
            return False

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        print(f"❌ Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
