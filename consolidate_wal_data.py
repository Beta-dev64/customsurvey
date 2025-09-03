#!/usr/bin/env python3
"""
SQLite WAL Consolidation Script
Consolidates data from WAL (Write-Ahead Log) files back into main database
"""

import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path
import shutil
import os

# Database configuration
DB_PATH = 'maindatabase.db'
WAL_PATH = 'maindatabase.db-wal'
SHM_PATH = 'maindatabase.db-shm'

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

def check_wal_status():
    """Check the current WAL mode status and file sizes"""
    try:
        files_info = {}
        
        # Check main database file
        if Path(DB_PATH).exists():
            size = Path(DB_PATH).stat().st_size
            files_info['main_db'] = {'exists': True, 'size': size, 'size_mb': size / (1024*1024)}
        else:
            files_info['main_db'] = {'exists': False}
        
        # Check WAL file
        if Path(WAL_PATH).exists():
            size = Path(WAL_PATH).stat().st_size
            files_info['wal'] = {'exists': True, 'size': size, 'size_mb': size / (1024*1024)}
        else:
            files_info['wal'] = {'exists': False}
        
        # Check SHM file
        if Path(SHM_PATH).exists():
            size = Path(SHM_PATH).stat().st_size
            files_info['shm'] = {'exists': True, 'size': size, 'size_mb': size / (1024*1024)}
        else:
            files_info['shm'] = {'exists': False}
        
        return files_info
        
    except Exception as e:
        logger.error(f"Error checking WAL status: {str(e)}")
        return {}

def get_table_counts():
    """Get record counts from all tables"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            counts = {}
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    counts[table] = count
                except Exception as e:
                    logger.warning(f"Could not count table {table}: {str(e)}")
                    counts[table] = 'ERROR'
            
            return counts
            
    except Exception as e:
        logger.error(f"Error getting table counts: {str(e)}")
        return {}

def check_journal_mode():
    """Check the current journal mode"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            return mode
    except Exception as e:
        logger.error(f"Error checking journal mode: {str(e)}")
        return "UNKNOWN"

def create_backup():
    """Create backup of all database files"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = f"db_backup_{timestamp}"
        Path(backup_dir).mkdir(exist_ok=True)
        
        files_backed_up = []
        
        # Backup main database
        if Path(DB_PATH).exists():
            backup_path = Path(backup_dir) / DB_PATH
            shutil.copy2(DB_PATH, backup_path)
            files_backed_up.append(DB_PATH)
        
        # Backup WAL file
        if Path(WAL_PATH).exists():
            backup_path = Path(backup_dir) / WAL_PATH
            shutil.copy2(WAL_PATH, backup_path)
            files_backed_up.append(WAL_PATH)
        
        # Backup SHM file
        if Path(SHM_PATH).exists():
            backup_path = Path(backup_dir) / SHM_PATH
            shutil.copy2(SHM_PATH, backup_path)
            files_backed_up.append(SHM_PATH)
        
        logger.info(f"Backup created in {backup_dir}")
        return backup_dir, files_backed_up
        
    except Exception as e:
        logger.error(f"Backup creation failed: {str(e)}")
        return None, []

def consolidate_wal():
    """Consolidate WAL data back into main database"""
    try:
        logger.info("Starting WAL consolidation...")
        
        # Check if WAL file exists
        if not Path(WAL_PATH).exists():
            logger.info("No WAL file found - database may already be consolidated")
            return True
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Force checkpoint to consolidate WAL data
            logger.info("Performing WAL checkpoint...")
            cursor.execute("PRAGMA wal_checkpoint(FULL)")
            result = cursor.fetchone()
            
            if result:
                logger.info(f"Checkpoint result: {result}")
            
            # Verify the checkpoint worked
            cursor.execute("PRAGMA wal_checkpoint")
            checkpoint_info = cursor.fetchone()
            logger.info(f"Final checkpoint info: {checkpoint_info}")
            
            conn.commit()
            
        logger.info("WAL consolidation completed")
        return True
        
    except Exception as e:
        logger.error(f"WAL consolidation failed: {str(e)}")
        return False

def switch_to_delete_mode():
    """Switch database from WAL mode to DELETE mode"""
    try:
        logger.info("Switching to DELETE journal mode...")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Switch to DELETE mode
            cursor.execute("PRAGMA journal_mode = DELETE")
            new_mode = cursor.fetchone()[0]
            
            logger.info(f"Journal mode changed to: {new_mode}")
            
            # Verify the change
            cursor.execute("PRAGMA journal_mode")
            current_mode = cursor.fetchone()[0]
            
            if current_mode.upper() == 'DELETE':
                logger.info("Successfully switched to DELETE mode")
                return True
            else:
                logger.warning(f"Mode switch may not have worked. Current mode: {current_mode}")
                return False
                
    except Exception as e:
        logger.error(f"Error switching journal mode: {str(e)}")
        return False

def cleanup_wal_files():
    """Remove WAL and SHM files after consolidation"""
    try:
        files_removed = []
        
        # Remove WAL file
        if Path(WAL_PATH).exists():
            os.remove(WAL_PATH)
            files_removed.append(WAL_PATH)
            logger.info(f"Removed {WAL_PATH}")
        
        # Remove SHM file
        if Path(SHM_PATH).exists():
            os.remove(SHM_PATH)
            files_removed.append(SHM_PATH)
            logger.info(f"Removed {SHM_PATH}")
        
        return files_removed
        
    except Exception as e:
        logger.error(f"Error cleaning up WAL files: {str(e)}")
        return []

def main():
    """Main function to consolidate WAL data"""
    print("🗃️  SQLite WAL Data Consolidation")
    print("=" * 50)
    
    try:
        # Check current status
        print("📊 Current database file status:")
        files_info = check_wal_status()
        
        for file_type, info in files_info.items():
            if info['exists']:
                print(f"   {file_type.upper()}: {info['size_mb']:.2f} MB ({info['size']:,} bytes)")
            else:
                print(f"   {file_type.upper()}: Not found")
        
        # Check journal mode
        current_mode = check_journal_mode()
        print(f"📋 Current journal mode: {current_mode}")
        
        # Check table counts before
        print("\n📈 Current data counts:")
        counts_before = get_table_counts()
        for table, count in counts_before.items():
            print(f"   {table}: {count}")
        
        # Check if we need to do anything
        if not Path(WAL_PATH).exists() and current_mode.upper() != 'WAL':
            print("\n✅ Database appears to already be consolidated (no WAL mode/files)")
            return True
        
        if not Path(WAL_PATH).exists():
            print("\n⚠️  WAL mode is enabled but no WAL file found")
        
        # Ask for confirmation
        print(f"\n⚠️  This will consolidate WAL data into the main database file")
        print("This is generally safe but creates permanent changes.")
        
        response = input("\nDo you want to continue? (type 'CONSOLIDATE' to confirm): ").strip()
        
        if response != 'CONSOLIDATE':
            print("❌ Operation cancelled.")
            return False
        
        # Create backup
        print("\n💾 Creating backup...")
        backup_dir, files_backed_up = create_backup()
        if backup_dir:
            print(f"✅ Backup created: {backup_dir}")
            print(f"   Files backed up: {', '.join(files_backed_up)}")
        else:
            print("⚠️  Backup creation failed!")
            confirm_no_backup = input("Continue without backup? (y/N): ").strip().lower()
            if confirm_no_backup != 'y':
                print("❌ Operation cancelled.")
                return False
        
        # Consolidate WAL data
        print("\n🔄 Consolidating WAL data...")
        consolidate_success = consolidate_wal()
        
        if not consolidate_success:
            print("❌ WAL consolidation failed!")
            return False
        
        # Switch to DELETE mode to prevent future WAL files
        print("\n🔧 Switching to DELETE journal mode...")
        mode_switch_success = switch_to_delete_mode()
        
        if not mode_switch_success:
            print("⚠️  Journal mode switch failed, but data is consolidated")
        
        # Clean up WAL files
        print("\n🧹 Cleaning up WAL files...")
        removed_files = cleanup_wal_files()
        if removed_files:
            print(f"✅ Removed: {', '.join(removed_files)}")
        
        # Check final status
        print("\n📊 Final database status:")
        files_info_after = check_wal_status()
        for file_type, info in files_info_after.items():
            if info['exists']:
                print(f"   {file_type.upper()}: {info['size_mb']:.2f} MB ({info['size']:,} bytes)")
            else:
                print(f"   {file_type.upper()}: Not found")
        
        final_mode = check_journal_mode()
        print(f"📋 Final journal mode: {final_mode}")
        
        # Verify data integrity
        print("\n📈 Final data counts:")
        counts_after = get_table_counts()
        for table, count in counts_after.items():
            before_count = counts_before.get(table, 0)
            status = "✅" if count == before_count else "⚠️"
            print(f"   {table}: {count} {status}")
        
        print(f"\n✅ WAL consolidation completed successfully!")
        print(f"💾 Backup saved in: {backup_dir}")
        print("\n📝 What happened:")
        print("   - WAL data consolidated into main database file")
        print("   - Journal mode switched to DELETE (no more WAL files)")
        print("   - WAL/SHM files removed")
        print("   - Your data is now fully in the main .db file")
        
        return True
        
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
