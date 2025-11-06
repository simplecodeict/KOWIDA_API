from flask import Blueprint, request, jsonify
from extensions import db
from models.offer import Offer
from schemas import OfferSchema
from sqlalchemy.exc import IntegrityError
from marshmallow import ValidationError
import logging

logger = logging.getLogger(__name__)

offer_bp = Blueprint('offer', __name__)

@offer_bp.route('/offers', methods=['POST'])
def create_offer():
    """
    Create a new offer
    """
    schema = OfferSchema()
    try:
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
        
        logger.info(f"Received offer creation data: {data}")
        
        # Create new offer
        try:
            new_offer = Offer(
                message=data['message'],
                base_value=data['base_value'],
                discount=data['discount'],
                end_date=data['end_date'],
                is_active=data.get('is_active', True)
            )
            
            db.session.add(new_offer)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Offer created successfully',
                'data': {
                    'offer': {
                        'id': new_offer.id,
                        'message': new_offer.message,
                        'base_value': float(new_offer.base_value),
                        'discount': float(new_offer.discount),
                        'end_date': new_offer.end_date.isoformat() if new_offer.end_date else None,
                        'is_active': new_offer.is_active,
                        'created_at': new_offer.created_at.isoformat() if new_offer.created_at else None,
                        'updated_at': new_offer.updated_at.isoformat() if new_offer.updated_at else None
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
        logger.error(f"Unexpected error during offer creation: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred during offer creation',
            'error_code': 'OFFER_CREATION_ERROR'
        }), 500

@offer_bp.route('/offers', methods=['GET'])
def get_first_offer():
    """
    Get the very first active offer
    """
    try:
        logger.debug("=== Starting /offers GET endpoint ===")
        
        # Get first active offer ordered by id
        offer = Offer.query.filter_by(is_active=True).order_by(Offer.id.asc()).first()
        
        if not offer:
            return jsonify({
                'status': 'error',
                'message': 'No active offer found',
                'error_code': 'OFFER_NOT_FOUND'
            }), 404
        
        response_data = {
            'status': 'success',
            'data': {
                'offer': {
                    'id': offer.id,
                    'message': offer.message,
                    'base_value': float(offer.base_value) if offer.base_value else 0,
                    'discount': float(offer.discount) if offer.discount else 0,
                    'end_date': offer.end_date.isoformat() if offer.end_date else None,
                    'is_active': offer.is_active,
                    'created_at': offer.created_at.isoformat() if offer.created_at else None,
                    'updated_at': offer.updated_at.isoformat() if offer.updated_at else None
                }
            }
        }
        
        logger.debug("Successfully retrieved first active offer")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error in offers GET endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e),
            'error_code': 'OFFER_FETCH_ERROR'
        }), 500

@offer_bp.route('/offers/all', methods=['GET'])
def get_all_offers():
    """
    Get all offers
    """
    try:
        logger.debug("=== Starting /offers/all GET endpoint ===")
        
        # Get all offers ordered by id
        offers = Offer.query.order_by(Offer.id.asc()).all()
        
        offers_list = []
        for offer in offers:
            offers_list.append({
                'id': offer.id,
                'message': offer.message,
                'base_value': float(offer.base_value) if offer.base_value else 0,
                'discount': float(offer.discount) if offer.discount else 0,
                'end_date': offer.end_date.isoformat() if offer.end_date else None,
                'is_active': offer.is_active,
                'created_at': offer.created_at.isoformat() if offer.created_at else None,
                'updated_at': offer.updated_at.isoformat() if offer.updated_at else None
            })
        
        response_data = {
            'status': 'success',
            'data': {
                'offers': offers_list,
                'total': len(offers_list)
            }
        }
        
        logger.debug(f"Successfully retrieved {len(offers_list)} offers")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error in offers/all GET endpoint: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e),
            'error_code': 'OFFER_FETCH_ERROR'
        }), 500

@offer_bp.route('/offers/<int:offer_id>/deactivate', methods=['PUT'])
def deactivate_offer(offer_id):
    """
    Deactivate an offer by setting is_active to false
    """
    try:
        logger.debug(f"=== Starting deactivate offer endpoint for ID: {offer_id} ===")
        
        # Find the offer by ID
        offer = Offer.query.get(offer_id)
        
        if not offer:
            return jsonify({
                'status': 'error',
                'message': 'Offer not found',
                'error_code': 'OFFER_NOT_FOUND'
            }), 404
        
        # Check if already inactive
        if not offer.is_active:
            return jsonify({
                'status': 'error',
                'message': 'Offer is already inactive',
                'error_code': 'OFFER_ALREADY_INACTIVE'
            }), 400
        
        # Deactivate the offer
        try:
            offer.is_active = False
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Offer deactivated successfully',
                'data': {
                    'offer': {
                        'id': offer.id,
                        'message': offer.message,
                        'base_value': float(offer.base_value) if offer.base_value else 0,
                        'discount': float(offer.discount) if offer.discount else 0,
                        'end_date': offer.end_date.isoformat() if offer.end_date else None,
                        'is_active': offer.is_active,
                        'created_at': offer.created_at.isoformat() if offer.created_at else None,
                        'updated_at': offer.updated_at.isoformat() if offer.updated_at else None
                    }
                }
            }), 200
            
        except IntegrityError as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': 'Database integrity error occurred',
                'error_code': 'DATABASE_ERROR'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in deactivate offer endpoint: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred while deactivating offer',
            'error_code': 'OFFER_DEACTIVATION_ERROR'
        }), 500

