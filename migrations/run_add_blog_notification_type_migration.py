"""Standalone script to add 'blog' value to notification_types enum type
Run this script to apply the migration safely in production.

Usage: python migrations/run_add_blog_notification_type_migration.py
"""
import sys
import os

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db

def run_migration():
    """Run the migration to add 'blog' value to notification_types enum type"""
    app = create_app()

    with app.app_context():
        try:
            print("=" * 60)
            print("Running migration: Add 'blog' value to notification_types enum")
            print("=" * 60)
            print("\nThis will:")
            print("  1. Add 'blog' value to existing notification_types enum type")
            print()

            print("[1/1] Adding 'blog' value to notification_types enum type...")
            db.session.execute(
                db.text("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_enum
                            WHERE enumlabel = 'blog'
                            AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'notification_types')
                        ) THEN
                            ALTER TYPE notification_types ADD VALUE 'blog';
                        END IF;
                    END $$;
                """)
            )
            db.session.commit()
            print("✓ 'blog' value added to notification_types enum (or already exists)")

            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("✓ The notification_types enum now includes: 'announcement', 'quotes', 'news', 'boost_knowledge', 'blog'")
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
