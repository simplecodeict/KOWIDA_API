from flask import Blueprint, jsonify, request
from models.user import User
from models.reference import Reference
from extensions import db
from marshmallow import Schema, fields, validate, ValidationError
from datetime import datetime

class UserPhoneSchema(Schema):
    phone = fields.Str(required=True, validate=validate.Regexp(
        r'^[0-9]{9,10}$',
        error='Phone number must be 9 or 10 digits'
    ))

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/activate-user', methods=['POST'])
def activate_user():
    schema = UserPhoneSchema()
    try:
        # Validate request data
        data = schema.load(request.get_json())
        
        # Find user by phone number
        user = User.query.filter_by(phone=data['phone']).first()
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found with the provided phone number'
            }), 404
            
        # Check if user is already active
        if user.is_active:
            return jsonify({
                'status': 'error',
                'message': 'User is already active'
            }), 400
            
        # Update user status
        user.is_active = True
        user.updated_at = datetime.now()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'User activated successfully',
            'data': {
                'id': user.id,
                'full_name': user.full_name,
                'phone': user.phone,
                'is_active': user.is_active,
                'is_reference_paid': user.is_reference_paid,
                'updated_at': user.updated_at.isoformat()
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

@admin_bp.route('/mark-reference-paid', methods=['POST'])
def mark_reference_paid():
    schema = UserPhoneSchema()
    try:
        # Validate request data
        data = schema.load(request.get_json())
        
        # Find user by phone number
        user = User.query.filter_by(phone=data['phone']).first()
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found with the provided phone number'
            }), 404
            
        # Check if user is active
        if not user.is_active:
            return jsonify({
                'status': 'error',
                'message': 'Cannot mark reference as paid for inactive user'
            }), 400
            

        # Check if reference is already marked as paid
        if user.is_reference_paid:
            return jsonify({
                'status': 'error',
                'message': 'Reference payment is already marked as paid'
            }), 400
            
        # Update reference payment status
        user.is_reference_paid = True
        user.updated_at = datetime.now()
        db.session.commit()
        
        
        
        return jsonify({
            'status': 'success',
            'message': 'Reference payment marked as paid successfully',
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