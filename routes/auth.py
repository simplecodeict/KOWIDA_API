from flask import Blueprint, request, jsonify, current_app
from extensions import db, bcrypt, jwt, upload_file_to_s3
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
        s3_url = None
        bank_slip = None
        
        # Check if bank slip or document is present in request
        if 'bank_slip' in request.files:
            bank_slip = request.files['bank_slip']
        elif 'document' in request.files:
            bank_slip = request.files['document']
            
        # Validate request data first
        try:
            data = schema.load(request.form)
        except ValidationError as e:
            return jsonify({
                'status': 'error',
                'message': 'Validation error',
                'errors': e.messages,
                'error_code': 'VALIDATION_ERROR'
            }), 400
        
        logging.info(f"Received registration data: {data}")
        
        # Check if user already exists BEFORE uploading to S3
        existing_user = User.query.filter_by(phone=data['phone']).first()
        if existing_user:
            return jsonify({
                'status': 'error',
                'message': 'Phone number already registered',
                'error_code': 'PHONE_ALREADY_EXISTS'
            }), 409
            
        # Validate and upload file if present (only after phone validation)
        if bank_slip:
            # Validate file
            if bank_slip.filename == '':
                return jsonify({
                    'status': 'error',
                    'message': 'No file selected',
                    'error_code': 'NO_FILE_SELECTED'
                }), 400

            # Validate file type
            allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg'}
            file_extension = bank_slip.filename.rsplit('.', 1)[1].lower() if '.' in bank_slip.filename else ''
            
            if not file_extension or file_extension not in allowed_extensions:
                return jsonify({
                    'status': 'error',
                    'message': f'Invalid file type. Allowed types: {", ".join(allowed_extensions)}',
                    'error_code': 'INVALID_FILE_TYPE'
                }), 400

            # Validate file size (max 5MB)
            max_size = 5 * 1024 * 1024  # 5MB in bytes
            file_data = bank_slip.read()
            if len(file_data) > max_size:
                return jsonify({
                    'status': 'error',
                    'message': 'File size exceeds maximum limit of 5MB',
                    'error_code': 'FILE_TOO_LARGE'
                }), 400

            # Upload to S3 (only after all validations pass)
            try:
                s3_url = upload_file_to_s3(file_data, bank_slip.filename)
            except ValueError as e:
                return jsonify({
                    'status': 'error',
                    'message': str(e),
                    'error_code': 'S3_UPLOAD_ERROR'
                }), 500
            except Exception as e:
                logger.error(f"Unexpected error uploading bank slip: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to upload bank slip. Please try again.',
                    'error_code': 'UPLOAD_ERROR'
                }), 500
            
        # Create new user with S3 URL
        try:
            # Determine payment method based on whether bank slip was provided
            payment_method = 'bank_deposit' if s3_url else 'card_payment'
            is_active = True if payment_method == 'card_payment' else False
            
            # Get paid_amount from form data, default to 0
            if data.get('paid_amount'):
                paid_amount = float(data.get('paid_amount', 0))
            elif data.get('referal_coin'):
                paid_amount = float(data.get('referal_coin', 0))
            else:
                paid_amount = 0
            
            # Validate paid_amount for user role
            if data.get('role') == 'user' and paid_amount == 0:
                return jsonify({
                    'status': 'error',
                    'message': 'Paid amount cannot be 0 for users with role "user"',
                    'error_code': 'INVALID_PAID_AMOUNT'
                }), 400
            
            new_user = User(
                full_name=data['full_name'],
                phone=data['phone'],
                password=data['password'],
                url=s3_url,  # Store S3 URL in the url field
                payment_method=payment_method,
                promo_code=data.get('promo_code'),
                role=data.get('role'),
                paid_amount=paid_amount
            )
            
            # Set is_active based on payment method
            new_user.is_active = is_active
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
                        'paid_amount': float(new_user.paid_amount),
                        'created_at': new_user.created_at.isoformat()
                    },
                    'access_token': access_token
                }
            }), 201
            
        except ValueError as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': str(e),
                'error_code': 'VALIDATION_ERROR'
            }), 400
        except IntegrityError as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': 'Database integrity error occurred',
                'error_code': 'DATABASE_ERROR'
            }), 500
            
    except Exception as e:
        logger.error(f"Unexpected error during registration: {str(e)}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred during registration',
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

@auth_bp.route('/admin/login', methods=['POST'])
def admin_login():
    schema = LoginSchema()
    try:
        # Rate limiting check could be added here
        
        # Log request (excluding sensitive data)
        logger.debug(f"Admin login attempt from IP: {request.remote_addr}")
        
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
            
        # Check if user has admin role
        if user.role != 'admin':
            return jsonify({
                'status': 'error',
                'message': 'Access denied. Admin privileges required.',
                'error_code': 'ADMIN_ACCESS_REQUIRED'
            }), 403
            
        # Generate access token
        access_token = generate_token(user.id)
        
        # Create response
        response_data = {
            'status': 'success',
            'message': 'Admin login successful',
            'data': {
                'user': {
                    'id': user.id,
                    'full_name': user.full_name,
                    'phone': user.phone,
                    'url': user.url,
                    'is_active': user.is_active,
                    'is_reference_paid': user.is_reference_paid,
                    'role': user.role
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
        logger.error(f"Admin login error: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while processing admin login',
            'error_code': 'ADMIN_LOGIN_ERROR'
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
            
        # Get user's reference data
        from models.reference import Reference
        reference = Reference.query.filter_by(phone=user.phone).first()
        
        # Prepare referral data
        referral_data = None
        if reference:
            # Get all users who used this reference code
            referred_users = User.query.filter_by(promo_code=reference.code).all()
            
            # Calculate statistics
            total_referrals = len(referred_users)
            active_referrals = sum(1 for u in referred_users if u.is_active)
            paid_referrals = sum(1 for u in referred_users if u.is_reference_paid)
            
            # Calculate earnings
            total_earnings = float(reference.received_amount * total_referrals) if reference.received_amount else 0
            
            referral_data = {
                'reference_code': reference.code,
                'discount_amount': float(reference.discount_amount) if reference.discount_amount else 0,
                'received_amount': float(reference.received_amount) if reference.received_amount else 0,
                'total_referrals': total_referrals,
                'active_referrals': active_referrals,
                'paid_referrals': paid_referrals,
                'total_earnings': total_earnings,
                'created_at': reference.created_at.isoformat(),
                'updated_at': reference.updated_at.isoformat()
            }
            
        # Get user's used promo code data if they used one
        used_promo_data = None
        if user.promo_code:
            referring_user = User.query.join(Reference).filter(
                Reference.code == user.promo_code
            ).first()
            
            if referring_user:
                used_promo_data = {
                    'code': user.promo_code,
                    'referrer_name': referring_user.full_name,
                    'is_paid': user.is_reference_paid
                }
            
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
                },
                'referral': referral_data,  # Will be None if user has no reference code
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Error fetching user data: {str(e)}", exc_info=True)
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