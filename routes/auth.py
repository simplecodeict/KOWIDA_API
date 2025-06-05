from flask import Blueprint, request, jsonify
from extensions import db
from models.user import User
from schemas import UserRegistrationSchema
from sqlalchemy.exc import IntegrityError
from marshmallow import ValidationError

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
            url=data['url']
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
                'is_active': new_user.is_active
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