from flask import Blueprint, jsonify, request
from models.version import Version
from extensions import db
from marshmallow import ValidationError
from schemas import VersionCreateSchema, VersionUpdateSchema
import logging

logger = logging.getLogger(__name__)

version_bp = Blueprint('version', __name__)

@version_bp.route('/version', methods=['POST'])
def create_version():
    """
    Create a new version
    """
    schema = VersionCreateSchema()
    try:
        # Validate request data
        data = schema.load(request.get_json())
        
        # Check if version with id=1 already exists
        existing_version = Version.query.filter_by(id=1).first()
        if existing_version:
            return jsonify({
                'status': 'error',
                'message': 'Version with id=1 already exists. Use update endpoint to modify it.'
            }), 400
        
        # Create new version
        version = Version(version=data['version'])
        db.session.add(version)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Version created successfully',
            'data': {
                'id': version.id,
                'version': version.version
            }
        }), 201
        
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': 'Validation error',
            'errors': e.messages
        }), 400
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating version: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@version_bp.route('/version', methods=['GET'])
def get_version():
    """
    Get version with id=1
    """
    try:
        # Get version with id=1
        version = Version.query.filter_by(id=1).first()
        
        if not version:
            return jsonify({
                'status': 'error',
                'message': 'Version not found'
            }), 404
        
        return jsonify({
            'status': 'success',
            'data': {
                'id': version.id,
                'version': version.version
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting version: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@version_bp.route('/version', methods=['PUT'])
def update_version():
    """
    Update version with id=1
    """
    schema = VersionUpdateSchema()
    try:
        # Validate request data
        data = schema.load(request.get_json())
        
        # Get version with id=1
        version = Version.query.filter_by(id=1).first()
        
        if not version:
            return jsonify({
                'status': 'error',
                'message': 'Version not found. Use create endpoint to create a new version.'
            }), 404
        
        # Update version
        version.version = data['version']
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Version updated successfully',
            'data': {
                'id': version.id,
                'version': version.version
            }
        }), 200
        
    except ValidationError as e:
        return jsonify({
            'status': 'error',
            'message': 'Validation error',
            'errors': e.messages
        }), 400
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating version: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

