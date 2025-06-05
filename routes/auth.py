from flask import Blueprint, request, jsonify
from extensions import db, bcrypt
from models.user import User
from schemas import UserRegistrationSchema, LoginSchema
from sqlalchemy.exc import IntegrityError
from marshmallow import ValidationError
from flask_jwt_extended import create_access_token

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    schema = UserRegistrationSchema()
    try:
        # Validate request data
        data = schema.load(request.get_json())
        
        # Check if phone number already exists
        existing_user = User.query.filter_by(phone=data['phone']).first()
        # print(existing_user.is_active)
        if existing_user:
            if existing_user.is_active == True :
                return jsonify({
                    'status': 'error',
                    'message': 'Phone number already registered with an active account'
                }), 409
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Phone number already registered but account is inactive'
                }), 409
        
        # Create new user
        new_user = User(
            full_name=data['full_name'],
            phone=data['phone'],
            password=data['password'],
            url=data['url'],
            promo_code=data['promo_code']
        )
        
        # Save to database
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'User registered successfully',
            'data': {
                'id': new_user.id,
                'full_name': new_user.full_name,
                'phone': new_user.phone,
                'url': new_user.url,
                'is_active': new_user.is_active,
                'promo_code': new_user.promo_code
            }
        }), 201
        
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': 'Validation error',
            'errors': e.messages
        }), 400
        
    except IntegrityError as e:
        db.session.rollback()
        # Check if the error is due to duplicate phone number
        if 'duplicate key value violates unique constraint' in str(e):
            return jsonify({
                'status': 'error',
                'message': 'Phone number already registered'
            }), 409
        return jsonify({
            'status': 'error',
            'message': 'Database error occurred'
        }), 500
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    schema = LoginSchema()
    try:
        # Validate request data
        data = schema.load(request.get_json())
        
        # Find user by phone
        user = User.query.filter_by(phone=data['phone']).first()
        
        # Check if user exists and is active
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'Invalid phone number or password'
            }), 401
            
        if not user.is_active:
            return jsonify({
                'status': 'error',
                'message': 'Account is inactive'
            }), 401
            
        # Verify password
        if not bcrypt.check_password_hash(user.password, data['password']):
            return jsonify({
                'status': 'error',
                'message': 'Invalid phone number or password'
            }), 401
            
        # Generate access token
        access_token = create_access_token(
            identity=str(user.id),  # Convert user.id to string
            additional_claims={
                'phone': user.phone,
                'full_name': user.full_name
            }
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Login successful',
            'data': {
                'access_token': access_token,
                'user': {
                    'id': user.id,
                    'full_name': user.full_name,
                    'phone': user.phone,
                    'url': user.url
                }
            }
        }), 200
        
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': 'Validation error',
            'errors': e.messages
        }), 400
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 