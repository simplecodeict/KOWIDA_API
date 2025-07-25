from flask import Blueprint, jsonify
from models.base_amount import BaseAmount
import logging

logger = logging.getLogger(__name__)

base_amount_bp = Blueprint('base_amount', __name__)

@base_amount_bp.route('/base-amount', methods=['GET'])
def get_base_amount():
    """
    Get base amount data
    Returns all base amount records
    """
    try:
        logger.debug("=== Starting /base-amount endpoint ===")
        
        # Get first base amount
        base_amount = BaseAmount.query.first()
        
        if not base_amount:
            return jsonify({
                'status': 'error',
                'message': 'No base amount found'
            }), 404
        
        response_data = {
            'status': 'success',
            'data': {
                'id': base_amount.id,
                'amount': float(base_amount.amount) if base_amount.amount else 0
            }
        }
        
        logger.debug("Successfully retrieved base amount")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error in base-amount endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 



# this is for apple
@base_amount_bp.route('/base-data', methods=['GET'])
def get_base_amount_for_apple():
    """
    Get base amount data
    Returns all base amount records
    """
    try:
        logger.debug("=== Starting /base-amount endpoint ===")
        
        # Get first base amount
        base_amount = BaseAmount.query.first()
        
        if not base_amount:
            return jsonify({
                'status': 'error',
                'message': 'No base amount found'
            }), 404
        
        response_data = {
            'status': 'success',
            'data': {
                'id': base_amount.id,
                'amount': float(base_amount.amount) if base_amount.amount else 0
            }
        }
        
        logger.debug("Successfully retrieved base amount")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error in base-amount endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 