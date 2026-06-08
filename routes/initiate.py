from flask import Blueprint, request, jsonify
from models.notification import Notification
from models.version import Version
from sqlalchemy import or_, and_
import logging

logger = logging.getLogger(__name__)

initiate_bp = Blueprint('initiate', __name__)


def _get_notifications_query():
    return Notification.query.filter(
        or_(
            Notification.type == 'boost_knowledge',
            Notification.type == 'quotes',
            and_(Notification.type == 'announcement', Notification.who_see != 'SL001'),
            and_(Notification.type == 'news', Notification.who_see != 'SL001')
        )
    ).order_by(Notification.created_at.desc())


def _format_notification(notification):
    return {
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


@initiate_bp.route('/kowida', methods=['GET'])
def get_kowida_initiate():
    """
    App initiate endpoint.
    Returns version, notifications, and offer flag.
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 15

        if page < 1:
            page = 1

        version_record = Version.query.filter_by(id=1).first()
        version = version_record.version if version_record else None

        notifications_query = _get_notifications_query()

        pagination = notifications_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        notifications_data = [
            _format_notification(notification) for notification in pagination.items
        ]

        return jsonify({
            'status': 'success',
            'message': 'Kowida initiate data retrieved successfully',
            'data': {
                'version': version,
                'notifications': notifications_data,
                'offer': False
            }
        }), 200

    except Exception as e:
        logger.error(f"Error retrieving kowida initiate data: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An error occurred while retrieving kowida initiate data',
            'error': str(e)
        }), 500
