from flask import Blueprint, request, jsonify
from extensions import db
from models.user import User
from models.bank_details import BankDetails
from schemas import BankDetailsSchema, AdminBankDetailsSchema
from marshmallow import ValidationError
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from extensions import colombo_tz

bank_bp = Blueprint('bank', __name__)

@bank_bp.route('/bank-details', methods=['POST'])
@jwt_required()
def upsert_bank_details():
    schema = BankDetailsSchema()
    try:
        # Get current user from JWT token and convert to integer
        current_user_id = int(get_jwt_identity())
        
        # Validate request data
        data = schema.load(request.get_json())
        
        # Check if user exists and is active
        user = User.query.get(current_user_id)
        if not user or not user.is_active:
            return jsonify({
                'status': 'error',
                'message': 'User not found or inactive'
            }), 404
            
        # Check if bank details already exist for the user
        bank_details = BankDetails.query.filter_by(user_id=current_user_id).first()
        
        current_time = datetime.now(colombo_tz)
        
        if bank_details:
            # Update existing bank details
            bank_details.name = data['name']
            bank_details.bank_name = data['bank_name']
            bank_details.branch = data['branch']
            bank_details.account_number = data['account_number']
            bank_details.updated_at = current_time
            message = 'Bank details updated successfully'
        else:
            # Create new bank details
            bank_details = BankDetails(
                user_id=current_user_id,
                name=data['name'],
                bank_name=data['bank_name'],
                branch=data['branch'],
                account_number=data['account_number'],
                created_at=current_time,
                updated_at=current_time
            )
            db.session.add(bank_details)
            message = 'Bank details added successfully'
            
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': message,
            'data': {
                'id': bank_details.id,
                'name': bank_details.name,
                'bank_name': bank_details.bank_name,
                'branch': bank_details.branch,
                'account_number': bank_details.account_number,
                'created_at': bank_details.created_at.isoformat(),
                'updated_at': bank_details.updated_at.isoformat()
            }
        }), 200
        
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': 'Validation error',
            'errors': e.messages
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bank_bp.route('/bank-details', methods=['GET'])
@jwt_required()
def get_bank_details():
    try:
        # Get current user from JWT token and convert to integer
        current_user_id = int(get_jwt_identity())
        
        # Check if user exists and is active
        user = User.query.get(current_user_id)
        if not user or not user.is_active:
            return jsonify({
                'status': 'error',
                'message': 'User not found or inactive'
            }), 404
            
        # Get bank details
        bank_details = BankDetails.query.filter_by(user_id=current_user_id).first()
        
        if not bank_details:
            return jsonify({
                'status': 'error',
                'message': 'Bank details not found'
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': {
                'id': bank_details.id,
                'name': bank_details.name,
                'bank_name': bank_details.bank_name,
                'branch': bank_details.branch,
                'account_number': bank_details.account_number,
                'created_at': bank_details.created_at.isoformat(),
                'updated_at': bank_details.updated_at.isoformat()
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bank_bp.route('/admin/bank-details', methods=['POST'])
@jwt_required()
def admin_create_bank_details():
    schema = AdminBankDetailsSchema()
    try:
        # Validate request data
        data = schema.load(request.get_json())
        
        # Find user by phone number and check if active
        user = User.query.filter_by(phone=data['phone']).first()
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found with the provided phone number'
            }), 404
            
        if not user.is_active:
            return jsonify({
                'status': 'error',
                'message': 'User account is not active'
            }), 400
            
        # Check if bank details already exist for the user
        existing_bank = BankDetails.query.filter_by(user_id=user.id).first()
        if existing_bank:
            # Update existing bank details
            existing_bank.name = data['name']
            existing_bank.bank_name = data['bank_name']
            existing_bank.branch = data['branch']
            existing_bank.account_number = data['account_number']
            existing_bank.updated_at = datetime.now(colombo_tz)
            message = 'Bank details updated successfully'
        else:
            # Create new bank details
            bank_details = BankDetails(
                user_id=user.id,
                name=data['name'],
                bank_name=data['bank_name'],
                branch=data['branch'],
                account_number=data['account_number'],
                created_at=datetime.now(colombo_tz),
                updated_at=datetime.now(colombo_tz)
            )
            db.session.add(bank_details)
            message = 'Bank details added successfully'
            
        db.session.commit()
        
        # Get the bank details to return in response
        bank_details = BankDetails.query.filter_by(user_id=user.id).first()
        
        return jsonify({
            'status': 'success',
            'message': message,
            'data': {
                'bank_details': {
                    'id': bank_details.id,
                    'name': bank_details.name,
                    'bank_name': bank_details.bank_name,
                    'branch': bank_details.branch,
                    'account_number': bank_details.account_number,
                    'created_at': bank_details.created_at.isoformat(),
                    'updated_at': bank_details.updated_at.isoformat()
                },
                'user': {
                    'id': user.id,
                    'full_name': user.full_name,
                    'phone': user.phone,
                    'is_active': user.is_active
                }
            }
        }), 201 if message == 'Bank details added successfully' else 200
        
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': 'Validation error',
            'errors': e.messages
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 