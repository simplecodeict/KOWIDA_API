from flask import Blueprint, request, jsonify
from extensions import db, colombo_tz
from models.notification import Notification
from models.user import User
from datetime import datetime
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
        restriction_area = data.get('restriction_area')
        url = data.get('url')
        
        # Save notification to database
        current_time = datetime.now(colombo_tz).replace(tzinfo=None)
        notification = Notification(
            type=notification_type,
            header=header,
            sub_header=sub_header,
            body=body,
            restriction_area=restriction_area,
            url=url,
            created_at=current_time,
            updated_at=current_time
        )
        db.session.add(notification)
        db.session.commit()
        
        # Fetch all users from users table where expo_push_token != 'pending'
        users = User.query.filter(User.expo_push_token != 'pending').filter(User.expo_push_token.isnot(None)).all()
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
        push_body = body or "New notification"
        
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
        successfully_sent_count = 0
        batch_size = 100
        for i in range(0, len(notifications), batch_size):
            batch = notifications[i:i + batch_size]
            try:
                response = requests.post(EXPO_PUSH_URL, json=batch, timeout=10)
                response.raise_for_status()
                response_data = response.json()
                
                # Count successful sends from Expo response
                # Expo returns a list of receipts, each with a status
                if isinstance(response_data, dict) and 'data' in response_data:
                    receipts = response_data.get('data', [])
                    for receipt in receipts:
                        # Status can be 'ok' or an error status
                        if isinstance(receipt, dict) and receipt.get('status') == 'ok':
                            successfully_sent_count += 1
                elif isinstance(response_data, list):
                    # Sometimes Expo returns a list directly
                    for receipt in response_data:
                        if isinstance(receipt, dict) and receipt.get('status') == 'ok':
                            successfully_sent_count += 1
                else:
                    # If we can't parse the response, assume all in batch were sent
                    # (This is a fallback - Expo usually returns detailed receipts)
                    successfully_sent_count += len(batch)
                
                logger.info(f"Sent batch {i//batch_size + 1} of notifications: {len(batch)} tokens")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error sending notification batch: {str(e)}")
        
        return jsonify({
            'status': 'success',
            'message': f'Notification successfully sent to {successfully_sent_count} users',
            'data': {
                'notification': {
                    'id': notification.id,
                    'type': str(notification.type) if notification.type else None,
                    'header': notification.header,
                    'sub_header': notification.sub_header,
                    'body': notification.body,
                    'restriction_area': notification.restriction_area,
                    'url': notification.url,
                    'created_at': notification.created_at.isoformat() if notification.created_at else None,
                    'updated_at': notification.updated_at.isoformat() if notification.updated_at else None
                },
                'successfully_sent_count': successfully_sent_count,
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
        users_with_tokens_query = User.query.filter(
            User.expo_push_token != 'pending'
        ).filter(
            User.expo_push_token.isnot(None)
        )
        
        # Query users without valid tokens (expo_push_token == 'pending' or null)
        # Order by created_at DESC to show newest users first
        users_without_tokens_query = User.query.filter(
            (User.expo_push_token == 'pending') | (User.expo_push_token.is_(None))
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

