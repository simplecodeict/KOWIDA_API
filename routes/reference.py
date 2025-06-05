from flask import Blueprint, jsonify, request
from models.reference import Reference
from models.user import User
from extensions import db, colombo_tz
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from schemas import ReferenceCreateSchema
from datetime import datetime
import uuid

reference_bp = Blueprint('reference', __name__)

@reference_bp.route('/reference/<code>', methods=['GET'])
def get_reference_by_code(code):
    try:
        # Find reference by code
        reference = Reference.query.filter_by(code=code).first()
        
        if not reference:
            return jsonify({
                'status': 'error',
                'message': 'Reference code not found'
            }), 404
            
        # Get user details using phone number
        user = User.query.filter_by(phone=reference.phone).first()
        
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found'
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': {
                'reference': {
                    'id': reference.id,
                    'code': reference.code,
                    'discount_amount': float(reference.discount_amount) if reference.discount_amount else None,
                    'received_amount': float(reference.received_amount) if reference.received_amount else None,
                    'created_at': reference.created_at.isoformat(),
                    'updated_at': reference.updated_at.isoformat()
                },
                'user': {
                    'full_name': user.full_name,
                    'phone': user.phone,
                    'url': user.url
                }
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@reference_bp.route('/reference', methods=['POST'])
@jwt_required()
def create_reference():
    schema = ReferenceCreateSchema()
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
            
        # Check if user already has a reference code
        existing_reference = Reference.query.filter_by(phone=data['phone']).first()
        if existing_reference:
            return jsonify({
                'status': 'error',
                'message': 'User already has a reference code'
            }), 409
            
        # Create new reference
        reference = Reference(
            code=data['promo_code'],
            phone=data['phone'],
            discount_amount=data['discount_amount'],
            received_amount=data['received_amount'],
            created_at=datetime.now(colombo_tz),
            updated_at=datetime.now(colombo_tz)
        )
        
        db.session.add(reference)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Reference code created successfully',
            'data': {
                'reference': {
                    'id': reference.id,
                    'code': reference.code,
                    'discount_amount': float(reference.discount_amount),
                    'received_amount': float(reference.received_amount),
                    'created_at': reference.created_at.isoformat(),
                    'updated_at': reference.updated_at.isoformat()
                },
                'user': {
                    'full_name': user.full_name,
                    'phone': user.phone,
                    'url': user.url
                }
            }
        }), 201
        
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

@reference_bp.route('/my-earnings', methods=['GET'])
@jwt_required()
def get_my_earnings():
    try:
        # Get current user from JWT token
        current_user_id = int(get_jwt_identity())
        
        # Get user details
        user = User.query.get(current_user_id)
        if not user or not user.is_active:
            return jsonify({
                'status': 'error',
                'message': 'User not found or inactive'
            }), 404
            
        # Find user's reference code
        reference = Reference.query.filter_by(phone=user.phone).first()
        if not reference:
            return jsonify({
                'status': 'error',
                'message': 'No reference code found for your account'
            }), 404
            
        # Find all users who used this reference code
        referred_users = User.query.filter_by(promo_code=reference.code).all()
        
        # Calculate total earnings
        total_earnings = float(reference.received_amount * len(referred_users)) if reference.received_amount else 0
        
        # Prepare referred users data
        referred_users_data = []
        for ref_user in referred_users:
            referred_users_data.append({
                'full_name': ref_user.full_name,
                'phone': ref_user.phone,
                'registered_at': ref_user.created_at.isoformat(),
                'is_active': ref_user.is_active,
                'is_reference_paid': ref_user.is_reference_paid
            })
            
        return jsonify({
            'status': 'success',
            'data': {
                'reference_code': reference.code,
                'discount_amount': float(reference.discount_amount) if reference.discount_amount else 0,
                'received_amount': float(reference.received_amount) if reference.received_amount else 0,
                'total_referrals': len(referred_users),
                'total_earnings': total_earnings,
                'referred_users': referred_users_data
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 