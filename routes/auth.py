from flask import Blueprint, request, jsonify, current_app
from extensions import db, bcrypt, jwt
from models.user import User
from schemas import UserRegistrationSchema, LoginSchema
from sqlalchemy.exc import IntegrityError
from marshmallow import ValidationError
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
    decode_token
)
from datetime import datetime, timedelta
import logging
import os
import json
import secrets
import time
import random

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

def generate_token(user_id):
    """Generate JWT token with user claims"""
    try:
        logger.debug(f"Generating token for user_id: {user_id}")
        
        # Convert user_id to string for consistency
        user_id_str = str(user_id)
        
        # Get current timestamp
        current_time = datetime.utcnow()
        
        # Create additional claims with enhanced security
        additional_claims = {
            "user_id": user_id_str,
            "token_type": "access",
            "type": "access",  # For backward compatibility
            "iat": current_time.timestamp(),  # Issued at
            "nbf": current_time.timestamp(),  # Not valid before
            "jti": secrets.token_urlsafe(32),  # Unique token ID
            "scope": "access",  # Token scope
            "fresh": False  # Token freshness
        }
        
        # Generate token with enhanced settings
        access_token = create_access_token(
            identity=user_id_str,
            additional_claims=additional_claims,
            fresh=False
        )
        
        # Debug: Decode the token we just created to verify its contents
        try:
            decoded = decode_token(access_token)
            # Log only non-sensitive parts of the token
            logger.debug(f"Token generated with algorithm: {decoded.get('type')}")
            logger.debug(f"Token expiration: {datetime.fromtimestamp(decoded.get('exp'))}")
        except Exception as decode_error:
            logger.error(f"Error decoding generated token: {str(decode_error)}")
        
        return access_token
    except Exception as e:
        logger.error(f"Error generating token: {str(e)}", exc_info=True)
        raise

@auth_bp.route('/register', methods=['POST'])
def register():
    schema = UserRegistrationSchema()
    try:
        # Validate request data
        data = schema.load(request.get_json())
        logging.info(f"Received registration data: {data}")
        
        # Check if user already exists
        existing_user = User.query.filter_by(phone=data['phone']).first()
        if existing_user:
            return jsonify({
                'status': 'error',
                'message': 'Phone number already registered',
                'error_code': 'PHONE_ALREADY_EXISTS'
            }), 409
            
        # Create new user
        try:
            new_user = User(
                full_name=data['full_name'],
                phone=data['phone'],
                password=data['password'],
                url=data['url'],
                promo_code=data.get('promo_code')
            )
            db.session.add(new_user)
            db.session.commit()
            
            # Generate access token
            access_token = generate_token(new_user.id)
            
            return jsonify({
                'status': 'success',
                'message': 'User registered successfully',
                'data': {
                    'user': {
                        'id': new_user.id,
                        'full_name': new_user.full_name,
                        'phone': new_user.phone,
                        'url': new_user.url,
                        'is_active': new_user.is_active,
                        'created_at': new_user.created_at.isoformat()
                    },
                    'access_token': access_token
                }
            }), 201
            
        except ValueError as e:
            logging.error(f"Validation error during user creation: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e),
                'error_code': 'VALIDATION_ERROR'
            }), 400
            
    except ValidationError as e:
        logging.error(f"Schema validation error: {e.messages}")
        return jsonify({
            'status': 'error',
            'message': 'Validation error',
            'errors': e.messages,
            'error_code': 'VALIDATION_ERROR'
        }), 400
        
    except Exception as e:
        logging.error(f"Unexpected error during registration: {str(e)}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e),
            'error_code': 'REGISTRATION_ERROR'
        }), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    schema = LoginSchema()
    try:
        # Rate limiting check could be added here
        
        # Log request (excluding sensitive data)
        logger.debug(f"Login attempt from IP: {request.remote_addr}")
        
        # Validate request data
        data = schema.load(request.get_json())
        
        # Find user by phone
        user = User.query.filter_by(phone=data['phone']).first()
        
        # Use constant-time comparison for password check
        if not user or not bcrypt.check_password_hash(user.password, data['password']):
            # Add delay to prevent timing attacks
            time.sleep(random.uniform(0.1, 0.3))
            return jsonify({
                'status': 'error',
                'message': 'Invalid phone number or password',
                'error_code': 'INVALID_CREDENTIALS'
            }), 401
            
        # Check if user is active
        if not user.is_active:
            return jsonify({
                'status': 'error',
                'message': 'Account is not activated',
                'error_code': 'ACCOUNT_INACTIVE'
            }), 403
            
        # Generate access token
        access_token = generate_token(user.id)
        
        # Create response
        response_data = {
            'status': 'success',
            'message': 'Login successful',
            'data': {
                'user': {
                    'id': user.id,
                    'full_name': user.full_name,
                    'phone': user.phone,
                    'url': user.url,
                    'is_active': user.is_active,
                    'is_reference_paid': user.is_reference_paid
                },
                'access_token': access_token
            }
        }
        
        # Create response object
        response = jsonify(response_data)
        
        # Set secure headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        return response, 200
        
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': 'Validation error',
            'errors': e.messages,
            'error_code': 'VALIDATION_ERROR'
        }), 400
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while processing login',
            'error_code': 'LOGIN_ERROR'
        }), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    try:
        # Get both the identity and the full JWT claims
        current_user_id = get_jwt_identity()
        jwt_claims = get_jwt()
        
        # Verify the token type
        if jwt_claims.get('token_type') != 'access':
            return jsonify({
                'status': 'error',
                'message': 'Invalid token type',
                'error_code': 'INVALID_TOKEN_TYPE'
            }), 401
        
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found',
                'error_code': 'USER_NOT_FOUND'
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': {
                'user': {
                    'id': user.id,
                    'full_name': user.full_name,
                    'phone': user.phone,
                    'url': user.url,
                    'is_active': user.is_active,
                    'is_reference_paid': user.is_reference_paid,
                    'created_at': user.created_at.isoformat(),
                    'updated_at': user.updated_at.isoformat()
                }
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Error fetching user data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while fetching user data',
            'error_code': 'USER_FETCH_ERROR'
        }), 500

@auth_bp.route('/verify-token', methods=['GET'])
@jwt_required()
def verify_token():
    try:
        # Log request headers
        logger.debug("Token verification request")
        logger.debug(f"Request headers: {dict(request.headers)}")
        
        # Extract token from header
        auth_header = request.headers.get('Authorization', '')
        logger.debug(f"Auth header: {auth_header}")
        
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            logger.debug(f"Extracted token length: {len(token)}")
            
            # Try to decode the token manually
            try:
                decoded = decode_token(token)
                logger.debug(f"Successfully decoded token: {json.dumps(decoded)}")
            except Exception as decode_error:
                logger.error(f"Error decoding token: {str(decode_error)}", exc_info=True)
                return jsonify({
                    'status': 'error',
                    'message': f'Token decode error: {str(decode_error)}',
                    'error_code': 'TOKEN_DECODE_ERROR'
                }), 401
        
        # Get identity and claims
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
                'error_code': 'CLAIMS_ERROR'
            }), 401
        
        return jsonify({
            'status': 'success',
            'message': 'Token is valid',
            'data': {
                'user_id': current_user_id,
                'claims': jwt_claims
            }
        }), 200
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e),
            'error_code': 'TOKEN_VERIFICATION_FAILED'
        }), 401 