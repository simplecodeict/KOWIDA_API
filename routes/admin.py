from flask import Blueprint, jsonify, request
from models.user import User
from models.reference import Reference
from models.bank_details import BankDetails
from models.transaction import Transaction
from models.transaction_details import TransactionDetails
from models.base_amount import BaseAmount
from extensions import db
from marshmallow import ValidationError
from datetime import datetime
from sqlalchemy import and_, distinct, or_
from schemas import UserPhoneSchema, UserFilterSchema, ReferenceCodeSchema, UserRegistrationSchema, AdminRegistrationSchema, MakeTransactionSchema, TransactionFilterSchema
from flask_jwt_extended import jwt_required
from extensions import colombo_tz, upload_file_to_s3

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/activate-user', methods=['POST'])
@jwt_required()
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
        user.updated_at = datetime.now(colombo_tz).replace(tzinfo=None)
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
@jwt_required()
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
        user.updated_at = datetime.now(colombo_tz).replace(tzinfo=None)
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
@jwt_required()
def get_all_users():
    schema = UserFilterSchema()
    try:
        # Validate query parameters - empty dict if no parameters provided
        params = schema.load(request.args or {})
        
        # Base query for users with role = 'user' and their relationships
        query = User.query.filter(User.role == 'user')\
            .outerjoin(BankDetails)
        
        # Apply is_active filter if provided
        if 'is_active' in params and params['is_active'] is not None:
            query = query.filter(User.is_active == params['is_active'])
            
        # Apply promo_code filter if provided
        if params.get('promo_code'):
            query = query.filter(User.promo_code == params['promo_code'])
            
        # Apply reference code filter only if provided
        if params.get('reference_code'):
            query = query.filter(User.promo_code == params['reference_code'])
            
        # Apply phone filter if provided
        if params.get('phone'):
            query = query.filter(User.phone.like(f'%{params["phone"]}%'))
            
        # Apply payment_method filter if provided
        if params.get('payment_method'):
            query = query.filter(User.payment_method == params['payment_method'])
            
        # Apply pagination
        page = params.get('page', 1)
        per_page = params.get('per_page', 10)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Prepare response data
        users_data = []
        for user in pagination.items:
            # Get reference data based on promo_code
            reference_data = []
            if user.promo_code:
                reference = Reference.query.filter_by(code=user.promo_code).first()
                if reference:
                    reference_data = [{
                        'code': reference.code,
                        'discount_amount': float(reference.discount_amount) if reference.discount_amount else None,
                        'received_amount': float(reference.received_amount) if reference.received_amount else None,
                        'created_at': reference.created_at.isoformat()
                    }]
            
            user_data = {
                'id': user.id,
                'full_name': user.full_name,
                'phone': user.phone,
                'role': user.role,
                'payment_method': user.payment_method,
                'url': user.url,
                'promo_code': user.promo_code,
                'paid_amount': float(user.paid_amount),
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
                'references': reference_data
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

@admin_bp.route('/requests', methods=['GET'])
@jwt_required()
def get_all_requests():
    schema = UserFilterSchema()
    try:
        # Validate query parameters - empty dict if no parameters provided
        params = schema.load(request.args or {})
        
        # Base query for inactive users with their relationships
        query = User.query.filter_by(is_active=False, role='user')\
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
                'payment_method': user.payment_method,
                'is_reference_paid': user.is_reference_paid,
                'paid_amount': float(user.paid_amount),
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
@jwt_required()
def get_reference_owners():
    schema = UserFilterSchema()
    try:
        # Validate query parameters - empty dict if no parameters provided
        params = schema.load(request.args or {})
        
        # Base query for active users with role = 'referer'
        query = User.query\
            .filter(User.is_active == True)\
            .filter(User.role == 'referer')\
            .outerjoin(Reference, User.phone == Reference.phone)\
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
                'role': user.role,
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
                } if reference else None,
                'has_reference': reference is not None
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

@admin_bp.route('/reference-owners/<reference_code>', methods=['GET'])
@jwt_required()
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
            
        # Query users who used this reference code (ALL users regardless of status)
        query = User.query\
            .filter(User.promo_code == params['reference_code'])\
            .outerjoin(BankDetails)
            
        # Apply date range filter if provided
        if params.get('start_date'):
            query = query.filter(User.created_at >= datetime.combine(params['start_date'], datetime.min.time()))
        if params.get('end_date'):
            query = query.filter(User.created_at <= datetime.combine(params['end_date'], datetime.max.time()))
            
        # Apply is_reference_paid filter if provided
        if 'is_reference_paid' in params and params['is_reference_paid'] is not None:
            query = query.filter(User.is_reference_paid == params['is_reference_paid'])
            
        # Apply is_active filter if provided
        if 'is_active' in params and params['is_active'] is not None:
            query = query.filter(User.is_active == params['is_active'])
            
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
                'paid_amount': float(user.paid_amount),
                'payment_method': user.payment_method,
                'is_active': user.is_active,
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


@admin_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_stats():
    try:
        # Count active users (role = 'user' and is_active = true)
        active_users_count = User.query.filter(
            User.role == 'user',
            User.is_active == True
        ).count()
        
        # Count requests (role = 'user' and is_active = false)
        requests_count = User.query.filter(
            User.role == 'user',
            User.is_active == False
        ).count()
        
        # Count reference owners (role = 'referer' and is_active = true)
        reference_owners_count = User.query.filter(
            User.role == 'referer',
            User.is_active == True
        ).count()
        
        # Count reference payment pending (role = 'user', is_active = true, is_reference_paid = false)
        reference_payment_pending_count = User.query.filter(
            User.role == 'user',
            User.is_active == True,
            User.is_reference_paid == False
        ).count()
        
        # Calculate total income (sum of paid_amount for active users with role = 'user')
        from sqlalchemy import func
        total_income_result = db.session.query(func.sum(User.paid_amount)).filter(
            User.role == 'user',
            User.is_active == True
        ).scalar()
        total_income = float(total_income_result) if total_income_result else 0.0
        
        # Calculate total pending amount (sum of paid_amount for inactive users with role = 'user')
        total_pending_result = db.session.query(func.sum(User.paid_amount)).filter(
            User.role == 'user',
            User.is_active == False
        ).scalar()
        total_pending_amount = float(total_pending_result) if total_pending_result else 0.0
        
        return jsonify({
            'status': 'success',
            'data': {
                'active_users': active_users_count,
                'requests': requests_count,
                'reference_owners': reference_owners_count,
                'reference_payment_pending': reference_payment_pending_count,
                'total_income': total_income,
                'total_pending_amount': total_pending_amount
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
            # Create user with default URL and role set as 'referer'
            paid_amount = float(user_data.get('paid_amount', 0)) if user_data.get('paid_amount') else 0
            
            user = User(
                full_name=user_data['full_name'],
                phone=user_data['phone'],
                password=user_data['password'],
                url="",
                role='referer',  # Always set as referer for admin-register
                paid_amount=paid_amount,
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
                        'role': saved_user.role,
                        'is_active': saved_user.is_active,
                        'paid_amount': float(saved_user.paid_amount),
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


@admin_bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_all_transactions():
    schema = TransactionFilterSchema()
    try:
        # Validate query parameters
        params = schema.load(request.args or {})
        
        # Base query for transactions with reference owner data
        query = Transaction.query.join(User, Transaction.user_id == User.id)
        
        # Apply reference_code filter if provided
        if params.get('reference_code'):
            query = query.filter(Transaction.reference_code == params['reference_code'])
            
        # Apply user_id filter if provided
        if params.get('user_id'):
            query = query.filter(Transaction.user_id == params['user_id'])
            
        # Apply pagination
        page = params.get('page', 1)
        per_page = params.get('per_page', 10)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Prepare response data
        transactions_data = []
        for transaction in pagination.items:
            # Get reference owner data
            reference_owner = User.query.get(transaction.user_id)
            
            # Get transaction details count
            transaction_details_count = len(transaction.transaction_details)
            
            transaction_data = {
                'id': transaction.id,
                'total_reference_count': transaction.total_reference_count,
                'total_reference_amount': float(transaction.total_reference_amount),
                'reference_code': transaction.reference_code,
                'discount_amount': float(transaction.discount_amount),
                'received_amount': float(transaction.received_amount),
                'receipt_url': transaction.receipt_url,
                'status': transaction.status,
                'created_at': transaction.created_at.isoformat(),
                'updated_at': transaction.updated_at.isoformat(),
                'reference_owner': {
                    'id': reference_owner.id,
                    'full_name': reference_owner.full_name,
                    'phone': reference_owner.phone,
                    'is_active': reference_owner.is_active
                } if reference_owner else None,
                'transaction_details_count': transaction_details_count
            }
            transactions_data.append(transaction_data)
            
        return jsonify({
            'status': 'success',
            'data': {
                'transactions': transactions_data,
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


@admin_bp.route('/transactions/<transaction_id>', methods=['GET'])
@jwt_required()
def get_transaction_details(transaction_id):
    try:
        # Get transaction by ID
        transaction = Transaction.query.filter_by(id=transaction_id).first()
        if not transaction:
            return jsonify({
                'status': 'error',
                'message': 'Transaction not found'
            }), 404
        
        # Get reference owner data
        reference_owner = User.query.get(transaction.user_id)
        
        # Get transaction details with user information
        transaction_details_data = []
        for detail in transaction.transaction_details:
            user = User.query.get(detail.user_id)
            transaction_details_data.append({
                'id': detail.id,
                'user_id': detail.user_id,
                'user_name': user.full_name if user else None,
                'user_phone': user.phone if user else None,
                'user_email': getattr(user, 'email', None) if user else None,
                'is_active': user.is_active if user else None,
                'is_reference_paid': user.is_reference_paid if user else None,
                'paid_amount': float(user.paid_amount) if user else None,
                'created_at': detail.created_at.isoformat(),
                'updated_at': detail.updated_at.isoformat()
            })
        
        # Prepare transaction data
        transaction_data = {
            'id': transaction.id,
            'total_reference_count': transaction.total_reference_count,
            'total_reference_amount': float(transaction.total_reference_amount),
            'reference_code': transaction.reference_code,
            'discount_amount': float(transaction.discount_amount),
            'received_amount': float(transaction.received_amount),
            'receipt_url': transaction.receipt_url,
            'status': transaction.status,
            'created_at': transaction.created_at.isoformat(),
            'updated_at': transaction.updated_at.isoformat(),
            'reference_owner': {
                'id': reference_owner.id,
                'full_name': reference_owner.full_name,
                'phone': reference_owner.phone,
                'is_active': reference_owner.is_active
            } if reference_owner else None,
            'transaction_details': transaction_details_data,
        }
        
        return jsonify({
            'status': 'success',
            'data': transaction_data
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@admin_bp.route('/reference-owners/<int:user_id>/transactions', methods=['GET'])
@jwt_required()
def get_transactions_by_reference_owner(user_id):
    try:
        # Check if reference owner exists
        reference_owner = User.query.get(user_id)
        if not reference_owner:
            return jsonify({
                'status': 'error',
                'message': 'Reference owner not found'
            }), 404
        
        # Get all transactions for this reference owner
        transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).all()
        
        # Prepare response data
        transactions_data = []
        total_reference_count = 0
        total_reference_amount = 0.0
        
        for transaction in transactions:
            # Get transaction details count
            transaction_details_count = len(transaction.transaction_details)
            
            # Get users in this transaction
            users_in_transaction = []
            for detail in transaction.transaction_details:
                user = User.query.get(detail.user_id)
                if user:
                    users_in_transaction.append({
                        'id': user.id,
                        'full_name': user.full_name,
                        'phone': user.phone,
                        'is_active': user.is_active,
                        'is_reference_paid': user.is_reference_paid,
                        'paid_amount': float(user.paid_amount)
                    })
            
            transaction_data = {
                'id': transaction.id,
                'total_reference_count': transaction.total_reference_count,
                'total_reference_amount': float(transaction.total_reference_amount),
                'reference_code': transaction.reference_code,
                'discount_amount': float(transaction.discount_amount),
                'received_amount': float(transaction.received_amount),
                'receipt_url': transaction.receipt_url,
                'status': transaction.status,
                'created_at': transaction.created_at.isoformat(),
                'updated_at': transaction.updated_at.isoformat(),
                'transaction_details_count': transaction_details_count,
                'users': users_in_transaction
            }
            transactions_data.append(transaction_data)
            
            # Calculate totals
            total_reference_count += transaction.total_reference_count
            total_reference_amount += float(transaction.total_reference_amount)
        
        # Prepare reference owner data
        reference_owner_data = {
            'id': reference_owner.id,
            'full_name': reference_owner.full_name,
            'phone': reference_owner.phone,
            'is_active': reference_owner.is_active,
            'role': reference_owner.role
        }
        
        return jsonify({
            'status': 'success',
            'data': {
                'reference_owner': reference_owner_data,
                'transactions': transactions_data,
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@admin_bp.route('/make-transaction', methods=['POST'])
@jwt_required()
def make_transaction():
    schema = MakeTransactionSchema()
    try:
        s3_url = None
        
        # Check if receipt is present in request (required)
        if 'receipt' not in request.files:
            return jsonify({
                'status': 'error',
                'message': 'Receipt file is required',
                'error_code': 'RECEIPT_REQUIRED'
            }), 400
            
        receipt_file = request.files['receipt']
        
        # Validate file
        if receipt_file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No file selected',
                'error_code': 'NO_FILE_SELECTED'
            }), 400

        # Validate file type
        allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg'}
        file_extension = receipt_file.filename.rsplit('.', 1)[1].lower() if '.' in receipt_file.filename else ''
        
        if not file_extension or file_extension not in allowed_extensions:
            return jsonify({
                'status': 'error',
                'message': f'Invalid file type. Allowed types: {", ".join(allowed_extensions)}',
                'error_code': 'INVALID_FILE_TYPE'
            }), 400

        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB in bytes
        file_data = receipt_file.read()
        if len(file_data) > max_size:
            return jsonify({
                'status': 'error',
                'message': 'File size exceeds maximum limit of 5MB',
                'error_code': 'FILE_TOO_LARGE'
            }), 400

        # Upload to S3
        try:
            s3_url = upload_file_to_s3(file_data, receipt_file.filename)
        except ValueError as e:
            return jsonify({
                'status': 'error',
                'message': str(e),
                'error_code': 'S3_UPLOAD_ERROR'
            }), 500
        except Exception as e:
            logger.error(f"Unexpected error uploading receipt: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Failed to upload receipt. Please try again.',
                'error_code': 'UPLOAD_ERROR'
            }), 500

        # Validate request data
        try:
            data = schema.load(request.form)
        except ValidationError as e:
            return jsonify({
                'status': 'error',
                'message': 'Validation error',
                'errors': e.messages,
                'error_code': 'VALIDATION_ERROR'
            }), 400
        
        # Start database transaction
        db.session.begin()
        
        try:
            # Get base amount from base_amount table
            base_amount = BaseAmount.query.first()
            if not base_amount:
                db.session.rollback()
                return jsonify({
                    'status': 'error',
                    'message': 'Base amount not configured'
                }), 400
            
            # Get reference data using reference_code
            reference = Reference.query.filter_by(code=data['reference_code']).first()
            if not reference:
                db.session.rollback()
                return jsonify({
                    'status': 'error',
                    'message': 'Reference code not found'
                }), 404
            
            # Get referrer user (user_id from payload)
            referrer_user = User.query.get(data['user_id'])
            if not referrer_user:
                db.session.rollback()
                return jsonify({
                    'status': 'error',
                    'message': 'Referrer user not found'
                }), 404
            
            # Get users who used this reference code (active and unpaid)
            eligible_users = User.query.filter(
                User.promo_code == data['reference_code'],
                User.is_active == True,
                User.is_reference_paid == False,
                User.role == 'user'
            ).all()
            
            if not eligible_users:
                db.session.rollback()
                return jsonify({
                    'status': 'error',
                    'message': 'No eligible users found for this reference code'
                }), 400
            
            # Calculate total reference count
            total_reference_count = len(eligible_users)
            
            # Create transaction
            transaction = Transaction(
                total_reference_count=total_reference_count,
                total_reference_amount=data['total_reference_amount'],
                user_id=data['user_id'],
                reference_code=data['reference_code'],
                discount_amount=reference.discount_amount,
                received_amount=reference.received_amount,
                receipt_url=s3_url,  # Store S3 URL
                status=False  # Initially false, will be set to true at the end
            )
            
            db.session.add(transaction)
            db.session.flush()  # Get the transaction ID
            
            # Create transaction details for each eligible user
            transaction_details_list = []
            for user in eligible_users:
                transaction_detail = TransactionDetails(
                    user_id=user.id,
                    transaction_id=transaction.id
                )
                db.session.add(transaction_detail)
                transaction_details_list.append(transaction_detail)
                
                # Update user's reference payment status
                user.is_reference_paid = True
                user.updated_at = datetime.now(colombo_tz).replace(tzinfo=None)
            
            # Set transaction status to true (completed)
            transaction.status = True
            
            # Commit all changes
            db.session.commit()
            
            # Prepare response data
            transaction_details_data = []
            for detail in transaction_details_list:
                user = User.query.get(detail.user_id)
                transaction_details_data.append({
                    'id': detail.id,
                    'user_id': detail.user_id,
                    'user_name': user.full_name if user else None,
                    'user_phone': user.phone if user else None,
                    'transaction_id': detail.transaction_id,
                    'created_at': detail.created_at.isoformat()
                })
            
            return jsonify({
                'status': 'success',
                'message': 'Transaction created successfully',
                'data': {
                    'transaction': {
                        'id': transaction.id,
                        'total_reference_count': transaction.total_reference_count,
                        'total_reference_amount': float(transaction.total_reference_amount),
                        'user_id': transaction.user_id,
                        'referrer_name': referrer_user.full_name,
                        'reference_code': transaction.reference_code,
                        'discount_amount': float(transaction.discount_amount),
                        'received_amount': float(transaction.received_amount),
                        'receipt_url': transaction.receipt_url,
                        'status': transaction.status,
                        'created_at': transaction.created_at.isoformat()
                    },
                    'base_amount': float(base_amount.amount),
                    'transaction_details': transaction_details_data,
                    'summary': {
                        'total_users_processed': total_reference_count,
                        'total_amount_paid': float(transaction.total_reference_amount)
                    }
                }
            }), 201
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error creating transaction: {str(e)}'
            }), 500
            
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