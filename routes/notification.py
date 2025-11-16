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
                        'type': notification.type,
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
                    'type': notification.type,
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
                'type': notification.type,
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

