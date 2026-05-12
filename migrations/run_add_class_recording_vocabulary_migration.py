"""Standalone script to add vocabulary_pdf_url and vocabulary_audio_track to class_recordings.
Run this script to apply the migration safely in production.

Usage: python migrations/run_add_class_recording_vocabulary_migration.py
"""
import os
import sys

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from extensions import db


def run_migration():
    """Run the migration to add nullable vocabulary columns to class_recordings."""
    app = create_app()

    with app.app_context():
        try:
            print("=" * 60)
            print(
                "Running migration: Add vocabulary_pdf_url, vocabulary_audio_track "
                "to class_recordings"
            )
            print("=" * 60)
            print("\nThis will:")
            print("  1. Add vocabulary_pdf_url column (VARCHAR(500), nullable)")
            print("  2. Add vocabulary_audio_track column (VARCHAR(500), nullable)")
            print()

            print("[1/2] Adding vocabulary_pdf_url column...")
            db.session.execute(
                db.text(
                    """
                    ALTER TABLE class_recordings
                    ADD COLUMN IF NOT EXISTS vocabulary_pdf_url VARCHAR(500);
                    """
                )
            )
            db.session.commit()
            print("✓ vocabulary_pdf_url column added")

            print("\n[2/2] Adding vocabulary_audio_track column...")
            db.session.execute(
                db.text(
                    """
                    ALTER TABLE class_recordings
                    ADD COLUMN IF NOT EXISTS vocabulary_audio_track VARCHAR(500);
                    """
                )
            )
            db.session.commit()
            print("✓ vocabulary_audio_track column added")

            print("\n" + "=" * 60)
            print("✓ Migration completed successfully!")
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
