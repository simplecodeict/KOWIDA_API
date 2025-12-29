"""Standalone script to add who_see column to notifications table
Run this script to apply the migration safely in production.

Usage: python migrations/run_add_who_see_migration.py
"""
import sys
import os

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db

def run_migration():
    """Run the migration to add who_see column to notifications table"""
    app = create_app()
    
    with app.app_context():
        try:
            print("=" * 60)
            print("Running migration: Add who_see column to notifications table")
            print("=" * 60)
            print("\nThis will:")
            print("  1. Add who_see column to notifications table")
            print("  2. Set all existing notifications to who_see='all'")
            print()
            
            # Step 1: Add the who_see column with default 'all'
            print("[1/2] Adding who_see column to notifications table...")
            db.session.execute(
                db.text("""
                    ALTER TABLE notifications 
                    ADD COLUMN IF NOT EXISTS who_see VARCHAR(255) 
                    DEFAULT 'all' NOT NULL;
                """)
            )
            db.session.commit()
            print("✓ who_see column added")
            
            # Step 2: Ensure all existing records have 'all' as who_see
            print("\n[2/2] Updating existing records to who_see='all'...")
            result = db.session.execute(
                db.text("UPDATE notifications SET who_see = 'all' WHERE who_see IS NULL")
            )
            db.session.commit()
            print(f"✓ Updated {result.rowcount} records")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("✓ All existing notifications have been set to who_see='all'")
            print("=" * 60)
            return 0
            
        except Exception as e:
            db.session.rollback()
            print("\n" + "=" * 60)
            print("✗ Migration failed!")
            print(f"Error: {str(e)}")
            print("=" * 60)
            import traceback
            traceback.print_exc()
            return 1

if __name__ == '__main__':
    exit_code = run_migration()
    sys.exit(exit_code)











