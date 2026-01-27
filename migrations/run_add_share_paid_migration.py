"""Standalone script to add share_paid column to users table
Run this script to apply the migration safely in production.

Usage: python migrations/run_add_share_paid_migration.py
"""
import sys
import os

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db

def run_migration():
    """Run the migration to add share_paid column to users table"""
    app = create_app()
    
    with app.app_context():
        try:
            print("=" * 60)
            print("Running migration: Add share_paid column to users table")
            print("=" * 60)
            print("\nThis will:")
            print("  1. Add share_paid column to users table (boolean, default False)")
            print("  2. Set all existing users to share_paid=False")
            print()
            
            # Step 1: Add the share_paid column with default False
            print("[1/2] Adding share_paid column to users table...")
            db.session.execute(
                db.text("""
                    ALTER TABLE users 
                    ADD COLUMN IF NOT EXISTS share_paid BOOLEAN 
                    NOT NULL DEFAULT FALSE;
                """)
            )
            db.session.commit()
            print("✓ share_paid column added")
            
            # Step 2: Update all existing records to share_paid=False
            print("\n[2/2] Updating existing records to share_paid=False...")
            result = db.session.execute(
                db.text("UPDATE users SET share_paid = FALSE")
            )
            db.session.commit()
            print(f"✓ Updated {result.rowcount} records")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("✓ All existing users have been set to share_paid=False")
            print("✓ New users will default to share_paid=False")
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
