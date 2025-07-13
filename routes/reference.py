from flask import Blueprint, jsonify, request
from models.reference import Reference
from models.user import User
from extensions import db, colombo_tz
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    get_jwt,
    verify_jwt_in_request,
    decode_token
)
from marshmallow import ValidationError, Schema, fields
from schemas import ReferenceCreateSchema
from datetime import datetime
import logging
import json
from flask import current_app
from sqlalchemy import and_, or_

logger = logging.getLogger(__name__)

reference_bp = Blueprint('reference', __name__)

class ReferenceUserFilterSchema(Schema):
    """Schema for reference user filter parameters"""
    page = fields.Integer(load_default=1, validate=lambda n: n > 0)
    per_page = fields.Integer(load_default=10, validate=lambda n: 0 < n <= 100)
    start_date = fields.Date(load_default=None)
    end_date = fields.Date(load_default=None)
    phone = fields.String(load_default=None)
    is_active = fields.Boolean(load_default=None)
    is_reference_paid = fields.Boolean(load_default=None)

@reference_bp.route('/reference/<code>', methods=['GET'])
def get_reference_by_code(code):
    try:
        # Find reference by code and ensure it's active
        reference = Reference.query.filter_by(code=code, is_active=True).first()
        
        if not reference:
            return jsonify({
                'status': 'error',
                'message': 'Reference code not found or inactive'
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
                    'is_active': reference.is_active,
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

@reference_bp.route('/reference/users', methods=['GET'])
@jwt_required()
def get_reference_users():
    """
    Get paginated and filtered list of referred users
    Query parameters:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 10, max: 100)
    - start_date: Filter by registration date (YYYY-MM-DD)
    - end_date: Filter by registration date (YYYY-MM-DD)
    - phone: Filter by phone number
    - is_active: Filter by active status
    - is_reference_paid: Filter by reference payment status
    """
    try:
        logger.debug("=== Starting /reference/users endpoint ===")
        
        # Validate JWT and get current user
        try:
            current_user_id = get_jwt_identity()
            jwt_claims = get_jwt()
            logger.debug(f"JWT identity: {current_user_id}")
            
            if jwt_claims.get('token_type') != 'access':
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid token type',
                    'error_code': 'INVALID_TOKEN_TYPE'
                }), 401
        except Exception as claims_error:
            logger.error(f"JWT claims error: {str(claims_error)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Invalid authentication token',
                'error_code': 'INVALID_TOKEN'
            }), 401
            
        # Get current user
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }), 404
            
        if not user.is_active:
            return jsonify({
                'status': 'error',
                'message': 'User account is not active',
                'error_code': 'ACCOUNT_INACTIVE'
            }), 403
            
        # Get user's reference code
        reference = Reference.query.filter_by(phone=user.phone).first()
        if not reference:
            return jsonify({
                'status': 'error',
                'message': 'No reference code found for your account',
                'error_code': 'NO_REFERENCE_CODE'
            }), 404
            
        # Validate and parse query parameters
        try:
            filter_schema = ReferenceUserFilterSchema()
            params = filter_schema.load(request.args)
            logger.debug(f"Filter parameters: {params}")
        except ValidationError as e:
            return jsonify({
                'status': 'error',
                'message': 'Invalid filter parameters',
                'errors': e.messages,
                'error_code': 'INVALID_PARAMETERS'
            }), 400
            
        # Build query
        query = User.query.filter_by(promo_code=reference.code)
        
        # Apply filters
        if params.get('start_date'):
            query = query.filter(User.created_at >= params['start_date'])
            
        if params.get('end_date'):
            # Add one day to include the end date fully
            end_date = datetime.combine(params['end_date'], datetime.max.time())
            query = query.filter(User.created_at <= end_date)
            
        if params.get('phone'):
            query = query.filter(User.phone.ilike(f"%{params['phone']}%"))
            
        if params.get('is_active') is not None:
            query = query.filter(User.is_active == params['is_active'])
            
        if params.get('is_reference_paid') is not None:
            query = query.filter(User.is_reference_paid == params['is_reference_paid'])
            
        # Execute paginated query
        try:
            paginated_users = query.paginate(
                page=params['page'],
                per_page=params['per_page'],
                error_out=False
            )
        except Exception as e:
            logger.error(f"Database query error: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'Error fetching users',
                'error_code': 'DATABASE_ERROR'
            }), 500
            
        # Calculate earnings for filtered users
        filtered_earnings = float(reference.received_amount * len(paginated_users.items)) if reference.received_amount else 0
        
        # Prepare response data
        users_data = [{
            'full_name': user.full_name,
            'phone': user.phone,
            'registered_at': user.created_at.isoformat(),
            'is_active': user.is_active,
            'is_reference_paid': user.is_reference_paid
        } for user in paginated_users.items]
        
        response_data = {
            'status': 'success',
            'data': {
                'reference_code': reference.code,
                'discount_amount': float(reference.discount_amount) if reference.discount_amount else 0,
                'received_amount': float(reference.received_amount) if reference.received_amount else 0,
                'pagination': {
                    'current_page': paginated_users.page,
                    'total_pages': paginated_users.pages,
                    'total_items': paginated_users.total,
                    'has_next': paginated_users.has_next,
                    'has_prev': paginated_users.has_prev,
                    'items_per_page': params['per_page']
                },
                'filtered_earnings': filtered_earnings,
                'users': users_data
            }
        }
        
        logger.debug(f"Successfully retrieved {len(users_data)} users")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Unexpected error in reference users endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred',
            'error_code': 'INTERNAL_SERVER_ERROR'
        }), 500 