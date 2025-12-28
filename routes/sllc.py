from flask import Blueprint, jsonify, request, current_app
from models.base_amount import BaseAmount
from models.user import User
from models.bank_details import BankDetails
from models.reference import Reference
from models.transaction import Transaction
from models.notification import Notification
from schemas import UserFilterSchema, TransactionFilterSchema, PreRegisterSchema, PreRegisterSchema
from flask_jwt_extended import jwt_required, create_access_token, decode_token
from marshmallow import ValidationError
from datetime import datetime
from extensions import db, colombo_tz
from sqlalchemy import or_, and_
import logging
import requests
import secrets
import re

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

@sllc_bp.route('/notifications', methods=['GET'])
def get_sllc_notifications():
    """
    Get notifications for SLLC with pagination
    Returns:
    - All boost_knowledge notifications
    - All quotes notifications
    - Announcement notifications where who_see === 'SL001'
    - News notifications where who_see === 'SL001'
    Ordered by created_at DESC (newest first)
    """
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        
        # Ensure per_page is always 15 as specified
        per_page = 15
        
        # Validate page number
        if page < 1:
            page = 1
        
        # Query notifications with filters:
        # - All boost_knowledge notifications (regardless of who_see)
        # - All quotes notifications (regardless of who_see)
        # - Announcement notifications where who_see === 'SL001'
        # - News notifications where who_see === 'SL001'
        notifications_query = Notification.query.filter(
            or_(
                Notification.type == 'boost_knowledge',
                Notification.type == 'quotes',
                and_(Notification.type == 'announcement', Notification.who_see == 'SL001'),
                and_(Notification.type == 'news', Notification.who_see == 'SL001')
            )
        ).order_by(Notification.created_at.desc())
        
        # Get total count for pagination info
        total_count = notifications_query.count()
        
        # Apply pagination
        pagination = notifications_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        notifications = pagination.items
        
        # Format notifications for response
        notifications_data = []
        for notification in notifications:
            notifications_data.append({
                'id': notification.id,
                'type': str(notification.type) if notification.type else None,
                'header': notification.header,
                'sub_header': notification.sub_header,
                'body': notification.body,
                'restriction_area': notification.restriction_area,
                'url': notification.url,
                'who_see': notification.who_see,
                'created_at': notification.created_at.isoformat() if notification.created_at else None,
                'updated_at': notification.updated_at.isoformat() if notification.updated_at else None
            })
        
        return jsonify({
            'status': 'success',
            'message': 'SLLC notifications retrieved successfully',
            'data': {
                'notifications': notifications_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_count,
                    'pages': pagination.pages,
                    'has_next': pagination.has_next,
                    'has_prev': pagination.has_prev
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving SLLC notifications: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while retrieving SLLC notifications',
            'error': str(e)
        }), 500

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

def send_notification_to_sllc_users(header, sub_header, body, notification_body, url):
    """
    Send notification to SL001 users only (without saving to database)
    Returns the count of successfully sent notifications
    """
    try:
        # Fetch only SL001 users with valid tokens
        users = User.query.filter(
            User.expo_push_token != 'pending'
        ).filter(
            User.expo_push_token.isnot(None)
        ).filter(
            User.role != 'admin'
        ).filter(
            User.promo_code == 'SL001'
        ).all()
        
        tokens = [user.expo_push_token for user in users if user.expo_push_token and user.expo_push_token.strip()]
        
        if not tokens:
            logger.info("No SL001 users with valid tokens found")
            return 0
        
        # Prepare notifications for Expo API
        push_title = "SLLC"
        push_subtitle = sub_header or ""
        push_body = notification_body if notification_body is not None else (body or "New notification")
        
        # Prepare data payload with URL
        notification_data = {}
        if url:
            notification_data['url'] = url
        
        notifications = []
        for token in tokens:
            notification_payload = {
                "to": token,
                "sound": "default",
                "title": push_title,
                "subtitle": push_subtitle,
                "body": push_body
            }
            
            # Add data field with URL if available
            if notification_data:
                notification_payload["data"] = notification_data
            
            notifications.append(notification_payload)
        
        # Send notifications in batches of 100
        successfully_sent_count = 0
        batch_size = 100
        
        def send_batch(batch_to_send, batch_name=""):
            """Helper function to send a batch and count successful sends"""
            nonlocal successfully_sent_count
            try:
                response = requests.post(EXPO_PUSH_URL, json=batch_to_send, timeout=10)
                response.raise_for_status()
                response_data = response.json()
                
                logger.info(f"Expo API response for SL001 {batch_name}: {response_data}")
                
                # Count successful sends from Expo response
                receipts = []
                
                if isinstance(response_data, dict):
                    if 'data' in response_data:
                        receipts = response_data['data']
                    elif 'results' in response_data:
                        receipts = response_data['results']
                elif isinstance(response_data, list):
                    receipts = response_data
                
                # Count successful sends
                for receipt in receipts:
                    if isinstance(receipt, dict):
                        status = receipt.get('status')
                        if status == 'ok':
                            successfully_sent_count += 1
                        else:
                            logger.warning(f"SL001 notification send failed with status: {status}, receipt: {receipt}")
                
                # If no receipts found but response was successful, assume all were sent
                if not receipts and response.status_code == 200:
                    logger.warning(f"No receipts in response, assuming all {len(batch_to_send)} SL001 notifications were sent")
                    successfully_sent_count += len(batch_to_send)
                
                return True
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 400:
                    try:
                        error_data = e.response.json()
                        # Check if it's the PUSH_TOO_MANY_EXPERIENCE_IDS error
                        if 'errors' in error_data:
                            for error in error_data['errors']:
                                if error.get('code') == 'PUSH_TOO_MANY_EXPERIENCE_IDS':
                                    # Parse token groups by project
                                    details = error.get('details', {})
                                    if details:
                                        logger.info(f"Detected multiple projects for SL001, splitting batch by project")
                                        # Send separate batches for each project
                                        for project_id, project_tokens in details.items():
                                            # Filter notifications for this project's tokens
                                            project_batch = [
                                                notif for notif in batch_to_send 
                                                if notif['to'] in project_tokens
                                            ]
                                            if project_batch:
                                                logger.info(f"Sending {len(project_batch)} SL001 notifications for project {project_id}")
                                                # Send in sub-batches of 100
                                                for j in range(0, len(project_batch), batch_size):
                                                    sub_batch = project_batch[j:j + batch_size]
                                                    send_batch(sub_batch, f"project {project_id} sub-batch {j//batch_size + 1}")
                                        return True
                    except Exception as parse_error:
                        logger.error(f"Error parsing Expo error response for SL001: {str(parse_error)}")
                
                logger.error(f"HTTP error sending SL001 notification batch {batch_name}: {str(e)}")
                if e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}")
                    logger.error(f"Response text: {e.response.text}")
                return False
            except requests.exceptions.RequestException as e:
                logger.error(f"Error sending SL001 notification batch {batch_name}: {str(e)}")
                return False
        
        # Send notifications in batches
        for i in range(0, len(notifications), batch_size):
            batch = notifications[i:i + batch_size]
            send_batch(batch, f"SL001 batch {i//batch_size + 1}")
            logger.info(f"Processed SL001 batch {i//batch_size + 1} of notifications: {len(batch)} tokens, {successfully_sent_count} successful so far")
        
        return successfully_sent_count
        
    except Exception as e:
        logger.error(f"Error sending notifications to SL001 users: {str(e)}", exc_info=True)
        return 0

@sllc_bp.route('/notifications', methods=['POST'])
def create_sllc_notification():
    """
    Create a notification for SLLC users
    Saves notification to database with who_see = 'SL001' by default
    Then sends notification to SL001 users only
    """
    try:
        data = request.get_json()
        
        # Get notification data from request
        notification_type = data.get('type')
        header = data.get('header')
        sub_header = data.get('sub_header')
        body = data.get('body')
        notification_body = data.get('notification_body')  # Optional field for push notification body only
        restriction_area = data.get('restriction_area')
        url = data.get('url')
        # Force who_see to 'SL001' for SLLC notifications
        who_see = 'SL001'
        
        # Save notification to database with who_see = 'SL001'
        current_time = datetime.now(colombo_tz).replace(tzinfo=None)
        notification = Notification(
            type=notification_type,
            header=header,
            sub_header=sub_header,
            body=body,
            restriction_area=restriction_area,
            url=url,
            who_see=who_see,
            created_at=current_time,
            updated_at=current_time
        )
        db.session.add(notification)
        db.session.commit()
        
        # Send notification to SL001 users only
        successfully_sent_count = send_notification_to_sllc_users(
            header=header,
            sub_header=sub_header,
            body=body,
            notification_body=notification_body,
            url=url
        )
        
        return jsonify({
            'status': 'success',
            'message': f'Notification successfully created and sent to {successfully_sent_count} SL001 users',
            'data': {
                'notification': {
                    'id': notification.id,
                    'type': str(notification.type) if notification.type else None,
                    'header': notification.header,
                    'sub_header': notification.sub_header,
                    'body': notification.body,
                    'restriction_area': notification.restriction_area,
                    'url': notification.url,
                    'who_see': notification.who_see,
                    'created_at': notification.created_at.isoformat() if notification.created_at else None,
                    'updated_at': notification.updated_at.isoformat() if notification.updated_at else None
                },
                'successfully_sent_count': successfully_sent_count
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating SLLC notification: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while creating the SLLC notification',
            'error': str(e)
        }), 500

@sllc_bp.route('/pre-register', methods=['POST'])
def sllc_pre_register():
    """
    Pre-register a user for SLLC with promo_code = 'SL001' by default
    Similar to /api/auth/pre-register but automatically sets promo_code to 'SL001'
    Phone number validation is handled by frontend - accepts any phone number from payload
    """
    try:
        # Get request data directly (no phone validation)
        request_data = request.get_json()
        if not request_data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required',
                'error_code': 'VALIDATION_ERROR'
            }), 400
        
        # Validate only full_name (phone validation removed - handled by frontend)
        full_name = request_data.get('full_name')
        if not full_name or len(full_name.strip()) < 2:
            return jsonify({
                'status': 'error',
                'message': 'Validation error',
                'errors': {'full_name': ['Full name must be at least 2 characters']},
                'error_code': 'VALIDATION_ERROR'
            }), 400
        
        # Get phone directly from payload without validation
        phone = request_data.get('phone')
        if not phone:
            return jsonify({
                'status': 'error',
                'message': 'Validation error',
                'errors': {'phone': ['Phone number is required']},
                'error_code': 'VALIDATION_ERROR'
            }), 400
        
        # Get password (optional)
        password = request_data.get('password')
        
        # Get expo_push_token from payload (optional, set to None if not provided)
        expo_push_token = request_data.get('expo_push_token')
        if not expo_push_token or expo_push_token.strip() == '':
            expo_push_token = None
        
        # Prepare data dict
        data = {
            'full_name': full_name.strip(),
            'phone': phone.strip(),
            'password': password,
            'expo_push_token': expo_push_token
        }
        
        logging.info(f"Received SLLC pre-registration data: {data}")
        
        # Check if user already exists
        existing_user = User.query.filter_by(phone=data['phone']).first()
        if existing_user:
            return jsonify({
                'status': 'error',
                'message': 'Phone number already registered',
                'error_code': 'PHONE_ALREADY_EXISTS'
            }), 409
        
        # Create new user with pre-registration defaults and promo_code = 'SL001'
        try:
            # Use a default password if not provided (can be set later during full registration)
            password = data.get('password') or '0000'  # Default temporary password
            
            new_user = User(
                full_name=data['full_name'],
                phone=data['phone'],
                password=password,
                url=None,  # No receipt URL for pre-registration
                payment_method='pending',  # Payment method is pending
                promo_code='SL001',  # Set promo_code to SL001 by default
                role='user',  # Default role is user
                paid_amount=0,  # No payment yet
                status='pre-register',  # Set status as pre-register
                expo_push_token=data.get('expo_push_token')  # Get from payload, None if not provided
            )
            
            # Set is_active to False for pre-registered users
            new_user.is_active = False
            
            db.session.add(new_user)
            db.session.commit()
            
            # Generate access token using auth route's generate_token function
            from routes.auth import generate_token
            access_token = generate_token(new_user.id)
            
            return jsonify({
                'status': 'success',
                'message': 'SLLC user pre-registered successfully',
                'data': {
                    'user': {
                        'id': new_user.id,
                        'full_name': new_user.full_name,
                        'phone': new_user.phone,
                        'url': new_user.url,
                        'is_active': new_user.is_active,
                        'payment_method': new_user.payment_method,
                        'role': new_user.role,
                        'status': new_user.status,
                        'promo_code': new_user.promo_code,
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
                'message': 'Invalid input data',
                'error': str(e),
                'error_code': 'INVALID_INPUT'
            }), 400
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating SLLC pre-registered user: {str(e)}", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': 'An error occurred while pre-registering the user',
                'error': str(e),
                'error_code': 'INTERNAL_ERROR'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in SLLC pre-register endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while processing the pre-registration',
            'error': str(e),
            'error_code': 'INTERNAL_ERROR'
        }), 500