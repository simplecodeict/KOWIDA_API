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