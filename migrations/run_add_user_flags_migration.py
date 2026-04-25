"""Standalone script to add user access flags to users table.
Run this script to apply the migration safely in production.

Usage: python migrations/run_add_user_flags_migration.py
"""
import os
import sys

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db


def run_migration():
    """Run the migration to add is_spoken, is_topik, have_recording_access columns."""
    app = create_app()

    with app.app_context():
        try:
            print("=" * 60)
            print("Running migration: Add user boolean flags to users table")
            print("=" * 60)
            print("\nThis will:")
            print("  1. Add is_spoken column (boolean, default FALSE)")
            print("  2. Add is_topik column (boolean, default FALSE)")
            print("  3. Add have_recording_access column (boolean, default FALSE)")
            print("  4. Set all NULL values to FALSE")
            print()

            print("[1/4] Adding is_spoken column to users table...")
            db.session.execute(
                db.text(
                    """
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS is_spoken BOOLEAN
                    NOT NULL DEFAULT FALSE;
                    """
                )
            )
            db.session.commit()
            print("✓ is_spoken column added")

            print("\n[2/4] Adding is_topik column to users table...")
            db.session.execute(
                db.text(
                    """
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS is_topik BOOLEAN
                    NOT NULL DEFAULT FALSE;
                    """
                )
            )
            db.session.commit()
            print("✓ is_topik column added")

            print("\n[3/4] Adding have_recording_access column to users table...")
            db.session.execute(
                db.text(
                    """
                    ALTER TABLE users
                    ADD COLUMN IF NOT EXISTS have_recording_access BOOLEAN
                    NOT NULL DEFAULT FALSE;
                    """
                )
            )
            db.session.commit()
            print("✓ have_recording_access column added")

            print("\n[4/4] Updating existing records to FALSE where needed...")
            result = db.session.execute(
                db.text(
                    """
                    UPDATE users
                    SET
                        is_spoken = COALESCE(is_spoken, FALSE),
                        is_topik = COALESCE(is_topik, FALSE),
                        have_recording_access = COALESCE(have_recording_access, FALSE)
                    WHERE
                        is_spoken IS NULL
                        OR is_topik IS NULL
                        OR have_recording_access IS NULL;
                    """
                )
            )
            db.session.commit()
            print(f"✓ Updated {result.rowcount} records")

            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
            print("✓ New and existing users default to FALSE for all 3 flags")
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


if __name__ == "__main__":
    exit_code = run_migration()
    sys.exit(exit_code)
