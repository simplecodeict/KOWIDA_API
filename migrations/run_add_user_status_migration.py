"""Standalone script to add status column to users table
Run this script to apply the migration safely in production.

Usage: python migrations/run_add_user_status_migration.py
"""
import sys
import os

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db

def run_migration():
    """Run the migration to add status column to users table"""
    app = create_app()
    
    with app.app_context():
        try:
            print("=" * 60)
            print("Running migration: Add status column to users table")
            print("=" * 60)
            print("\nThis will:")
            print("  1. Create user_status enum type (pre-register, pending, register)")
            print("  2. Add status column to users table")
            print("  3. Set all existing users to status='register'")
            print()
            
            # Step 1: Create the enum type (if it doesn't exist)
            print("[1/3] Creating user_status enum type...")
            db.session.execute(
                db.text("""
                    DO $$ 
                    BEGIN 
                        CREATE TYPE user_status AS ENUM ('pre-register', 'pending', 'register');
                    EXCEPTION 
                        WHEN duplicate_object THEN null;
                    END $$;
                """)
            )
            db.session.commit()
            print("✓ Enum type created (or already exists)")
            
            # Step 2: Add the status column with default 'register'
            print("\n[2/3] Adding status column to users table...")
            db.session.execute(
                db.text("""
                    ALTER TABLE users 
                    ADD COLUMN IF NOT EXISTS status user_status 
                    NOT NULL DEFAULT 'register';
                """)
            )
            db.session.commit()
            print("✓ Status column added")
            
            # Step 3: Ensure all existing records have 'register' status
            print("\n[3/3] Updating existing records to 'register'...")
            result = db.session.execute(
                db.text("UPDATE users SET status = 'register' WHERE status IS NULL")
            )
            db.session.commit()
            print(f"✓ Updated {result.rowcount} records")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("✓ All existing users have been set to status='register'")
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
