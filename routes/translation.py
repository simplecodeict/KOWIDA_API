"""
Translation API routes for Korean to English translation.
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
        "data": {
            "original_text": "Korean text",
            "translated_text": "English translation",
            "source_language": "Korean",
            "target_language": "English",
            "processing_time": 0.123,
            "model": "NLLB-200-distilled-600M"
        }
    }
    """
    try:
        # Log translation request
        logger.info("Translation request received")
        
        # Validate request
        if not request.is_json:
            return jsonify({
                'status': 'error',
                'message': 'Request must be JSON',
                'error_code': 'INVALID_CONTENT_TYPE'
            }), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required',
                'error_code': 'MISSING_BODY'
            }), 400
        
        # Extract text to translate
        text = data.get('text')
        if not text:
            return jsonify({
                'status': 'error',
                'message': 'Text field is required',
                'error_code': 'MISSING_TEXT'
            }), 400
        
        if not isinstance(text, str):
            return jsonify({
                'status': 'error',
                'message': 'Text must be a string',
                'error_code': 'INVALID_TEXT_TYPE'
            }), 400
        
        # Check text length
        if len(text.strip()) == 0:
            return jsonify({
                'status': 'error',
                'message': 'Text cannot be empty',
                'error_code': 'EMPTY_TEXT'
            }), 400
        
        if len(text) > 2000:  # Reasonable limit for API
            return jsonify({
                'status': 'error',
                'message': 'Text is too long. Maximum 2000 characters allowed',
                'error_code': 'TEXT_TOO_LONG'
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

@translation_bp.route('/translate/batch', methods=['POST'])
def translate_batch():
    """
    Translate multiple Korean texts to English in batch.
    
    Request body:
    {
        "texts": ["Korean text 1", "Korean text 2", ...],
        "use_cache": true (optional, default: true)
    }
    
    Returns:
    {
        "status": "success",
        "data": {
            "translations": [
                {
                    "original_text": "Korean text 1",
                    "translated_text": "English translation 1",
                    "processing_time": 0.123
                },
                ...
            ],
            "total_processing_time": 0.456,
            "successful_translations": 2,
            "failed_translations": 0
        }
    }
    """
    try:
        # Log batch translation request
        logger.info("Batch translation request received")
        
        # Validate request
        if not request.is_json:
            return jsonify({
                'status': 'error',
                'message': 'Request must be JSON',
                'error_code': 'INVALID_CONTENT_TYPE'
            }), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'Request body is required',
                'error_code': 'MISSING_BODY'
            }), 400
        
        # Extract texts to translate
        texts = data.get('texts')
        if not texts:
            return jsonify({
                'status': 'error',
                'message': 'Texts field is required',
                'error_code': 'MISSING_TEXTS'
            }), 400
        
        if not isinstance(texts, list):
            return jsonify({
                'status': 'error',
                'message': 'Texts must be an array',
                'error_code': 'INVALID_TEXTS_TYPE'
            }), 400
        
        if len(texts) == 0:
            return jsonify({
                'status': 'error',
                'message': 'Texts array cannot be empty',
                'error_code': 'EMPTY_TEXTS'
            }), 400
        
        if len(texts) > 50:  # Reasonable batch limit
            return jsonify({
                'status': 'error',
                'message': 'Too many texts. Maximum 50 texts allowed per batch',
                'error_code': 'TOO_MANY_TEXTS'
            }), 400
        
        # Get cache preference
        use_cache = data.get('use_cache', True)
        if not isinstance(use_cache, bool):
            use_cache = True
        
        # Process batch translation
        import time
        start_time = time.time()
        
        translations = []
        successful_count = 0
        failed_count = 0
        
        for i, text in enumerate(texts):
            if not isinstance(text, str):
                translations.append({
                    'index': i,
                    'original_text': str(text),
                    'translated_text': '',
                    'error': 'Text must be a string',
                    'processing_time': 0
                })
                failed_count += 1
                continue
            
            if len(text.strip()) == 0:
                translations.append({
                    'index': i,
                    'original_text': text,
                    'translated_text': '',
                    'error': 'Text cannot be empty',
                    'processing_time': 0
                })
                failed_count += 1
                continue
            
            if len(text) > 2000:
                translations.append({
                    'index': i,
                    'original_text': text,
                    'translated_text': '',
                    'error': 'Text is too long. Maximum 2000 characters allowed',
                    'processing_time': 0
                })
                failed_count += 1
                continue
            
            # Translate individual text
            result = translation_service.translate(text, use_cache=use_cache)
            
            if result['success']:
                translations.append({
                    'index': i,
                    'english_text': result['translated_text'],
                    'status': 'success',
                    'response_time': result['processing_time']
                })
                successful_count += 1
            else:
                translations.append({
                    'index': i,
                    'english_text': '',
                    'status': 'error',
                    'response_time': result['processing_time']
                })
                failed_count += 1
        
        total_processing_time = time.time() - start_time
        
        return jsonify({
            'status': 'success',
            'translations': translations,
            'response_time': round(total_processing_time, 3)
        }), 200
        
    except Exception as e:
        logger.error(f"Batch translation API error: {e}")
        return jsonify({
            'status': 'error',
            'translations': [],
            'response_time': 0
        }), 500

@translation_bp.route('/translate/model-info', methods=['GET'])
def get_model_info():
    """
    Get information about the translation model.
    
    Returns:
    {
        "status": "success",
        "data": {
            "model_name": "facebook/nllb-200-distilled-600M",
            "initialized": true,
            "device": "cuda",
            "cache_size": 150,
            "cache_maxsize": 1000
        }
    }
    """
    try:
        model_info = translation_service.get_model_info()
        
        return jsonify({
            'status': 'success',
            'message': 'Model information retrieved successfully',
            'data': model_info
        }), 200
        
    except Exception as e:
        logger.error(f"Model info API error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to retrieve model information',
            'error_code': 'MODEL_INFO_ERROR'
        }), 500

@translation_bp.route('/translate/clear-cache', methods=['POST'])
def clear_translation_cache():
    """
    Clear the translation cache.
    
    Returns:
    {
        "status": "success",
        "message": "Translation cache cleared successfully"
    }
    """
    try:
        translation_service.clear_cache()
        
        return jsonify({
            'status': 'success',
            'message': 'Translation cache cleared successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Clear cache API error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to clear translation cache',
            'error_code': 'CLEAR_CACHE_ERROR'
        }), 500

@translation_bp.route('/translate/cache-stats', methods=['GET'])
def get_cache_stats():
    """
    Get translation cache statistics for monitoring performance.
    
    Returns:
    {
        "status": "success",
        "data": {
            "hits": 150,
            "misses": 50,
            "current_size": 200,
            "max_size": 5000,
            "hit_rate": 0.75
        }
    }
    """
    try:
        cache_stats = translation_service.get_cache_stats()
        model_info = translation_service.get_model_info()
        
        return jsonify({
            'status': 'success',
            'message': 'Cache statistics retrieved successfully',
            'data': {
                'cache_stats': cache_stats,
                'model_info': model_info
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Cache stats API error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to retrieve cache statistics',
            'error_code': 'CACHE_STATS_ERROR'
        }), 500
