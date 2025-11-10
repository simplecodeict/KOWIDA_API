from flask import Blueprint, jsonify, request
from models.base_amount import BaseAmount
from models.user import User
from models.bank_details import BankDetails
from models.reference import Reference
from models.transaction import Transaction
from schemas import UserFilterSchema, TransactionFilterSchema
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError
from datetime import datetime
from extensions import db
import logging

logger = logging.getLogger(__name__)

sllc_bp = Blueprint('sllc', __name__)

@sllc_bp.route('/base-data', methods=['GET'])
def get_base_data_for_sllc():
    """
    Get base data for SLLC
    Returns the last base amount record from the base_amounts table
    """
    try:
        logger.debug("=== Starting /base-data endpoint for SLLC ===")
        
        # Always fetch the base amount record with id = 2
        base_amount = BaseAmount.query.get(2)
        
        if not base_amount:
            return jsonify({
                'status': 'error',
                'message': 'Base amount with id 2 not found'
            }), 404
        
        response_data = {
            'status': 'success',
            'data': {
                'id': base_amount.id,
                'amount': float(base_amount.amount) if base_amount.amount else 0
            }
        }
        
        logger.debug("Successfully retrieved base amount id 2 for SLLC")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error in SLLC base-data endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@sllc_bp.route('/users', methods=['GET'])
@jwt_required()
def get_all_sllc_users():
    schema = UserFilterSchema()
    try:
        # Validate query parameters - empty dict if no parameters provided
        params = schema.load(request.args or {})
        
        # Base query for users with role = 'user' and promo_code = 'SL001'
        query = User.query.filter(User.role == 'user', User.promo_code == 'SL001')\
            .outerjoin(BankDetails)
        
        # Apply is_active filter if provided
        if 'is_active' in params and params['is_active'] is not None:
            query = query.filter(User.is_active == params['is_active'])
            
        # Apply is_reference_paid filter if provided
        if 'is_reference_paid' in params and params['is_reference_paid'] is not None:
            query = query.filter(User.is_reference_paid == params['is_reference_paid'])
            
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

@sllc_bp.route('/requests', methods=['GET'])
@jwt_required()
def get_all_sllc_requests():
    schema = UserFilterSchema()
    try:
        # Validate query parameters - empty dict if no parameters provided
        params = schema.load(request.args or {})
        
        # Base query for inactive users with promo_code = 'SL001' and their relationships
        query = User.query.filter_by(is_active=False, role='user')\
            .filter(User.promo_code == 'SL001')\
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

@sllc_bp.route('/reference-owners', methods=['GET'])
@jwt_required()
def get_sllc_reference_owners():
    schema = UserFilterSchema()
    try:
        # Validate query parameters - empty dict if no parameters provided
        params = schema.load(request.args or {})
        
        # Base query for active users with role = 'referer' who created SL001 reference
        query = User.query\
            .filter(User.is_active == True)\
            .filter(User.role == 'referer')\
            .outerjoin(Reference, User.phone == Reference.phone)\
            .filter(Reference.code == 'SL001')\
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
                'promo_code': user.promo_code,
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

@sllc_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def get_sllc_dashboard_stats():
    try:
        # Count active users (role = 'user', is_active = true, and promo_code = 'SL001')
        active_users_count = User.query.filter(
            User.role == 'user',
            User.is_active == True,
            User.promo_code == 'SL001'
        ).count()
        
        # Count requests (role = 'user', is_active = false, and promo_code = 'SL001')
        requests_count = User.query.filter(
            User.role == 'user',
            User.is_active == False,
            User.promo_code == 'SL001'
        ).count()
        
        # Count reference owners (role = 'referer', is_active = true, and promo_code = 'SL001')
        reference_owners_count = User.query.filter(
            User.role == 'referer',
            User.is_active == True,
            User.promo_code == 'SL001'
        ).count()
        
        # Count reference payment pending (role = 'user', is_active = true, is_reference_paid = false, and promo_code = 'SL001')
        from sqlalchemy import and_, alias
        UserAlias = alias(User)
        reference_payment_pending_count = db.session.query(User).join(
            Reference, User.promo_code == Reference.code
        ).join(
            UserAlias, Reference.phone == UserAlias.c.phone
        ).filter(
            and_(
                User.role == 'user',
                User.is_active == True,
                User.is_reference_paid == False,
                User.promo_code == 'SL001',
                UserAlias.c.role == 'referer'  # Reference owner must be referer, not admin
            )
        ).count()
        
        # Calculate total income (sum of paid_amount for active users with role = 'user' and promo_code = 'SL001')
        from sqlalchemy import func
        total_income_result = db.session.query(func.sum(User.paid_amount)).filter(
            User.role == 'user',
            User.is_active == True,
            User.promo_code == 'SL001'
        ).scalar()
        total_income = float(total_income_result) if total_income_result else 0.0
        
        # Calculate total pending amount (sum of paid_amount for inactive users with role = 'user' and promo_code = 'SL001')
        total_pending_result = db.session.query(func.sum(User.paid_amount)).filter(
            User.role == 'user',
            User.is_active == False,
            User.promo_code == 'SL001'
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

@sllc_bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_all_sllc_transactions():
    schema = TransactionFilterSchema()
    try:
        # Validate query parameters
        params = schema.load(request.args or {})
        
        # Base query for transactions with reference owner data (reference_code = 'SL001')
        query = Transaction.query.join(User, Transaction.user_id == User.id)\
            .filter(Transaction.reference_code == 'SL001')
        
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
                    'promo_code': reference_owner.promo_code,
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