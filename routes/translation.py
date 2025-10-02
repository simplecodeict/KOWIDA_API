"""
Translation API routes for Korean to English and Sinhala translation.
Provides unlimited, free translation services using Facebook's NLLB model.
"""

from flask import Blueprint, request, jsonify
import logging
from services.translation_service import translation_service

logger = logging.getLogger(__name__)

# Create blueprint
translation_bp = Blueprint('translation', __name__)

@translation_bp.route('/translate', methods=['POST'])
def translate_text():
    """
    Translate Korean text to English.
    
    Request body:
    {
        "text": "Korean text to translate",
        "use_cache": true (optional, default: true)
    }
    
    Returns:
    {
        "status": "success",
        "english_text": "English translation",
        "response_time": 0.123
    }
    """
    try:
        # Log translation request
        logger.info("Translation request received")
        
        # Validate request
        if not request.is_json:
            return jsonify({
                'status': 'error',
                'english_text': '',
                'response_time': 0
            }), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'english_text': '',
                'response_time': 0
            }), 400
        
        # Extract text to translate
        text = data.get('text')
        if not text:
            return jsonify({
                'status': 'error',
                'english_text': '',
                'response_time': 0
            }), 400
        
        if not isinstance(text, str):
            return jsonify({
                'status': 'error',
                'english_text': '',
                'response_time': 0
            }), 400
        
        # Check text length
        if len(text.strip()) == 0:
            return jsonify({
                'status': 'error',
                'english_text': '',
                'response_time': 0
            }), 400
        
        if len(text) > 2000:  # Reasonable limit for API
            return jsonify({
                'status': 'error',
                'english_text': '',
                'response_time': 0
            }), 400
        
        # Get cache preference
        use_cache = data.get('use_cache', True)
        if not isinstance(use_cache, bool):
            use_cache = True
        
        # Perform translation
        logger.info(f"Translating text: {text[:50]}...")
        result = translation_service.translate(text, use_cache=use_cache)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'english_text': result['translated_text'],
                'response_time': result['processing_time']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'english_text': '',
                'response_time': result['processing_time']
            }), 500
            
    except Exception as e:
        logger.error(f"Translation API error: {e}")
        return jsonify({
            'status': 'error',
            'english_text': '',
            'response_time': 0
        }), 500

@translation_bp.route('/translate/both', methods=['POST'])
def translate_korean_to_both():
    """
    Translate Korean text to both English and Sinhala.
    
    Request body:
    {
        "text": "Korean text to translate",
        "use_cache": true (optional, default: true)
    }
    
    Returns:
    {
        "status": "success",
        "english_text": "English translation",
        "sinhala_text": "Sinhala translation",
        "response_time": 0.123
    }
    """
    try:
        # Log translation request
        logger.info("Korean to both languages translation request received")
        
        # Validate request
        if not request.is_json:
            return jsonify({
                'status': 'error',
                'english_text': '',
                'sinhala_text': '',
                'response_time': 0
            }), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'english_text': '',
                'sinhala_text': '',
                'response_time': 0
            }), 400
        
        # Extract text to translate
        text = data.get('text')
        if not text:
            return jsonify({
                'status': 'error',
                'english_text': '',
                'sinhala_text': '',
                'response_time': 0
            }), 400
        
        if not isinstance(text, str):
            return jsonify({
                'status': 'error',
                'english_text': '',
                'sinhala_text': '',
                'response_time': 0
            }), 400
        
        # Check text length
        if len(text.strip()) == 0:
            return jsonify({
                'status': 'error',
                'english_text': '',
                'sinhala_text': '',
                'response_time': 0
            }), 400
        
        if len(text) > 2000:  # Reasonable limit for API
            return jsonify({
                'status': 'error',
                'english_text': '',
                'sinhala_text': '',
                'response_time': 0
            }), 400
        
        # Get cache preference
        use_cache = data.get('use_cache', True)
        if not isinstance(use_cache, bool):
            use_cache = True
        
        # Perform translation
        logger.info(f"Translating Korean text to both languages: {text[:50]}...")
        result = translation_service.translate_korean_to_both(text, use_cache=use_cache)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'english_text': result['english_text'],
                'sinhala_text': result['sinhala_text'],
                'response_time': result['processing_time']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'english_text': '',
                'sinhala_text': '',
                'response_time': result['processing_time']
            }), 500
            
    except Exception as e:
        logger.error(f"Korean to both translation API error: {e}")
        return jsonify({
            'status': 'error',
            'english_text': '',
            'sinhala_text': '',
            'response_time': 0
        }), 500