#!/usr/bin/env python3
"""
Remove Duplicate Outlets Script
Finds and removes duplicate outlets based on outlet_name, address, state, and local_govt
Keeps the oldest record (lowest ID) for each set of duplicates
"""

import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
import shutil
from collections import defaultdict

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

        backup_name = f"backup_before_duplicate_removal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(DB_PATH, backup_name)
        logger.info(f"Backup created: {backup_name}")
        return backup_name
    except Exception as e:
        logger.error(f"Backup creation failed: {str(e)}")
        return None

def normalize_text(text):
    """Normalize text for comparison (lowercase, strip whitespace)"""
    if text is None:
        return ""
    return str(text).lower().strip()

def find_duplicate_outlets():
    """Find duplicate outlets based on name, address, state, and LGA"""
    try:
        logger.info("Searching for duplicate outlets...")

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Get all outlets
            cursor.execute("""
                SELECT id, urn, outlet_name, address, state, local_govt, customer_name, created_at
                FROM outlets
                WHERE is_active = 1
                ORDER BY id
            """)

            outlets = cursor.fetchall()

            if not outlets:
                logger.info("No outlets found in database")
                return {}

            # Group outlets by normalized key (name, address, state, lga)
            groups = defaultdict(list)

            for outlet in outlets:
                # Create a key based on the fields we're checking for duplicates
                key = (
                    normalize_text(outlet['outlet_name']),
                    normalize_text(outlet['address']),
                    normalize_text(outlet['state']),
                    normalize_text(outlet['local_govt'])
                )
                groups[key].append(dict(outlet))

            # Find groups with duplicates (more than 1 outlet)
            duplicates = {}
            for key, outlet_list in groups.items():
                if len(outlet_list) > 1:
                    # Sort by ID to keep the oldest (lowest ID)
                    outlet_list.sort(key=lambda x: x['id'])
                    duplicates[key] = outlet_list

            logger.info(f"Found {len(duplicates)} sets of duplicate outlets")
            return duplicates

    except Exception as e:
        logger.error(f"Error finding duplicates: {str(e)}")
        return {}

def show_duplicate_details(duplicates):
    """Display detailed information about duplicates"""
    if not duplicates:
        print("ℹ️  No duplicate outlets found.")
        return

    print(f"\n📊 Found {len(duplicates)} sets of duplicate outlets:")
    print("=" * 80)

    total_duplicates = 0

    for i, (key, outlets) in enumerate(duplicates.items(), 1):
        outlet_name, address, state, lga = key
        duplicate_count = len(outlets) - 1  # -1 because we keep one
        total_duplicates += duplicate_count

        print(f"\n🔍 Duplicate Set #{i}:")
        print(f"   Name: {outlets[0]['outlet_name']}")
        print(f"   Address: {outlets[0]['address']}")
        print(f"   State: {outlets[0]['state']}")
        print(f"   LGA: {outlets[0]['local_govt']}")
        print(f"   Total Records: {len(outlets)} (will remove {duplicate_count})")

        print(f"   📋 Details:")
        for j, outlet in enumerate(outlets):
            keep_status = "KEEP" if j == 0 else "DELETE"
            print(f"      [{keep_status}] ID: {outlet['id']}, URN: {outlet['urn']}, Customer: {outlet['customer_name']}")

    print(f"\n📈 Summary:")
    print(f"   Duplicate sets found: {len(duplicates)}")
    print(f"   Total outlets to delete: {total_duplicates}")
    print(f"   Total outlets to keep: {len(duplicates)}")

def check_execution_references(outlet_ids):
    """Check if any of the outlets to be deleted have execution references"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check for executions referencing these outlets
            placeholders = ','.join(['?' for _ in outlet_ids])
            cursor.execute(f"""
                SELECT outlet_id, COUNT(*) as execution_count
                FROM executions
                WHERE outlet_id IN ({placeholders})
                GROUP BY outlet_id
            """, outlet_ids)

            references = dict(cursor.fetchall())
            return references

    except Exception as e:
        logger.error(f"Error checking execution references: {str(e)}")
        return {}

def remove_duplicate_outlets(duplicates, force=False):
    """Remove duplicate outlets, keeping the oldest (lowest ID) in each set"""
    try:
        if not duplicates:
            logger.info("No duplicates to remove")
            return True

        outlets_to_delete = []
        outlets_to_keep = []

        # Collect IDs of outlets to delete and keep
        for key, outlets in duplicates.items():
            # Sort by ID (oldest first)
            outlets.sort(key=lambda x: x['id'])
            outlets_to_keep.append(outlets[0]['id'])  # Keep the first (oldest)
            outlets_to_delete.extend([o['id'] for o in outlets[1:]])  # Delete the rest

        # Check for execution references if not forcing
        if not force:
            references = check_execution_references(outlets_to_delete)
            if references:
                logger.warning("Some outlets to be deleted have execution references:")
                for outlet_id, count in references.items():
                    logger.warning(f"  Outlet ID {outlet_id}: {count} executions")

                print("⚠️  Warning: Some outlets to be deleted have execution references!")
                print("This could cause referential integrity issues.")

                response = input("Continue anyway? (y/N): ").strip().lower()
                if response != 'y':
                    logger.info("Operation cancelled by user")
                    return False

        # Perform deletion
        with get_db_connection() as conn:
            cursor = conn.cursor()

            logger.info(f"Deleting {len(outlets_to_delete)} duplicate outlets...")

            deleted_count = 0
            for outlet_id in outlets_to_delete:
                cursor.execute("DELETE FROM outlets WHERE id = ?", (outlet_id,))
                if cursor.rowcount > 0:
                    deleted_count += 1

            conn.commit()

            logger.info(f"Successfully deleted {deleted_count} duplicate outlets")
            logger.info(f"Kept {len(outlets_to_keep)} unique outlets")

            return True

    except Exception as e:
        logger.error(f"Error removing duplicates: {str(e)}")
        return False

def get_outlet_count():
    """Get the current count of outlets"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM outlets WHERE is_active = 1")
            count = cursor.fetchone()[0]
            return count
    except Exception as e:
        logger.error(f"Error getting outlet count: {str(e)}")
        return 0

def main():
    """Main function to find and remove duplicate outlets"""
    print("🔍 Remove Duplicate Outlets")
    print("=" * 50)
    print("This script will find duplicates based on:")
    print("- Outlet Name")
    print("- Address")
    print("- State")
    print("- Local Government Area (LGA)")
    print()

    try:
        # Check database exists
        if not Path(DB_PATH).exists():
            print("❌ Database file not found!")
            return False

        # Get current outlet count
        initial_count = get_outlet_count()
        print(f"📊 Total outlets in database: {initial_count}")

        if initial_count == 0:
            print("ℹ️  No outlets found in the database.")
            return True

        # Find duplicates
        print("\n🔍 Searching for duplicates...")
        duplicates = find_duplicate_outlets()

        if not duplicates:
            print("✅ No duplicate outlets found!")
            return True

        # Show duplicate details
        show_duplicate_details(duplicates)

        # Get confirmation
        total_to_delete = sum(len(outlets) - 1 for outlets in duplicates.values())

        print(f"\n⚠️  WARNING: This will delete {total_to_delete} duplicate outlet records!")
        print("The oldest record (lowest ID) will be kept for each duplicate set.")

        response = input("\nDo you want to continue? (type 'REMOVE' to confirm): ").strip()

        if response != 'REMOVE':
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

        # Perform removal
        print(f"\n🗑️  Removing {total_to_delete} duplicate outlets...")
        success = remove_duplicate_outlets(duplicates)

        if success:
            final_count = get_outlet_count()
            removed_count = initial_count - final_count
            print(f"✅ Successfully removed {removed_count} duplicate outlets!")
            print(f"📊 Outlets remaining: {final_count}")
            print(f"💾 Backup saved as: {backup_file}")
            return True
        else:
            print("❌ Duplicate removal failed! Check the logs for details.")
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
Remove Duplicate Outlets Script
Finds and removes duplicate outlets based on outlet_name, address, state, and local_govt
Keeps the oldest record (lowest ID) for each set of duplicates
"""

import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
import shutil
from collections import defaultdict

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

        backup_name = f"backup_before_duplicate_removal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(DB_PATH, backup_name)
        logger.info(f"Backup created: {backup_name}")
        return backup_name
    except Exception as e:
        logger.error(f"Backup creation failed: {str(e)}")
        return None

def normalize_text(text):
    """Normalize text for comparison (lowercase, strip whitespace)"""
    if text is None:
        return ""
    return str(text).lower().strip()

def find_duplicate_outlets():
    """Find duplicate outlets based on name, address, state, and LGA"""
    try:
        logger.info("Searching for duplicate outlets...")

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Get all outlets
            cursor.execute("""
                SELECT id, urn, outlet_name, address, state, local_govt, customer_name, created_at
                FROM outlets
                WHERE is_active = 1
                ORDER BY id
            """)

            outlets = cursor.fetchall()

            if not outlets:
                logger.info("No outlets found in database")
                return {}

            # Group outlets by normalized key (name, address, state, lga)
            groups = defaultdict(list)

            for outlet in outlets:
                # Create a key based on the fields we're checking for duplicates
                key = (
                    normalize_text(outlet['outlet_name']),
                    normalize_text(outlet['address']),
                    normalize_text(outlet['state']),
                    normalize_text(outlet['local_govt'])
                )
                groups[key].append(dict(outlet))

            # Find groups with duplicates (more than 1 outlet)
            duplicates = {}
            for key, outlet_list in groups.items():
                if len(outlet_list) > 1:
                    # Sort by ID to keep the oldest (lowest ID)
                    outlet_list.sort(key=lambda x: x['id'])
                    duplicates[key] = outlet_list

            logger.info(f"Found {len(duplicates)} sets of duplicate outlets")
            return duplicates

    except Exception as e:
        logger.error(f"Error finding duplicates: {str(e)}")
        return {}

def show_duplicate_details(duplicates):
    """Display detailed information about duplicates"""
    if not duplicates:
        print("ℹ️  No duplicate outlets found.")
        return

    print(f"\n📊 Found {len(duplicates)} sets of duplicate outlets:")
    print("=" * 80)

    total_duplicates = 0

    for i, (key, outlets) in enumerate(duplicates.items(), 1):
        outlet_name, address, state, lga = key
        duplicate_count = len(outlets) - 1  # -1 because we keep one
        total_duplicates += duplicate_count

        print(f"\n🔍 Duplicate Set #{i}:")
        print(f"   Name: {outlets[0]['outlet_name']}")
        print(f"   Address: {outlets[0]['address']}")
        print(f"   State: {outlets[0]['state']}")
        print(f"   LGA: {outlets[0]['local_govt']}")
        print(f"   Total Records: {len(outlets)} (will remove {duplicate_count})")

        print(f"   📋 Details:")
        for j, outlet in enumerate(outlets):
            keep_status = "KEEP" if j == 0 else "DELETE"
            print(f"      [{keep_status}] ID: {outlet['id']}, URN: {outlet['urn']}, Customer: {outlet['customer_name']}")

    print(f"\n📈 Summary:")
    print(f"   Duplicate sets found: {len(duplicates)}")
    print(f"   Total outlets to delete: {total_duplicates}")
    print(f"   Total outlets to keep: {len(duplicates)}")

def check_execution_references(outlet_ids):
    """Check if any of the outlets to be deleted have execution references"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Check for executions referencing these outlets
            placeholders = ','.join(['?' for _ in outlet_ids])
            cursor.execute(f"""
                SELECT outlet_id, COUNT(*) as execution_count
                FROM executions
                WHERE outlet_id IN ({placeholders})
                GROUP BY outlet_id
            """, outlet_ids)

            references = dict(cursor.fetchall())
            return references

    except Exception as e:
        logger.error(f"Error checking execution references: {str(e)}")
        return {}

def remove_duplicate_outlets(duplicates, force=False):
    """Remove duplicate outlets, keeping the oldest (lowest ID) in each set"""
    try:
        if not duplicates:
            logger.info("No duplicates to remove")
            return True

        outlets_to_delete = []
        outlets_to_keep = []

        # Collect IDs of outlets to delete and keep
        for key, outlets in duplicates.items():
            # Sort by ID (oldest first)
            outlets.sort(key=lambda x: x['id'])
            outlets_to_keep.append(outlets[0]['id'])  # Keep the first (oldest)
            outlets_to_delete.extend([o['id'] for o in outlets[1:]])  # Delete the rest

        # Check for execution references if not forcing
        if not force:
            references = check_execution_references(outlets_to_delete)
            if references:
                logger.warning("Some outlets to be deleted have execution references:")
                for outlet_id, count in references.items():
                    logger.warning(f"  Outlet ID {outlet_id}: {count} executions")

                print("⚠️  Warning: Some outlets to be deleted have execution references!")
                print("This could cause referential integrity issues.")

                response = input("Continue anyway? (y/N): ").strip().lower()
                if response != 'y':
                    logger.info("Operation cancelled by user")
                    return False

        # Perform deletion
        with get_db_connection() as conn:
            cursor = conn.cursor()

            logger.info(f"Deleting {len(outlets_to_delete)} duplicate outlets...")

            deleted_count = 0
            for outlet_id in outlets_to_delete:
                cursor.execute("DELETE FROM outlets WHERE id = ?", (outlet_id,))
                if cursor.rowcount > 0:
                    deleted_count += 1

            conn.commit()

            logger.info(f"Successfully deleted {deleted_count} duplicate outlets")
            logger.info(f"Kept {len(outlets_to_keep)} unique outlets")

            return True

    except Exception as e:
        logger.error(f"Error removing duplicates: {str(e)}")
        return False

def get_outlet_count():
    """Get the current count of outlets"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM outlets WHERE is_active = 1")
            count = cursor.fetchone()[0]
            return count
    except Exception as e:
        logger.error(f"Error getting outlet count: {str(e)}")
        return 0

def main():
    """Main function to find and remove duplicate outlets"""
    print("🔍 Remove Duplicate Outlets")
    print("=" * 50)
    print("This script will find duplicates based on:")
    print("- Outlet Name")
    print("- Address")
    print("- State")
    print("- Local Government Area (LGA)")
    print()

    try:
        # Check database exists
        if not Path(DB_PATH).exists():
            print("❌ Database file not found!")
            return False

        # Get current outlet count
        initial_count = get_outlet_count()
        print(f"📊 Total outlets in database: {initial_count}")

        if initial_count == 0:
            print("ℹ️  No outlets found in the database.")
            return True

        # Find duplicates
        print("\n🔍 Searching for duplicates...")
        duplicates = find_duplicate_outlets()

        if not duplicates:
            print("✅ No duplicate outlets found!")
            return True

        # Show duplicate details
        show_duplicate_details(duplicates)

        # Get confirmation
        total_to_delete = sum(len(outlets) - 1 for outlets in duplicates.values())

        print(f"\n⚠️  WARNING: This will delete {total_to_delete} duplicate outlet records!")
        print("The oldest record (lowest ID) will be kept for each duplicate set.")

        response = input("\nDo you want to continue? (type 'REMOVE' to confirm): ").strip()

        if response != 'REMOVE':
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

        # Perform removal
        print(f"\n🗑️  Removing {total_to_delete} duplicate outlets...")
        success = remove_duplicate_outlets(duplicates)

        if success:
            final_count = get_outlet_count()
            removed_count = initial_count - final_count
            print(f"✅ Successfully removed {removed_count} duplicate outlets!")
            print(f"📊 Outlets remaining: {final_count}")
            print(f"💾 Backup saved as: {backup_file}")
            return True
        else:
            print("❌ Duplicate removal failed! Check the logs for details.")
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
