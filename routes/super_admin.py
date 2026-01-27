from flask import Blueprint, request, jsonify
from extensions import db, upload_file_to_s3, bcrypt
from models.user import User
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from schemas import UserRegistrationSchema, LoginSchema
from marshmallow import ValidationError
from flask_jwt_extended import jwt_required
from routes.auth import generate_token
import logging

logger = logging.getLogger(__name__)

super_admin_bp = Blueprint('super_admin', __name__)

# Global constant for reference commission reduction rate (20%)
REFERENCE_COMMISSION_RATE = 0.20  # 20%


@super_admin_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard():
    """
    Get dashboard statistics for super admin
    Returns comprehensive financial and user statistics
    """
    try:
        # Helper function to get sum or 0 if None
        def get_sum_or_zero(query_result):
            return float(query_result) if query_result is not None else 0.0
        
        # Helper function to get count or 0
        def get_count_or_zero(query_result):
            return int(query_result) if query_result is not None else 0
        
        # ========== INCOME CALCULATIONS ==========
        
        # 1. direct_income: Sum of paid_amount where status='register' AND promo_code=null AND role='user'
        direct_income_query = db.session.query(func.sum(User.paid_amount)).filter(
            User.status == 'register',
            User.promo_code.is_(None),
            User.role == 'user'
        ).scalar()
        direct_income = get_sum_or_zero(direct_income_query)
        
        # 2. referenced_income: Sum of (paid_amount * 0.8) where status='register' AND promo_code!=null AND promo_code!='SL001' AND role='user'
        referenced_income_query = db.session.query(
            func.sum(User.paid_amount * (1 - REFERENCE_COMMISSION_RATE))
        ).filter(
            User.status == 'register',
            User.promo_code.isnot(None),
            User.promo_code != 'SL001',
            User.role == 'user'
        ).scalar()
        referenced_income = get_sum_or_zero(referenced_income_query)
        
        # 3. pending_income: Sum of paid_amount where status='pending' AND (promo_code is null OR promo_code!='SL001') AND role='user'
        pending_income_query = db.session.query(func.sum(User.paid_amount)).filter(
            User.status == 'pending',
            or_(User.promo_code.is_(None), User.promo_code != 'SL001'),
            User.role == 'user'
        ).scalar()
        pending_income = get_sum_or_zero(pending_income_query)
        
        # 4. total_income = direct_income + referenced_income
        total_income = direct_income + referenced_income
        
        # 5. kowida_income = total_income * 60%
        kowida_income = total_income * 0.60
        
        # 6. randyll_income = total_income * 40%
        randyll_income = total_income * 0.40
        
        # ========== USER COUNTS ==========
        
        # 7. active_users: Count where status='register' AND promo_code!='SL001' AND role='user'
        active_users_query = User.query.filter(
            User.status == 'register',
            or_(User.promo_code != 'SL001', User.promo_code.is_(None)),
            User.role == 'user'
        ).count()
        active_users = get_count_or_zero(active_users_query)
        
        # 8. pending_users: Count where status='pending' AND (promo_code is null OR promo_code!='SL001') AND role='user'
        pending_users_query = User.query.filter(
            User.status == 'pending',
            or_(User.promo_code.is_(None), User.promo_code != 'SL001'),
            User.role == 'user'
        ).count()
        pending_users = get_count_or_zero(pending_users_query)
        
        # 9. pre_register_users: Count where status='pre-register' AND (promo_code is null OR promo_code!='SL001') AND role='user'
        pre_register_users_query = User.query.filter(
            User.status == 'pre-register',
            or_(User.promo_code.is_(None), User.promo_code != 'SL001'),
            User.role == 'user'
        ).count()
        pre_register_users = get_count_or_zero(pre_register_users_query)
        
        # 10. total_users = active_users + pending_users + pre_register_users
        total_users = active_users + pending_users + pre_register_users
        
        # ========== PAID AMOUNTS ==========
        
        # 11. direct_paid: Sum of paid_amount where status='register' AND promo_code=null AND share_paid=true AND role='user'
        direct_paid_query = db.session.query(func.sum(User.paid_amount)).filter(
            User.status == 'register',
            User.promo_code.is_(None),
            User.share_paid == True,
            User.role == 'user'
        ).scalar()
        direct_paid = get_sum_or_zero(direct_paid_query)
        
        # 12. reference_paid: Sum of (paid_amount * 0.8) where status='register' AND promo_code!=null AND promo_code!='SL001' AND share_paid=true AND role='user'
        reference_paid_query = db.session.query(
            func.sum(User.paid_amount * (1 - REFERENCE_COMMISSION_RATE))
        ).filter(
            User.status == 'register',
            User.promo_code.isnot(None),
            User.promo_code != 'SL001',
            User.share_paid == True,
            User.role == 'user'
        ).scalar()
        reference_paid = get_sum_or_zero(reference_paid_query)
        
        # 13. paid_amount = direct_paid + reference_paid
        paid_amount = direct_paid + reference_paid

        kowida_paid_income = paid_amount * 0.60
        randyll_paid_income = paid_amount * 0.40
        
        # ========== PENDING PAID AMOUNTS ==========
        
        # 14. direct_pending_paid: Sum of paid_amount where status='register' AND promo_code=null AND share_paid=false AND role='user'
        direct_pending_paid_query = db.session.query(func.sum(User.paid_amount)).filter(
            User.status == 'register',
            User.promo_code.is_(None),
            User.share_paid == False,
            User.role == 'user'
        ).scalar()
        direct_pending_paid = get_sum_or_zero(direct_pending_paid_query)
        
        # 15. reference_pending_paid: Sum of (paid_amount * 0.8) where status='register' AND promo_code!=null AND promo_code!='SL001' AND share_paid=false AND role='user'
        reference_pending_paid_query = db.session.query(
            func.sum(User.paid_amount * (1 - REFERENCE_COMMISSION_RATE))
        ).filter(
            User.status == 'register',
            User.promo_code.isnot(None),
            User.promo_code != 'SL001',
            User.share_paid == False,
            User.role == 'user'
        ).scalar()
        reference_pending_paid = get_sum_or_zero(reference_pending_paid_query)
        
        # 16. pending_amount = direct_pending_paid + reference_pending_paid
        pending_amount = direct_pending_paid + reference_pending_paid

        kowida_pending_income = pending_amount * 0.60
        randyll_pending_income = pending_amount * 0.40
        
        # ========== USER COUNTS FOR SHARE PAID ==========
        
        # 17. paid_users: Count where status='register' AND role='user' AND share_paid=true
        paid_users_query = User.query.filter(
            User.status == 'register',
            User.role == 'user',
            User.share_paid == True
        ).count()
        paid_users = get_count_or_zero(paid_users_query)
        
        # 18. pending_users (for share_paid): Count where status='register' AND role='user' AND share_paid=false
        pending_users_share_paid_query = User.query.filter(
            or_(User.promo_code.is_(None), User.promo_code != 'SL001'),
            User.status == 'register',
            User.role == 'user',
            User.share_paid == False
        ).count()
        pending_users_share_paid = get_count_or_zero(pending_users_share_paid_query)
        
        # Build response
        return jsonify({
            'status': 'success',
            'message': 'Dashboard data retrieved successfully',
            'data': {
                'income': {
                    'direct_income': round(direct_income, 2),
                    'referenced_income': round(referenced_income, 2),
                    'pending_income': round(pending_income, 2),
                    'total_income': round(total_income, 2),
                    'kowida_income': round(kowida_income, 2),
                    'randyll_income': round(randyll_income, 2)
                },
                'users': {
                    'active_users': active_users,
                    'pending_users': pending_users,
                    'pre_register_users': pre_register_users,
                    'total_users': total_users
                },
                'paid': {
                    # 'direct_paid': round(direct_paid, 2),
                    # 'reference_paid': round(reference_paid, 2),
                    'paid_amount': round(paid_amount, 2),
                    'kowida_paid_income': round(kowida_paid_income, 2),
                    'randyll_paid_income': round(randyll_paid_income, 2)
                },
                'pending_paid': {
                    # 'direct_pending_paid': round(direct_pending_paid, 2),
                    # 'reference_pending_paid': round(reference_pending_paid, 2),
                    'pending_amount': round(pending_amount, 2),
                    'kowida_pending_income': round(kowida_pending_income, 2),
                    'randyll_pending_income': round(randyll_pending_income, 2)
                },
                'share_paid_users': {
                    'paid_users': paid_users,
                    'pending_users': pending_users_share_paid
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving dashboard data: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while retrieving dashboard data',
            'error': str(e)
        }), 500


@super_admin_bp.route('/requests', methods=['GET'])
@jwt_required()
def get_requests():
    """
    Get pending user requests with pagination
    Returns users where status='pending' AND (promo_code is null OR promo_code!='SL001')
    """
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Fixed to 10 per page as specified
        
        # Validate page number
        if page < 1:
            page = 1
        
        # Base query: users with status='pending' AND (promo_code is null OR promo_code!='SL001')
        requests_query = User.query.filter(
            User.status == 'pending',
            User.role == 'user',
            or_(User.promo_code.is_(None), User.promo_code != 'SL001')
        ).order_by(User.created_at.desc())
        
        # Get total count before pagination
        total_count = requests_query.count()
        
        # Apply pagination
        pagination = requests_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        requests = pagination.items
        
        # Format requests for response
        requests_data = []
        for user in requests:
            requests_data.append({
                'id': user.id,
                'full_name': user.full_name,
                'phone': user.phone,
                'url': user.url,
                'promo_code': user.promo_code,
                'payment_method': user.payment_method,
                'paid_amount': float(user.paid_amount),
                'is_active': user.is_active,
                'share_paid': user.share_paid,
                'is_logged': user.is_logged,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'updated_at': user.updated_at.isoformat() if user.updated_at else None
            })
        
        return jsonify({
            'status': 'success',
            'message': 'Requests retrieved successfully',
            'data': {
                'requests': requests_data,
                'pagination': {
                    'total': total_count,
                    'page': page,
                    'per_page': per_page,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving requests: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while retrieving requests',
            'error': str(e)
        }), 500


@super_admin_bp.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    """
    Get users with pagination and filters
    Returns users where (status='pending' OR status='register') AND role='user' 
    AND (promo_code is null OR promo_code!='SL001')
    
    Filters:
    - phone: partial match (like search)
    - status: exact match ('pending' or 'register')
    - promo_code: exact match
    - direct_user: if true, return users without promo_code with status active or pending
    """
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Validate page number
        if page < 1:
            page = 1
        
        # Validate per_page
        if per_page < 1:
            per_page = 10
        if per_page > 100:
            per_page = 100
        
        # Get filter parameters
        phone_filter = request.args.get('phone', '').strip()
        status_filter = request.args.get('status', '').strip()
        promo_code_filter = request.args.get('promo_code', '').strip()
        direct_user = request.args.get('direct_user', '').strip().lower() == 'true'
        
        # Base query: users where (status='pending' OR status='register') AND role='user' 
        # AND (promo_code is null OR promo_code!='SL001')
        users_query = User.query.filter(
            User.role == 'user',
            or_(User.status == 'pending', User.status == 'register'),
            or_(User.promo_code.is_(None), User.promo_code != 'SL001')
        )
        
        # Apply direct_user filter (users without promo_code)
        if direct_user:
            users_query = users_query.filter(User.promo_code.is_(None))
        
        # Apply phone filter (partial match)
        if phone_filter:
            users_query = users_query.filter(User.phone.like(f'%{phone_filter}%'))
        
        # Apply status filter (exact match)
        if status_filter:
            if status_filter in ['pending', 'register']:
                users_query = users_query.filter(User.status == status_filter)
        
        # Apply promo_code filter (exact match)
        if promo_code_filter:
            users_query = users_query.filter(User.promo_code == promo_code_filter)
        
        # Order by created_at DESC (latest created accounts display first)
        users_query = users_query.order_by(User.created_at.desc())
        
        # Get total count before pagination
        total_count = users_query.count()
        
        # Apply pagination
        pagination = users_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        users = pagination.items
        
        # Format users for response
        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'full_name': user.full_name,
                'phone': user.phone,
                'url': user.url,
                'promo_code': user.promo_code,
                'payment_method': user.payment_method,
                'status': str(user.status) if user.status else None,
                'paid_amount': float(user.paid_amount),
                'is_active': user.is_active,
                'share_paid': user.share_paid,
                'is_logged': user.is_logged,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'updated_at': user.updated_at.isoformat() if user.updated_at else None
            })
        
        return jsonify({
            'status': 'success',
            'message': 'Users retrieved successfully',
            'data': {
                'users': users_data,
                'pagination': {
                    'total': total_count,
                    'page': page,
                    'per_page': per_page,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving users: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while retrieving users',
            'error': str(e)
        }), 500


@super_admin_bp.route('/register', methods=['POST'])
@jwt_required()
def register():
    """
    Admin registration API
    Creates a user with:
    - role = 'user' (fixed)
    - is_active = true (fixed)
    - status = 'register' (fixed)
    - is_logged = false (fixed)
    - share_paid = false (fixed)
    """
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
        
        logger.info(f"Received admin registration data: {data}")
        
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
            
            # Get paid_amount from form data, default to 0
            if data.get('paid_amount'):
                paid_amount = float(data.get('paid_amount', 0))
            elif data.get('referal_coin'):
                paid_amount = float(data.get('referal_coin', 0))
            else:
                paid_amount = 0
            
            # Validate paid_amount for user role
            if paid_amount == 0:
                return jsonify({
                    'status': 'error',
                    'message': 'Paid amount cannot be 0 for users with role "user"',
                    'error_code': 'INVALID_PAID_AMOUNT'
                }), 400
            
            # Create user with admin-specific defaults
            new_user = User(
                full_name=data['full_name'],
                phone=data['phone'],
                password=data['password'],
                url=s3_url,  # Store S3 URL in the url field
                payment_method=payment_method,
                promo_code=data.get('promo_code'),
                role='user',  # Fixed to 'user'
                paid_amount=paid_amount,
                status='register'  # Fixed to 'register'
            )
            
            # Set admin-specific defaults
            new_user.is_active = True  # Fixed to true
            new_user.is_logged = False  # Fixed to false
            new_user.share_paid = False  # Fixed to false
            
            db.session.add(new_user)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'User registered successfully',
                'data': {
                    'user': {
                        'id': new_user.id,
                        'full_name': new_user.full_name,
                        'phone': new_user.phone,
                        'url': new_user.url,
                        'promo_code': new_user.promo_code,
                        'payment_method': new_user.payment_method,
                        'role': str(new_user.role),
                        'status': str(new_user.status),
                        'paid_amount': float(new_user.paid_amount),
                        'is_active': new_user.is_active,
                        'is_logged': new_user.is_logged,
                        'share_paid': new_user.share_paid,
                        'created_at': new_user.created_at.isoformat() if new_user.created_at else None
                    }
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
        logger.error(f"Unexpected error during admin registration: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred during registration',
            'error_code': 'REGISTRATION_ERROR'
        }), 500


@super_admin_bp.route('/pre-register', methods=['GET'])
@jwt_required()
def get_pre_register_users():
    """
    Get pre-register users with pagination and filters
    Returns users where status='pre-register' AND role='user' 
    AND (promo_code is null OR promo_code!='SL001')
    
    Filters:
    - phone: partial match (like search)
    """
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Validate page number
        if page < 1:
            page = 1
        
        # Validate per_page
        if per_page < 1:
            per_page = 10
        if per_page > 100:
            per_page = 100
        
        # Get filter parameters
        phone_filter = request.args.get('phone', '').strip()
        
        # Base query: users where status='pre-register' AND role='user' 
        # AND (promo_code is null OR promo_code!='SL001')
        pre_register_query = User.query.filter(
            User.status == 'pre-register',
            User.role == 'user',
            or_(User.promo_code.is_(None), User.promo_code != 'SL001')
        )
        
        # Apply phone filter (partial match)
        if phone_filter:
            pre_register_query = pre_register_query.filter(User.phone.like(f'%{phone_filter}%'))
        
        # Order by created_at DESC (latest created accounts display first)
        pre_register_query = pre_register_query.order_by(User.created_at.desc())
        
        # Get total count before pagination
        total_count = pre_register_query.count()
        
        # Apply pagination
        pagination = pre_register_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        users = pagination.items
        
        # Format users for response
        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'full_name': user.full_name,
                'phone': user.phone,
                'url': user.url,
                'promo_code': user.promo_code,
                'payment_method': user.payment_method,
                'status': str(user.status) if user.status else None,
                'paid_amount': float(user.paid_amount),
                'is_active': user.is_active,
                'share_paid': user.share_paid,
                'is_logged': user.is_logged,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'updated_at': user.updated_at.isoformat() if user.updated_at else None
            })
        
        return jsonify({
            'status': 'success',
            'message': 'Pre-register users retrieved successfully',
            'data': {
                'users': users_data,
                'pagination': {
                    'total': total_count,
                    'page': page,
                    'per_page': per_page,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving pre-register users: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while retrieving pre-register users',
            'error': str(e)
        }), 500


@super_admin_bp.route('/login', methods=['POST'])
def login():
    """
    Super admin login API
    Validates phone and password, checks if role is 'admin'
    Returns token on success
    """
    schema = LoginSchema()
    try:
        # Log request (excluding sensitive data)
        logger.debug(f"Super admin login attempt from IP: {request.remote_addr}")
        
        # Validate request data
        try:
            data = schema.load(request.get_json())
        except ValidationError as e:
            return jsonify({
                'status': 'error',
                'message': 'Validation error',
                'errors': e.messages,
                'error_code': 'VALIDATION_ERROR'
            }), 400
        
        # Find user by phone
        user = User.query.filter_by(phone=data['phone']).first()
        
        # Check if user exists and password matches
        if not user or not bcrypt.check_password_hash(user.password, data['password']):
            return jsonify({
                'status': 'error',
                'message': 'Invalid phone number or password',
                'error_code': 'INVALID_CREDENTIALS'
            }), 401
        
        # Check if user has admin role
        if user.role != 'admin':
            return jsonify({
                'status': 'error',
                'message': 'Access denied. Admin privileges required.',
                'error_code': 'ADMIN_ACCESS_REQUIRED'
            }), 403
        
        # Generate access token
        access_token = generate_token(user.id)
        
        # Return success response with token
        return jsonify({
            'status': 'success',
            'message': 'Login successful',
            'data': {
                'user': {
                    'id': user.id,
                    'full_name': user.full_name,
                    'phone': user.phone,
                    'role': str(user.role),
                    'is_active': user.is_active
                },
                'access_token': access_token
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Super admin login error: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while processing login',
            'error_code': 'LOGIN_ERROR'
        }), 500
