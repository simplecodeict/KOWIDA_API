"""Standalone script to add 'declined' value to user_status enum type
Run this script to apply the migration safely in production.

Usage: python migrations/run_add_declined_status_migration.py
"""
import sys
import os

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db

def run_migration():
    """Run the migration to add 'declined' value to user_status enum type"""
    app = create_app()
    
    with app.app_context():
        try:
            print("=" * 60)
            print("Running migration: Add 'declined' value to user_status enum")
            print("=" * 60)
            print("\nThis will:")
            print("  1. Add 'declined' value to existing user_status enum type")
            print()
            
            # Step 1: Add 'declined' value to the enum type
            print("[1/1] Adding 'declined' value to user_status enum type...")
            db.session.execute(
                db.text("""
                    DO $$ 
                    BEGIN 
                        -- Check if 'declined' value already exists
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_enum 
                            WHERE enumlabel = 'declined' 
                            AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'user_status')
                        ) THEN
                            ALTER TYPE user_status ADD VALUE 'declined';
                        END IF;
                    END $$;
                """)
            )
            db.session.commit()
            print("✓ 'declined' value added to user_status enum (or already exists)")
            
            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("✓ The user_status enum now includes: 'pre-register', 'pending', 'register', 'declined'")
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
