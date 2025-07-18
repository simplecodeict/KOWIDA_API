from flask import Blueprint, jsonify, request
from models.user import User
from models.reference import Reference
from models.bank_details import BankDetails
from extensions import db
from marshmallow import ValidationError
from datetime import datetime
from sqlalchemy import and_, distinct, or_
from schemas import UserPhoneSchema, UserFilterSchema, ReferenceCodeSchema, UserRegistrationSchema, AdminRegistrationSchema

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

@admin_bp.route('/users', methods=['GET'])
def get_all_users():
    schema = UserFilterSchema()
    try:
        # Validate query parameters - empty dict if no parameters provided
        params = schema.load(request.args or {})
        
        # Base query for users with their relationships
        query = User.query.filter_by()\
            .outerjoin(BankDetails)\
            .outerjoin(Reference, User.phone == Reference.phone)
        
        # Apply is_active filter if provided
        if 'is_active' in params and params['is_active'] is not None:
            query = query.filter(User.is_active == params['is_active'])
            
        # Apply promo_code filter if provided
        if params.get('promo_code'):
            query = query.filter(User.promo_code == params['promo_code'])
            
        # Apply reference code filter only if provided
        if params.get('reference_code'):
            query = query.filter(Reference.code == params['reference_code'])
            
        # Apply phone filter if provided
        if params.get('phone'):
            query = query.filter(User.phone.like(f'%{params["phone"]}%'))
            
        # Apply pagination
        page = params.get('page', 1)
        per_page = params.get('per_page', 10)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Prepare response data
        users_data = []
        for user in pagination.items:
            user_data = {
                'id': user.id,
                'full_name': user.full_name,
                'phone': user.phone,
                'url': user.url,
                'promo_code': user.promo_code,
                'is_reference_paid': user.is_reference_paid,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat(),
                'bank_details': [{
                    'bank_name': bd.bank_name,
                    'owner_name': bd.name,
                    'account_number': bd.account_number,
                    'branch_name': bd.branch
                } for bd in user.bank_details],
                'references': [{
                    'code': ref.code,
                    'discount_amount': float(ref.discount_amount) if ref.discount_amount else None,
                    'received_amount': float(ref.received_amount) if ref.received_amount else None,
                    'created_at': ref.created_at.isoformat()
                } for ref in user.references]
            }
            users_data.append(user_data)
            
        return jsonify({
            'status': 'success',
            'data': {
                'users': users_data,
                'pagination': {
                    'total_items': pagination.total,
                    'total_pages': pagination.pages,
                    'current_page': page,
                    'per_page': per_page,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
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

@admin_bp.route('/inactive-users', methods=['GET'])
def get_inactive_users():
    schema = UserFilterSchema()
    try:
        # Validate query parameters - empty dict if no parameters provided
        params = schema.load(request.args or {})
        
        # Base query for inactive users with their relationships
        query = User.query.filter_by(is_active=False)\
            .outerjoin(BankDetails)\
            .outerjoin(Reference, User.phone == Reference.phone)
        
        # Apply date range filter only if dates are provided
        if params.get('start_date'):
            query = query.filter(User.created_at >= datetime.combine(params['start_date'], datetime.min.time()))
        if params.get('end_date'):
            query = query.filter(User.created_at <= datetime.combine(params['end_date'], datetime.max.time()))
            
        # Apply reference code filter only if provided
        if params.get('reference_code'):
            query = query.filter(Reference.code == params['reference_code'])
            
        # Apply phone filter if provided
        if params.get('phone'):
            query = query.filter(User.phone.like(f'%{params["phone"]}%'))
            
        # Apply pagination
        page = params.get('page', 1)
        per_page = params.get('per_page', 10)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Prepare response data
        users_data = []
        for user in pagination.items:
            user_data = {
                'id': user.id,
                'full_name': user.full_name,
                'phone': user.phone,
                'url': user.url,
                'promo_code': user.promo_code,
                'is_reference_paid': user.is_reference_paid,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat(),
                'bank_details': [{
                    'bank_name': bd.bank_name,
                    'owner_name': bd.name,
                    'account_number': bd.account_number,
                    'branch_name': bd.branch
                } for bd in user.bank_details],
                'references': [{
                    'code': ref.code,
                    'discount_amount': float(ref.discount_amount) if ref.discount_amount else 0,
                    'received_amount': float(ref.received_amount) if ref.received_amount else 0,
                    'created_at': ref.created_at.isoformat()
                } for ref in user.references]
            }
            users_data.append(user_data)
            
        return jsonify({
            'status': 'success',
            'data': {
                'users': users_data,
                'pagination': {
                    'total_items': pagination.total,
                    'total_pages': pagination.pages,
                    'current_page': page,
                    'per_page': per_page,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
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

@admin_bp.route('/reference-owners', methods=['GET'])
def get_reference_owners():
    schema = UserFilterSchema()
    try:
        # Validate query parameters - empty dict if no parameters provided
        params = schema.load(request.args or {})
        
        # Base query for active users who have references
        query = User.query\
            .filter(User.is_active == True)\
            .join(Reference, User.phone == Reference.phone)\
            .outerjoin(BankDetails)\
            .distinct()
            
        # Apply reference code filter only if provided
        if params.get('reference_code'):
            query = query.filter(Reference.code == params['reference_code'])
            
        # Apply phone filter if provided
        if params.get('phone'):
            query = query.filter(User.phone.like(f'%{params["phone"]}%'))
            
        # Apply pagination
        page = params.get('page', 1)
        per_page = params.get('per_page', 10)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Prepare response data
        owners_data = []
        for user in pagination.items:
            # Get the user's reference and bank details
            reference = user.references[0] if user.references else None
            bank_detail = user.bank_details[0] if user.bank_details else None
            
            owner_data = {
                'id': user.id,
                'full_name': user.full_name,
                'phone': user.phone,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat(),
                'bank_details': {
                    'bank_name': bank_detail.bank_name if bank_detail else None,
                    'owner_name': bank_detail.name if bank_detail else None,
                    'account_number': bank_detail.account_number if bank_detail else None,
                    'branch_name': bank_detail.branch if bank_detail else None
                } if bank_detail else None,
                'reference_details': {
                    'promo_code': reference.code if reference else None,
                    'discount_amount': float(reference.discount_amount) if reference and reference.discount_amount else 0,
                    'received_amount': float(reference.received_amount) if reference and reference.received_amount else 0,
                    'created_at': reference.created_at.isoformat() if reference else None
                } if reference else None
            }
            owners_data.append(owner_data)
            
        return jsonify({
            'status': 'success',
            'data': {
                'reference_owners': owners_data,
                'pagination': {
                    'total_items': pagination.total,
                    'total_pages': pagination.pages,
                    'current_page': page,
                    'per_page': per_page,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
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

@admin_bp.route('/reference-users/<reference_code>', methods=['GET'])
def get_users_by_reference(reference_code):
    schema = ReferenceCodeSchema()
    try:
        # Validate query parameters for pagination
        params = schema.load({'reference_code': reference_code, **request.args})
        
        # First find the reference owner
        reference_owner = User.query\
            .join(Reference, User.phone == Reference.phone)\
            .filter(Reference.code == params['reference_code'])\
            .first()
            
        if not reference_owner:
            return jsonify({
                'status': 'error',
                'message': 'Reference code not found'
            }), 404
            
        # Query users who used this reference code (only active users)
        query = User.query\
            .filter(
                User.promo_code == params['reference_code'],
                User.is_active == True  # Only active users
            )\
            .outerjoin(BankDetails)
            
        # Apply date range filter if provided
        if params.get('start_date'):
            query = query.filter(User.created_at >= datetime.combine(params['start_date'], datetime.min.time()))
        if params.get('end_date'):
            query = query.filter(User.created_at <= datetime.combine(params['end_date'], datetime.max.time()))
            
        # Apply is_reference_paid filter if provided
        if 'is_reference_paid' in params and params['is_reference_paid'] is not None:
            query = query.filter(User.is_reference_paid == params['is_reference_paid'])
            
        # Apply pagination
        page = params.get('page', 1)
        per_page = params.get('per_page', 10)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Prepare response data
        users_data = []
        for user in pagination.items:
            user_data = {
                'id': user.id,
                'full_name': user.full_name,
                'phone': user.phone,
                'is_reference_paid': user.is_reference_paid,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat(),
                'bank_details': [{
                    'bank_name': bd.bank_name,
                    'owner_name': bd.name,
                    'account_number': bd.account_number,
                    'branch_name': bd.branch
                } for bd in user.bank_details]
            }
            users_data.append(user_data)
            
        # Get reference details
        reference = Reference.query.filter_by(code=params['reference_code']).first()
        reference_data = {
            'code': reference.code,
            'discount_amount': float(reference.discount_amount) if reference.discount_amount else 0,
            'received_amount': float(reference.received_amount) if reference.received_amount else 0,
            'created_at': reference.created_at.isoformat(),
            'owner': {
                'id': reference_owner.id,
                'full_name': reference_owner.full_name,
                'phone': reference_owner.phone,
                'is_active': reference_owner.is_active
            }
        }
            
        return jsonify({
            'status': 'success',
            'data': {
                'reference': reference_data,
                'registered_users': users_data,
                'summary': {
                    'total_users': pagination.total,
                    'reference_paid_users': sum(1 for user in users_data if user['is_reference_paid']),
                    'reference_unpaid_users': sum(1 for user in users_data if not user['is_reference_paid'])
                },
                'pagination': {
                    'total_items': pagination.total,
                    'total_pages': pagination.pages,
                    'current_page': page,
                    'per_page': per_page,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
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

@admin_bp.route('/all-users', methods=['GET'])
def get_all_users_complete():
    try:
        # Query all users without any conditions and explicitly include both active and inactive
        users = User.query\
            .filter(or_(User.is_active == True, User.is_active == False))\
            .outerjoin(BankDetails)\
            .outerjoin(Reference, User.phone == Reference.phone)\
            .all()
        
        # Prepare response data
        users_data = []
        for user in users:
            # Get the user's reference and bank details
            reference = user.references[0] if user.references else None
            bank_detail = user.bank_details[0] if user.bank_details else None
            
            user_data = {
                'id': user.id,
                'full_name': user.full_name,
                'phone': user.phone,
                'url': user.url,
                'promo_code': user.promo_code,
                'is_active': user.is_active,
                'is_reference_paid': user.is_reference_paid,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat(),
                'bank_details': {
                    'bank_name': bank_detail.bank_name if bank_detail else None,
                    'owner_name': bank_detail.name if bank_detail else None,
                    'account_number': bank_detail.account_number if bank_detail else None,
                    'branch_name': bank_detail.branch if bank_detail else None
                } if bank_detail else None,
                'reference_details': {
                    'promo_code': reference.code if reference else None,
                    'discount_amount': float(reference.discount_amount) if reference and reference.discount_amount else 0,
                    'received_amount': float(reference.received_amount) if reference and reference.received_amount else 0,
                    'created_at': reference.created_at.isoformat() if reference else None
                } if reference else None
            }
            users_data.append(user_data)
            
        return jsonify({
            'status': 'success',
            'data': {
                'users': users_data,
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@admin_bp.route('/admin-register', methods=['POST'])
def admin_register_user():
    schema = AdminRegistrationSchema()
    try:
        # Validate request data
        data = schema.load(request.get_json())
        
        # Extract data
        user_data = data['user_data']
        bank_details_data = data['bank_details']
        reference_data = data['reference_data']
        
        # Start transaction
        db.session.begin()
        
        try:
            # Create user with default URL
            user = User(
                full_name=user_data['full_name'],
                phone=user_data['phone'],
                password=user_data['password'],
                url="",
                # promo_code=reference_data['code']
            )
            # Set is_active after creation
            user.is_active = True
            user.is_reference_paid = True
            
            db.session.add(user)
            
            try:
                db.session.flush()  # Try to flush user to check for any issues
            except Exception as e:
                db.session.rollback()
                print(f"Error creating user: {str(e)}")  # Debug log
                return jsonify({
                    'status': 'error',
                    'message': f'Error creating user: {str(e)}'
                }), 500
            
            # Create bank details
            bank_details = BankDetails(
                user_id=user.id,
                bank_name=bank_details_data['bank_name'],
                name=bank_details_data['name'],
                account_number=bank_details_data['account_number'],
                branch=bank_details_data['branch']
            )
            db.session.add(bank_details)
            
            try:
                db.session.flush()  # Try to flush bank details to check for any issues
            except Exception as e:
                db.session.rollback()
                print(f"Error creating bank details: {str(e)}")  # Debug log
                return jsonify({
                    'status': 'error',
                    'message': f'Error creating bank details: {str(e)}'
                }), 500
            
            # Create reference with provided amounts
            reference = Reference(
                code=reference_data['code'],
                phone=user.phone,
                discount_amount=reference_data['discount_amount'],
                received_amount=reference_data['received_amount']
            )
            db.session.add(reference)
            
            try:
                # Final commit of all changes
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"Error in final commit: {str(e)}")  # Debug log
                return jsonify({
                    'status': 'error',
                    'message': f'Error saving data: {str(e)}'
                }), 500
            
            # Verify the data was saved by querying it back
            saved_user = User.query.get(user.id)
            if not saved_user:
                return jsonify({
                    'status': 'error',
                    'message': 'User was not saved properly'
                }), 500
            
            return jsonify({
                'status': 'success',
                'message': 'User registered successfully',
                'data': {
                    'user': {
                        'id': saved_user.id,
                        'full_name': saved_user.full_name,
                        'phone': saved_user.phone,
                        'is_active': saved_user.is_active,
                        'created_at': saved_user.created_at.isoformat()
                    },
                    'bank_details': {
                        'bank_name': bank_details.bank_name,
                        'owner_name': bank_details.name,
                        'account_number': bank_details.account_number,
                        'branch_name': bank_details.branch
                    },
                    'reference': {
                        'code': reference.code,
                        'discount_amount': float(reference.discount_amount),
                        'received_amount': float(reference.received_amount)
                    }
                }
            }), 201
            
        except Exception as e:
            db.session.rollback()
            print(f"Transaction error: {str(e)}")  # Debug log
            return jsonify({
                'status': 'error',
                'message': f'Transaction error: {str(e)}'
            }), 500
            
    except ValidationError as e:
        print(f"Validation error: {str(e)}")  # Debug log
        return jsonify({
            'status': 'error',
            'message': 'Validation error',
            'errors': e.messages
        }), 400
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}")  # Debug log
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 