#!/usr/bin/env python3
"""
Seeder script to create dummy users for development/testing purposes.
Run this script to populate the database with test data.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from extensions import db
from models.user import User

def create_dummy_user():
    """
    Create a dummy user with the specified credentials:
    - full_name: 'test'
    - phone: '0785858569' (valid 10-digit phone number)
    - password: '4858'
    """
    try:
        # Create Flask app context
        app = create_app()
        
        with app.app_context():
            # Check if user already exists
            existing_user = User.query.filter_by(phone='0785858569').first()
            if existing_user:
                print("User with phone '0785858569' already exists!")
                print(f"User ID: {existing_user.id}")
                print(f"Full Name: {existing_user.full_name}")
                print(f"Phone: {existing_user.phone}")
                print(f"Role: {existing_user.role}")
                print(f"Is Active: {existing_user.is_active}")
                return
            
            # Create new dummy user
            dummy_user = User(
                full_name='test',
                phone='0785858569',  # Valid 10-digit phone number
                password='4858',
                url=None,  # Default value
                payment_method='card_payment',  # Default value
                promo_code=None,  # Default value
                role='admin',  # Default value
                paid_amount=0  # Default valueclear
                
            )
            
            # Set additional fields after creation
            dummy_user.is_active = True
            dummy_user.is_reference_paid = True
            
            # Add user to database
            db.session.add(dummy_user)
            db.session.commit()
            
            print("✅ Dummy user created successfully!")
            print(f"User ID: {dummy_user.id}")
            print(f"Full Name: {dummy_user.full_name}")
            print(f"Phone: {dummy_user.phone}")
            print(f"Password: 4858")
            print(f"Role: {dummy_user.role}")
            print(f"Is Active: {dummy_user.is_active}")
            print(f"Payment Method: {dummy_user.payment_method}")
            print(f"Paid Amount: {dummy_user.paid_amount}")
            print(f"Created At: {dummy_user.created_at}")
            
    except Exception as e:
        print(f"❌ Error creating dummy user: {str(e)}")
        if hasattr(e, 'orig'):
            print(f"Original error: {e.orig}")
        sys.exit(1)

def main():
    """
    Main function to run the seeder
    """
    print("🌱 Starting user seeder...")
    print("Creating dummy user with credentials:")
    print("- Full Name: test")
    print("- Phone: 0785858569")
    print("- Password: 4858")
    print("- Other fields: default values")
    print("-" * 50)
    
    create_dummy_user()
    
    print("-" * 50)
    print("🎉 Seeder completed!")

if __name__ == "__main__":
    main() 