from flask import Blueprint, request, jsonify
from extensions import db, bcrypt
from models.user import User
from schemas import UserRegistrationSchema, LoginSchema
from sqlalchemy.exc import IntegrityError
from marshmallow import ValidationError
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import datetime
import logging

auth_bp = Blueprint('auth', __name__)

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
            access_token = create_access_token(identity=new_user.id)
            
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
        # Validate request data
        data = schema.load(request.get_json())
        
        # Find user by phone
        user = User.query.filter_by(phone=data['phone']).first()
        
        # Check if user exists and verify password
        if not user or not user.check_password(data['password']):
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
        access_token = create_access_token(identity=user.id)
        
        return jsonify({
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
        }), 200
        
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': 'Validation error',
            'errors': e.messages,
            'error_code': 'VALIDATION_ERROR'
        }), 400
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while processing login',
            'error_code': 'LOGIN_ERROR'
        }), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    try:
        current_user_id = get_jwt_identity()
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
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while fetching user data',
            'error_code': 'USER_FETCH_ERROR'
        }), 500 