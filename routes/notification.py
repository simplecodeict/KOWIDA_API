from flask import Blueprint, request, jsonify
from extensions import db, colombo_tz
from models.notification import Notification
from models.user import User
from datetime import datetime
from sqlalchemy import or_
import requests
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

logger = logging.getLogger(__name__)

notification_bp = Blueprint('notification', __name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

# Configuration for large-scale notification sending
BATCH_SIZE = 100  # Expo's recommended max per request
MAX_CONCURRENT_BATCHES = 6  # Number of concurrent HTTP requests (Expo recommends 6)
REQUEST_TIMEOUT = 30  # Increased timeout for reliability
MAX_RETRIES = 3  # Number of retry attempts for failed requests
RETRY_BACKOFF_FACTOR = 0.5  # Exponential backoff factor


def create_session_with_retries():
    """Create a requests session with retry strategy for reliability"""
    session = requests.Session()
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=MAX_CONCURRENT_BATCHES,
        pool_maxsize=MAX_CONCURRENT_BATCHES
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def send_single_batch(session, batch_to_send, batch_name=""):
    """
    Send a single batch of notifications to Expo API.
    Returns tuple of (success_count, failed_count, error_message)
    """
    success_count = 0
    failed_count = 0
    error_message = None
    
    try:
        response = session.post(
            EXPO_PUSH_URL,
            json=batch_to_send,
            timeout=REQUEST_TIMEOUT,
            headers={
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip, deflate',
                'Content-Type': 'application/json'
            }
        )
        response.raise_for_status()
        response_data = response.json()
        
        # Parse response - handle different response formats
        receipts = []
        if isinstance(response_data, dict):
            if 'data' in response_data:
                receipts = response_data['data']
            elif 'results' in response_data:
                receipts = response_data['results']
        elif isinstance(response_data, list):
            receipts = response_data
        
        # Count successful and failed sends
        for receipt in receipts:
            if isinstance(receipt, dict):
                status = receipt.get('status')
                if status == 'ok':
                    success_count += 1
                else:
                    failed_count += 1
                    error_detail = receipt.get('message', 'Unknown error')
                    logger.debug(f"Notification failed: {error_detail}")
        
        # If no receipts but 200 response, assume all sent
        if not receipts and response.status_code == 200:
            success_count = len(batch_to_send)
        
        logger.info(f"{batch_name}: sent {success_count}/{len(batch_to_send)} successfully")
        return (success_count, failed_count, None)
        
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 400:
            try:
                error_data = e.response.json()
                # Handle PUSH_TOO_MANY_EXPERIENCE_IDS error
                if 'errors' in error_data:
                    for error in error_data['errors']:
                        if error.get('code') == 'PUSH_TOO_MANY_EXPERIENCE_IDS':
                            details = error.get('details', {})
                            if details:
                                logger.info(f"{batch_name}: Multiple projects detected, splitting...")
                                # Split and resend by project
                                for project_id, project_tokens in details.items():
                                    project_batch = [
                                        notif for notif in batch_to_send
                                        if notif['to'] in project_tokens
                                    ]
                                    if project_batch:
                                        sub_success, sub_failed, _ = send_single_batch(
                                            session,
                                            project_batch,
                                            f"{batch_name} project {project_id}"
                                        )
                                        success_count += sub_success
                                        failed_count += sub_failed
                                return (success_count, failed_count, None)
            except Exception as parse_error:
                logger.error(f"Error parsing Expo error: {str(parse_error)}")
        
        error_message = f"HTTP {e.response.status_code if e.response else 'unknown'}: {str(e)}"
        logger.error(f"{batch_name} failed: {error_message}")
        failed_count = len(batch_to_send)
        
    except requests.exceptions.Timeout:
        error_message = "Request timeout"
        logger.error(f"{batch_name} failed: timeout after {REQUEST_TIMEOUT}s")
        failed_count = len(batch_to_send)
        
    except requests.exceptions.RequestException as e:
        error_message = str(e)
        logger.error(f"{batch_name} failed: {error_message}")
        failed_count = len(batch_to_send)
    
    return (success_count, failed_count, error_message)


def send_notifications_concurrently(tokens, push_title, push_subtitle, push_body, notification_data):
    """
    Send notifications to all tokens using concurrent batch processing.
    Returns total success count and total failed count.
    """
    total_success = 0
    total_failed = 0
    
    if not tokens:
        return (0, 0)
    
    # Create notification payloads in batches to manage memory
    batches = []
    current_batch = []
    
    for token in tokens:
        payload = {
            "to": token,
            "sound": "default",
            "title": push_title,
            "subtitle": push_subtitle,
            "body": push_body
        }
        if notification_data:
            payload["data"] = notification_data
        
        current_batch.append(payload)
        
        if len(current_batch) >= BATCH_SIZE:
            batches.append(current_batch)
            current_batch = []
    
    # Don't forget the last batch
    if current_batch:
        batches.append(current_batch)
    
    total_batches = len(batches)
    logger.info(f"Starting to send {len(tokens)} notifications in {total_batches} batches (max {MAX_CONCURRENT_BATCHES} concurrent)")
    
    # Create a session with retry strategy
    session = create_session_with_retries()
    
    try:
        # Process batches concurrently using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_BATCHES) as executor:
            # Submit all batches
            future_to_batch = {
                executor.submit(
                    send_single_batch,
                    session,
                    batch,
                    f"Batch {i+1}/{total_batches}"
                ): i for i, batch in enumerate(batches)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_batch):
                batch_index = future_to_batch[future]
                try:
                    success, failed, error = future.result()
                    total_success += success
                    total_failed += failed
                except Exception as e:
                    logger.error(f"Batch {batch_index + 1} raised exception: {str(e)}")
                    total_failed += len(batches[batch_index])
    finally:
        session.close()
    
    logger.info(f"Notification sending complete: {total_success} success, {total_failed} failed out of {len(tokens)} total")
    return (total_success, total_failed)


def get_user_tokens_chunked(chunk_size=1000):
    """
    Generator that yields user tokens in chunks to manage memory for large user bases.
    """
    offset = 0
    while True:
        users = User.query.filter(
            User.expo_push_token != 'pending'
        ).filter(
            User.expo_push_token.isnot(None)
        ).filter(
            User.role != 'admin'
        ).filter(
            or_(User.promo_code.is_(None), User.promo_code != 'SL001')
        ).offset(offset).limit(chunk_size).all()
        
        if not users:
            break
        
        tokens = [user.expo_push_token for user in users if user.expo_push_token and user.expo_push_token.strip()]
        if tokens:
            yield tokens
        
        offset += chunk_size


@notification_bp.route('/notifications', methods=['POST'])
def create_notification():
    """
    Create a notification and send it to all users with valid Expo push tokens.
    Optimized for handling large user bases (3k+) with:
    - Concurrent batch processing
    - Automatic retry on failure
    - Memory-efficient token loading
    - Connection pooling
    """
    try:
        data = request.get_json()
        
        # Get notification data from request
        notification_type = data.get('type')
        header = data.get('header')
        sub_header = data.get('sub_header')
        body = data.get('body')
        notification_body = data.get('notification_body')
        restriction_area = data.get('restriction_area')
        url = data.get('url')
        who_see = data.get('who_see', 'all')
        
        # Save notification to database first
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
        
        # Get all tokens efficiently (for large user bases, this is still okay as we process in batches)
        users = User.query.filter(
            User.expo_push_token != 'pending'
        ).filter(
            User.expo_push_token.isnot(None)
        ).filter(
            User.role != 'admin'
        ).filter(
            or_(User.promo_code.is_(None), User.promo_code != 'SL001')
        ).with_entities(User.expo_push_token).all()
        
        tokens = [u.expo_push_token for u in users if u.expo_push_token and u.expo_push_token.strip()]
        
        if not tokens:
            return jsonify({
                'status': 'success',
                'message': 'Notification saved but no users with valid tokens found to send to',
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
                    'successfully_sent_count': 0
                }
            }), 200
        
        # Prepare push notification content
        push_title = "KOWIDA"
        push_subtitle = sub_header or ""
        push_body = notification_body if notification_body is not None else (body or "New notification")
        
        # Prepare data payload with URL
        notification_data = {}
        if url:
            notification_data['url'] = url
        
        # Send notifications using concurrent processing
        logger.info(f"Starting notification send to {len(tokens)} users")
        start_time = time.time()
        
        successfully_sent_count, failed_count = send_notifications_concurrently(
            tokens=tokens,
            push_title=push_title,
            push_subtitle=push_subtitle,
            push_body=push_body,
            notification_data=notification_data
        )
        
        elapsed_time = time.time() - start_time
        logger.info(f"Notification sending completed in {elapsed_time:.2f}s: {successfully_sent_count} success, {failed_count} failed")
        
        # Send to SL001 users if applicable
        sllc_sent_count = 0
        if notification_type in ['quotes', 'boost_knowledge']:
            try:
                from routes.sllc import send_notification_to_sllc_users
                sllc_sent_count = send_notification_to_sllc_users(
                    header=header,
                    sub_header=sub_header,
                    body=body,
                    notification_body=notification_body,
                    url=url
                )
                logger.info(f"Successfully sent notification to {sllc_sent_count} SL001 users")
            except Exception as sllc_error:
                logger.error(f"Error sending notification to SL001 users: {str(sllc_error)}", exc_info=True)
        
        # Build response message
        if sllc_sent_count > 0:
            message = f'Notification successfully sent to {successfully_sent_count} non-SL001 users and {sllc_sent_count} SL001 users'
        else:
            message = f'Notification successfully sent to {successfully_sent_count} users'
        
        if failed_count > 0:
            message += f' ({failed_count} failed)'
        
        return jsonify({
            'status': 'success',
            'message': message,
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
                'successfully_sent_count': {
                    'non_sllc_users': successfully_sent_count,
                    'sllc_users': sllc_sent_count,
                    'total': successfully_sent_count + sllc_sent_count
                },
                'failed_count': failed_count,
                'total_tokens': len(tokens),
                'processing_time_seconds': round(elapsed_time, 2)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating notification: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while creating the notification',
            'error': str(e)
        }), 500

@notification_bp.route('/pre-register-notifications', methods=['POST'])
def create_pre_register_notification():
    """
    Create a notification and send it to users with status 'pre-register' only.
    The notification who_see will be set to 'pre-register'.
    Uses optimized concurrent batch processing for large user bases.
    """
    try:
        data = request.get_json()
        
        # Get notification data from request
        notification_type = data.get('type')
        header = data.get('header')
        sub_header = data.get('sub_header')
        body = data.get('body')
        notification_body = data.get('notification_body')
        restriction_area = data.get('restriction_area')
        url = data.get('url')
        who_see = 'pre-register'
        
        # Save notification to database
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
        
        # Fetch pre-register users with valid tokens efficiently
        users = User.query.filter(
            User.expo_push_token != 'pending'
        ).filter(
            User.expo_push_token.isnot(None)
        ).filter(
            User.role != 'admin'
        ).filter(
            User.status == 'pre-register'
        ).filter(
            or_(User.promo_code.is_(None), User.promo_code != 'SL001')
        ).with_entities(User.expo_push_token).all()
        
        tokens = [u.expo_push_token for u in users if u.expo_push_token and u.expo_push_token.strip()]

        # Handle case where no KOWIDA pre-register users found
        kowida_sent_count = 0
        failed_count = 0
        elapsed_time = 0
        
        if not tokens:
            logger.info("No KOWIDA pre-register users with valid tokens found")
        else:
            # Prepare push notification content
            push_title = "KOWIDA"
            push_subtitle = sub_header or ""
            push_body = notification_body if notification_body is not None else (body or "New notification")
            
            # Prepare data payload with URL
            notification_data = {}
            if url:
                notification_data['url'] = url
            
            # Send notifications using concurrent processing
            logger.info(f"Starting pre-register notification send to {len(tokens)} users")
            start_time = time.time()
            
            kowida_sent_count, failed_count = send_notifications_concurrently(
                tokens=tokens,
                push_title=push_title,
                push_subtitle=push_subtitle,
                push_body=push_body,
                notification_data=notification_data
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"Pre-register notification sending completed in {elapsed_time:.2f}s: {kowida_sent_count} success, {failed_count} failed")
        
        message = f'Notification successfully sent to {kowida_sent_count} pre-register users'
        if failed_count > 0:
            message += f' ({failed_count} failed)'
        
        return jsonify({
            'status': 'success',
            'message': message,
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
                'successfully_sent_count': kowida_sent_count,
                'failed_count': failed_count,
                'total_tokens': len(tokens),
                'processing_time_seconds': round(elapsed_time, 2)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating pre-register notification: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while creating the pre-register notification',
            'error': str(e)
        }), 500

@notification_bp.route('/notifications', methods=['GET'])
def get_notifications():
    """
    Get notifications with pagination
    Returns the last 15 notifications ordered by created_at DESC
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
        
        # Query notifications ordered by created_at DESC (newest first)
        notifications_query = Notification.query.order_by(Notification.created_at.desc())
        
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
            'message': 'Notifications retrieved successfully',
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
        logger.error(f"Error retrieving notifications: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while retrieving notifications',
            'error': str(e)
        }), 500

# this API used to get short note
@notification_bp.route('/boost-knowledge', methods=['GET'])
def get_boost_knowledge_notifications():
    """
    Get boost_knowledge notifications with pagination
    Returns boost_knowledge notifications ordered by created_at ASC
    Supports filtering by type parameter: සමාන, විරුද්ධ, or ව්‍යාකරණ
    """
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        
        # Get type filter parameter
        type_filter = request.args.get('type', '').strip()
        
        # Validate page number
        if page < 1:
            page = 1
        
        # Validate per_page (set reasonable limits)
        if per_page < 1:
            per_page = 15
        if per_page > 100:
            per_page = 100
        
        # Base query: always filter for boost_knowledge notifications
        notifications_query = Notification.query.filter(
            Notification.type == 'boost_knowledge'
        )
        
        # Apply type filter if provided
        if type_filter:
            if type_filter == 'සමාන':
                # Filter: header contains "සමාන"
                notifications_query = notifications_query.filter(
                    Notification.header.contains('සමාන')
                )
            elif type_filter == 'විරුද්ධ':
                # Filter: header contains "විරුද්ධ"
                notifications_query = notifications_query.filter(
                    Notification.header.contains('විරුද්ධ')
                )
            elif type_filter == 'ව්‍යාකරණ':
                # Filter: header does NOT contain "සමාන" AND does NOT contain "විරුද්ධ"
                notifications_query = notifications_query.filter(
                    ~Notification.header.contains('සමාන')
                ).filter(
                    ~Notification.header.contains('විරුද්ධ')
                )
            # If type_filter has a value but doesn't match any of the above, 
            # it will still be applied (no additional filter), which means all boost_knowledge notifications
        
        # Order by created_at ASC (oldest first)
        notifications_query = notifications_query.order_by(Notification.created_at.asc())
        
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
            'message': 'Boost knowledge notifications retrieved successfully',
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
        logger.error(f"Error retrieving boost knowledge notifications: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while retrieving boost knowledge notifications',
            'error': str(e)
        }), 500

@notification_bp.route('/notifications/<int:notification_id>', methods=['PUT'])
def update_notification(notification_id):
    """
    Update a notification by ID
    """
    try:
        # Find the notification by ID
        notification = Notification.query.get(notification_id)
        
        if not notification:
            return jsonify({
                'status': 'error',
                'message': 'Notification not found'
            }), 404
        
        # Get update data from request
        data = request.get_json()
        
        # Update fields if provided
        if 'type' in data:
            notification.type = data['type']
        if 'header' in data:
            notification.header = data['header']
        if 'sub_header' in data:
            notification.sub_header = data['sub_header']
        if 'body' in data:
            notification.body = data['body']
        if 'restriction_area' in data:
            notification.restriction_area = data['restriction_area']
        if 'url' in data:
            notification.url = data['url']
        if 'who_see' in data:
            notification.who_see = data['who_see']
        
        # Update the updated_at timestamp
        notification.updated_at = datetime.now(colombo_tz).replace(tzinfo=None)
        
        # Save changes to database
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Notification updated successfully',
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
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating notification: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while updating the notification',
            'error': str(e)
        }), 500

@notification_bp.route('/notifications/<int:notification_id>', methods=['DELETE'])
def delete_notification(notification_id):
    """
    Delete a notification by ID
    """
    try:
        # Find the notification by ID
        notification = Notification.query.get(notification_id)
        
        if not notification:
            return jsonify({
                'status': 'error',
                'message': 'Notification not found'
            }), 404
        
        # Store notification data for response before deletion
        notification_data = {
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
        }
        
        # Delete the notification
        db.session.delete(notification)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Notification deleted successfully',
            'data': {
                'notification': notification_data
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error deleting notification: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while deleting the notification',
            'error': str(e)
        }), 500

@notification_bp.route('/users-with-tokens', methods=['GET'])
def get_users_with_tokens():
    """
    Get users with and without valid Expo push tokens with pagination
    Returns both lists of users along with their counts
    """
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Fixed to 10 per page
        
        # Validate page number
        if page < 1:
            page = 1
        
        # Query users with valid tokens (expo_push_token != 'pending' and not null)
        # Exclude users with promo_code = 'SL001' (include NULL promo_code)
        users_with_tokens_query = User.query.filter(
            User.expo_push_token != 'pending'
        ).filter(
            User.expo_push_token.isnot(None)
        ).filter(
            or_(User.promo_code.is_(None), User.promo_code != 'SL001')
        )
        
        # Query users without valid tokens (expo_push_token == 'pending' or null)
        # Exclude users with promo_code = 'SL001' (include NULL promo_code)
        # Order by created_at ASC to show oldest users first
        users_without_tokens_query = User.query.filter(
            (User.expo_push_token == 'pending') | (User.expo_push_token.is_(None))
        ).filter(
            or_(User.promo_code.is_(None), User.promo_code != 'SL001')
        ).order_by(User.created_at.desc())
        
        # Get total counts
        total_with_tokens = users_with_tokens_query.count()
        total_without_tokens = users_without_tokens_query.count()
        
        # Apply pagination to users without tokens only
        pagination_without_tokens = users_without_tokens_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        users_without_tokens = pagination_without_tokens.items
        
        # Format users without tokens data
        users_without_tokens_data = []
        for user in users_without_tokens:
            users_without_tokens_data.append({
                'id': user.id,
                'full_name': user.full_name,
                'phone': user.phone,
                'expo_push_token': user.expo_push_token,
                'is_active': user.is_active,
                'status': str(user.status) if user.status else None,
                'role': str(user.role) if user.role else None,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'updated_at': user.updated_at.isoformat() if user.updated_at else None
            })
        
        return jsonify({
            'status': 'success',
            'message': f'Found {total_with_tokens} users with tokens and {total_without_tokens} users without tokens',
            'data': {
                'users_with_tokens': {
                    'count': total_with_tokens
                },
                'users_without_tokens': {
                    'users': users_without_tokens_data,
                    'count': total_without_tokens,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': total_without_tokens,
                        'pages': pagination_without_tokens.pages,
                        'has_next': pagination_without_tokens.has_next,
                        'has_prev': pagination_without_tokens.has_prev
                    }
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error retrieving users with tokens: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while retrieving users with tokens',
            'error': str(e)
        }), 500

