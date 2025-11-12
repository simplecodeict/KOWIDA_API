from flask import Blueprint, request, jsonify
from extensions import db
from models.notification import Notification
from models.user_token import UserToken
import requests
import logging

logger = logging.getLogger(__name__)

notification_bp = Blueprint('notification', __name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

@notification_bp.route('/create-notification', methods=['POST'])
def create_notification():
    """
    Create a notification and send it to all registered Expo push tokens
    """
    try:
        data = request.get_json()
        message = data.get('message', 'This work')
        
        # Save notification to database
        notification = Notification(text=message)
        db.session.add(notification)
        db.session.commit()
        
        # Fetch all device tokens from user_tokens table
        user_tokens = UserToken.query.filter(UserToken.expo_push_token.isnot(None)).all()
        tokens = [token.expo_push_token for token in user_tokens if token.expo_push_token]
        
        if not tokens:
            return jsonify({
                'status': 'success',
                'message': 'Notification saved but no tokens found to send to',
                'notification_id': notification.id
            }), 200
        
        # Prepare notifications for Expo API
        # Expo API supports sending multiple messages in one request (max 100 per batch)
        notifications = []
        for token in tokens:
            notifications.append({
                "to": token,
                "sound": "default",
                "title": "KOWIDA",
                "body": message
            })
        
        # Send notifications in batches of 100
        results = []
        batch_size = 100
        for i in range(0, len(notifications), batch_size):
            batch = notifications[i:i + batch_size]
            try:
                response = requests.post(EXPO_PUSH_URL, json=batch, timeout=10)
                response.raise_for_status()
                results.append(response.json())
                logger.info(f"Sent batch {i//batch_size + 1} of notifications: {len(batch)} tokens")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error sending notification batch: {str(e)}")
                results.append({"error": str(e)})
        
        return jsonify({
            'status': 'success',
            'message': 'Notification sent',
            'notification_id': notification.id,
            'tokens_sent': len(tokens),
            'expo_responses': results
        }), 200
        
    except Exception as e:
        logger.error(f"Error creating notification: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while creating the notification',
            'error': str(e)
        }), 500

