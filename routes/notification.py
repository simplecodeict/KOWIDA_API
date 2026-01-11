from flask import Blueprint, request, jsonify
from extensions import db, colombo_tz
from models.notification import Notification
from models.user import User
from datetime import datetime
from sqlalchemy import or_
import requests
import logging

logger = logging.getLogger(__name__)

notification_bp = Blueprint('notification', __name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

@notification_bp.route('/notifications', methods=['POST'])
def create_notification():
    """
    Create a notification and send it to all users with valid Expo push tokens
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
        who_see = data.get('who_see', 'all')  # Default to 'all' if not provided
        
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
        
        # Fetch all users from users table where expo_push_token != 'pending' and role != 'admin'
        # Exclude admin users - only send to regular users (KOWIDA app, not KOWIDA-ADMIN)
        # Exclude only SL001 users - include users with no promo code and users with other promo codes
        users = User.query.filter(
            User.expo_push_token != 'pending'
        ).filter(
            User.expo_push_token.isnot(None)
        ).filter(
            User.role != 'admin'
        ).filter(
            or_(User.promo_code.is_(None), User.promo_code != 'SL001')
        ).all()
        tokens = [user.expo_push_token for user in users if user.expo_push_token and user.expo_push_token.strip()]
        
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
        
        # Prepare notifications for Expo API
        # Expo API supports sending multiple messages in one request (max 100 per batch)
        # Use "KOWIDA" as title, type as subtitle, body as message body
        push_title = "KOWIDA"
        push_subtitle = sub_header or ""
        # Use notification_body if provided, otherwise fall back to body
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
        
        # Send notifications in batches of 100 and track successful sends
        # Handle case where tokens are from different Expo projects
        successfully_sent_count = 0
        batch_size = 100
        
        def send_batch(batch_to_send, batch_name=""):
            """Helper function to send a batch and count successful sends"""
            nonlocal successfully_sent_count
            try:
                response = requests.post(EXPO_PUSH_URL, json=batch_to_send, timeout=10)
                response.raise_for_status()
                response_data = response.json()
                
                # Log the response for debugging
                logger.info(f"Expo API response for {batch_name}: {response_data}")
                
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
                            logger.warning(f"Notification send failed with status: {status}, receipt: {receipt}")
                
                # If no receipts found but response was successful, assume all were sent
                if not receipts and response.status_code == 200:
                    logger.warning(f"No receipts in response, assuming all {len(batch_to_send)} notifications were sent")
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
                                        logger.info(f"Detected multiple projects, splitting batch by project")
                                        # Send separate batches for each project
                                        for project_id, project_tokens in details.items():
                                            # Filter notifications for this project's tokens
                                            project_batch = [
                                                notif for notif in batch_to_send 
                                                if notif['to'] in project_tokens
                                            ]
                                            if project_batch:
                                                logger.info(f"Sending {len(project_batch)} notifications for project {project_id}")
                                                # Send in sub-batches of 100
                                                for j in range(0, len(project_batch), batch_size):
                                                    sub_batch = project_batch[j:j + batch_size]
                                                    send_batch(sub_batch, f"project {project_id} sub-batch {j//batch_size + 1}")
                                        return True
                    except Exception as parse_error:
                        logger.error(f"Error parsing Expo error response: {str(parse_error)}")
                
                logger.error(f"HTTP error sending notification batch {batch_name}: {str(e)}")
                if e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}")
                    logger.error(f"Response text: {e.response.text}")
                return False
            except requests.exceptions.RequestException as e:
                logger.error(f"Error sending notification batch {batch_name}: {str(e)}")
                return False
        
        # Send notifications in batches
        for i in range(0, len(notifications), batch_size):
            batch = notifications[i:i + batch_size]
            send_batch(batch, f"batch {i//batch_size + 1}")
            logger.info(f"Processed batch {i//batch_size + 1} of notifications: {len(batch)} tokens, {successfully_sent_count} successful so far")
        
        # After successfully sending to non-SL001 users, send to SL001 users only if type is 'quotes' or 'boost_knowledge'
        sllc_sent_count = 0
        if notification_type in ['quotes', 'boost_knowledge']:
            try:
                # Import SLLC function to avoid circular imports
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
                # Log error but don't fail the request since non-SL001 users already received it
                logger.error(f"Error sending notification to SL001 users: {str(sllc_error)}", exc_info=True)
        
        # Build response message based on whether SLLC users were notified
        if sllc_sent_count > 0:
            message = f'Notification successfully sent to {successfully_sent_count} non-SL001 users and {sllc_sent_count} SL001 users'
        else:
            message = f'Notification successfully sent to {successfully_sent_count} users'
        
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
                'total_tokens': len(tokens)
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
    Create a notification and send it to users with status 'pre-register' only
    The notification who_see will be set to 'pre-register'
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
        # Force who_see to 'pre-register' for this endpoint
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
        
        # Fetch pre-register users with valid tokens (expo_push_token != 'pending' and not null)
        # Exclude admin users - only send to regular users (KOWIDA app, not KOWIDA-ADMIN)
        # Exclude only SL001 users - include users with no promo code and users with other promo codes
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
        ).all()
        tokens = [user.expo_push_token for user in users if user.expo_push_token and user.expo_push_token.strip()]

        # Handle case where no KOWIDA pre-register users found
        kowida_sent_count = 0
        if not tokens:
            logger.info("No KOWIDA pre-register users with valid tokens found")
        else:
            # Prepare notifications for Expo API
            # Expo API supports sending multiple messages in one request (max 100 per batch)
            # Use "KOWIDA" as title, type as subtitle, body as message body
            push_title = "KOWIDA"
            push_subtitle = sub_header or ""
            # Use notification_body if provided, otherwise fall back to body
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
            
            # Send notifications in batches of 100 and track successful sends
            # Handle case where tokens are from different Expo projects
            successfully_sent_count = 0
            batch_size = 100
            
            def send_batch(batch_to_send, batch_name=""):
                """Helper function to send a batch and count successful sends"""
                nonlocal successfully_sent_count
                try:
                    response = requests.post(EXPO_PUSH_URL, json=batch_to_send, timeout=10)
                    response.raise_for_status()
                    response_data = response.json()
                    
                    # Log the response for debugging
                    logger.info(f"Expo API response for {batch_name}: {response_data}")
                    
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
                                logger.warning(f"Notification send failed with status: {status}, receipt: {receipt}")
                    
                    # If no receipts found but response was successful, assume all were sent
                    if not receipts and response.status_code == 200:
                        logger.warning(f"No receipts in response, assuming all {len(batch_to_send)} notifications were sent")
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
                                            logger.info(f"Detected multiple projects, splitting batch by project")
                                            # Send separate batches for each project
                                            for project_id, project_tokens in details.items():
                                                # Filter notifications for this project's tokens
                                                project_batch = [
                                                    notif for notif in batch_to_send 
                                                    if notif['to'] in project_tokens
                                                ]
                                                if project_batch:
                                                    logger.info(f"Sending {len(project_batch)} notifications for project {project_id}")
                                                    # Send in sub-batches of 100
                                                    for j in range(0, len(project_batch), batch_size):
                                                        sub_batch = project_batch[j:j + batch_size]
                                                        send_batch(sub_batch, f"project {project_id} sub-batch {j//batch_size + 1}")
                                            return True
                        except Exception as parse_error:
                            logger.error(f"Error parsing Expo error response: {str(parse_error)}")
                    
                    logger.error(f"HTTP error sending notification batch {batch_name}: {str(e)}")
                    if e.response is not None:
                        logger.error(f"Response status: {e.response.status_code}")
                        logger.error(f"Response text: {e.response.text}")
                    return False
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error sending notification batch {batch_name}: {str(e)}")
                    return False
            
            # Send notifications in batches
            for i in range(0, len(notifications), batch_size):
                batch = notifications[i:i + batch_size]
                send_batch(batch, f"KOWIDA pre-register batch {i//batch_size + 1}")
                logger.info(f"Processed KOWIDA pre-register batch {i//batch_size + 1} of notifications: {len(batch)} tokens, {successfully_sent_count} successful so far")
            
            kowida_sent_count = successfully_sent_count
        
        return jsonify({
            'status': 'success',
            'message': f'Notification successfully sent to {kowida_sent_count} pre-register users',
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
                'total_tokens': len(tokens)
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

