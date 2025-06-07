from flask import Blueprint, jsonify, request
from models.reference import Reference
from models.user import User
from extensions import db, colombo_tz
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    get_jwt,
    verify_jwt_in_request
)
from marshmallow import ValidationError
from schemas import ReferenceCreateSchema
from datetime import datetime
import logging
import json
from flask import current_app

logger = logging.getLogger(__name__)

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
        logging.error(f"Error getting reference by code: {str(e)}")
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
        logging.error(f"Error creating reference: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@reference_bp.route('/my-earnings', methods=['GET'])
@jwt_required()
def get_my_earnings():
    try:
        logger.debug("=== Starting /my-earnings endpoint ===")
        
        # Log request headers and environment
        logger.debug(f"All request headers: {dict(request.headers)}")
        auth_header = request.headers.get('Authorization')
        logger.debug(f"Authorization header: {auth_header}")
        
        # Log JWT configuration
        logger.debug(f"JWT_SECRET_KEY length: {len(current_app.config['JWT_SECRET_KEY'])}")
        logger.debug(f"JWT configuration: {json.dumps(current_app.config['JWT_TOKEN_LOCATION'])}")
        
        # Extract and decode token manually
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            logger.debug(f"Extracted token length: {len(token)}")
            try:
                decoded = decode_token(token)
                logger.debug(f"Successfully decoded token manually: {json.dumps(decoded)}")
            except Exception as decode_error:
                logger.error(f"Manual token decode failed: {str(decode_error)}", exc_info=True)
        
        # Get current user from JWT token and claims
        try:
            current_user_id = get_jwt_identity()
            jwt_claims = get_jwt()
            logger.debug(f"JWT identity: {current_user_id}")
            logger.debug(f"JWT claims: {jwt_claims}")
        except Exception as claims_error:
            logger.error(f"Error getting JWT claims: {str(claims_error)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': f'Claims error: {str(claims_error)}',
                'error_details': str(claims_error)
            }), 401
        
        # Verify token type
        if jwt_claims.get('token_type') != 'access':
            logger.error(f"Invalid token type: {jwt_claims.get('token_type')}")
            return jsonify({
                'status': 'error',
                'message': 'Invalid token type',
                'error_code': 'INVALID_TOKEN_TYPE'
            }), 401
            
        # Get user details
        user = User.query.get(current_user_id)
        logger.debug(f"Found user: {user.id if user else None}")
        
        if not user:
            logger.error(f"User not found for ID: {current_user_id}")
            return jsonify({
                'status': 'error',
                'message': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }), 404
            
        if not user.is_active:
            logger.error(f"Inactive user attempted access: {current_user_id}")
            return jsonify({
                'status': 'error',
                'message': 'User account is not active',
                'error_code': 'ACCOUNT_INACTIVE'
            }), 403
            
        # Find user's reference code
        reference = Reference.query.filter_by(phone=user.phone).first()
        logger.debug(f"Found reference for user: {reference.id if reference else None}")
        
        if not reference:
            logger.error(f"No reference found for user: {current_user_id}")
            return jsonify({
                'status': 'error',
                'message': 'No reference code found for your account'
            }), 404
            
        # Find all users who used this reference code
        referred_users = User.query.filter_by(promo_code=reference.code).all()
        logger.debug(f"Found {len(referred_users)} referred users")
        
        # Calculate total earnings
        total_earnings = float(reference.received_amount * len(referred_users)) if reference.received_amount else 0
        logger.debug(f"Calculated total earnings: {total_earnings}")
        
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
        
        response_data = {
            'status': 'success',
            'data': {
                'reference_code': reference.code,
                'discount_amount': float(reference.discount_amount) if reference.discount_amount else 0,
                'received_amount': float(reference.received_amount) if reference.received_amount else 0,
                'total_referrals': len(referred_users),
                'total_earnings': total_earnings,
                'referred_users': referred_users_data
            }
        }
        logger.debug("Successfully prepared response")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error in my-earnings endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 