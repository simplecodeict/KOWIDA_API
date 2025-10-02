"""
OCR Routes for Korean Text Extraction
This module handles image processing and text extraction using EasyOCR
"""

import os
import logging
import time
from flask import Blueprint, request, jsonify, current_app
import easyocr
from PIL import Image
import cv2
import numpy as np
from werkzeug.utils import secure_filename
from ocr_corrections import apply_all_corrections, get_correction_stats

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
ocr_bp = Blueprint('ocr', __name__)

# Initialize EasyOCR reader for Korean and English
# This will be initialized once when the module is imported
reader = None

# Note: Removed file-based caching since we now process images directly from memory

def initialize_reader():
    """Initialize EasyOCR reader with optimized settings"""
    global reader
    if reader is None:
        try:
            # Initialize EasyOCR with optimized settings for speed
            reader = easyocr.Reader(
                ['ko', 'en'], 
                gpu=False,  # Set gpu=True if you have CUDA
                verbose=False,  # Reduce logging for speed
                quantize=True,  # Use quantization for faster processing
                model_storage_directory=None,  # Use default model storage
                download_enabled=True
            )
            logger.info("EasyOCR initialized successfully with Korean and English support")
            return True
        except ImportError as e:
            logger.error(f"EasyOCR not installed: {e}")
            reader = None
            return False
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            reader = None
            return False
    return True

# Removed image hashing function since we no longer cache files

def validate_image_array(img_array):
    """Validate image array before processing"""
    try:
        if img_array is None:
            return False, "No image data provided"
        
        if img_array.size == 0:
            return False, "Empty image data"
        
        # Check image dimensions
        if len(img_array.shape) < 2:
            return False, "Invalid image format"
        
        height, width = img_array.shape[:2]
        if width < 10 or height < 10:
            return False, "Image too small (minimum 10x10 pixels)"
        
        if width > 5000 or height > 5000:
            return False, "Image too large (maximum 5000x5000 pixels)"
        
        return True, "Valid image"
        
    except Exception as e:
        return False, f"Error validating image: {str(e)}"

# Removed file-based preprocessing function - now using in-memory processing only

def extract_text_from_image_memory(img_array, use_preprocessing=True):
    """
    Extract Korean text from image array (in-memory processing)
    """
    start_time = time.time()
    
    if not initialize_reader():
        return {
            'success': False,
            'error': "Failed to initialize OCR engine",
            'korean_text': '',
            'total_detections': 0
        }
    
    try:
        # Validate image array
        is_valid, error_msg = validate_image_array(img_array)
        if not is_valid:
            return {
                'success': False,
                'error': f"Image validation failed: {error_msg}",
                'korean_text': '',
                'total_detections': 0
            }
        
        # Optimized preprocessing
        if use_preprocessing:
            # Convert to grayscale
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
            
            # Optimize image size for processing speed
            height, width = gray.shape
            if width > 1200:  # Increased threshold for better quality
                scale = 1200 / width
                new_width = int(width * scale)
                new_height = int(height * scale)
                gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
            # Apply optimized preprocessing pipeline
            # Use bilateral filter for noise reduction while preserving edges
            filtered = cv2.bilateralFilter(gray, 9, 75, 75)
            
            # Apply CLAHE for better contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(filtered)
            
            # Apply adaptive thresholding
            thresh = cv2.adaptiveThreshold(
                enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            
            # Minimal morphological operations for speed
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            # Convert back to RGB for EasyOCR
            img_rgb = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2RGB)
            pil_img = Image.fromarray(img_rgb)
        else:
            # Use original image
            pil_img = Image.fromarray(cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB))
        
        # Optimized OCR with better parameters
        results = reader.readtext(
            np.array(pil_img), 
            detail=1,
            paragraph=False,  # Disable paragraph grouping for speed
            width_ths=0.7,    # Optimize width threshold
            height_ths=0.7    # Optimize height threshold
        )
        
        # Extract text and confidence scores
        extracted_texts = []
        korean_text = ""
        
        # Very low confidence threshold for large/complex images
        confidence_threshold = 0.05  # Very low threshold to catch more text
        
        for (bbox, text, confidence) in results:
            if confidence > confidence_threshold:
                # Convert NumPy types to native Python types for JSON serialization
                converted_bbox = []
                for point in bbox:
                    converted_point = [float(coord) for coord in point]
                    converted_bbox.append(converted_point)
                
                extracted_texts.append({
                    'text': text.strip(),
                    'confidence': round(float(confidence), 3),
                    'bbox': converted_bbox
                })
                
                # Check if text contains Korean characters (expanded range)
                has_korean = any(
                    '\uac00' <= char <= '\ud7af' or  # Hangul Syllables
                    '\u1100' <= char <= '\u11ff' or  # Hangul Jamo
                    '\u3130' <= char <= '\u318f'     # Hangul Compatibility Jamo
                    for char in text
                )
                
                if has_korean:
                    korean_text += text.strip() + " "
        
        # Clean up text
        korean_description = ' '.join(korean_text.strip().split())
        
        # Apply comprehensive corrections using the corrections module
        try:
            korean_description, _ = apply_all_corrections(
                korean_description, ""  # Pass empty string for English - Korean only mode
            )
        except Exception as e:
            logger.warning(f"Failed to apply corrections: {e}")
            # Continue without corrections if they fail
        
        # Prepare result
        result = {
            'success': True,
            'korean_text': korean_description,
            'total_detections': len(extracted_texts),
            'processing_time': round(time.time() - start_time, 3)
        }
        
        return result
        
    except MemoryError as e:
        logger.error(f"Memory error during OCR processing: {e}")
        return {
            'success': False,
            'error': "Image too large or complex for processing",
            'korean_text': '',
            'total_detections': 0
        }
    except Exception as e:
        logger.error(f"Error extracting text from image: {e}")
        return {
            'success': False,
            'error': "Failed to process image",
            'korean_text': '',
            'total_detections': 0
        }

# Removed file-based extraction function - now using in-memory processing only



# Removed cache endpoints since we now process images directly from memory

@ocr_bp.route('/corrections/stats', methods=['GET'])
def corrections_stats():
    """
    Get statistics about available text corrections
    """
    try:
        from ocr_corrections import get_correction_stats
        stats = get_correction_stats()
        return jsonify({
            'success': True,
            'corrections': stats
        })
    except ImportError as e:
        logger.error(f"Failed to import corrections module: {e}")
        return jsonify({
            'success': False,
            'error': 'Corrections module not available'
        }), 500
    except Exception as e:
        logger.error(f"Error getting correction stats: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to retrieve correction statistics'
        }), 500

@ocr_bp.route('/corrections/add', methods=['POST'])
def add_correction():
    """
    Add new text corrections dynamically
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400
        
        korean_wrong = data.get('korean_wrong')
        korean_correct = data.get('korean_correct')
        
        # Validate required fields
        if not korean_wrong or not korean_correct:
            return jsonify({
                'success': False,
                'error': 'Both korean_wrong and korean_correct are required'
            }), 400
        
        # Validate input
        if not isinstance(korean_wrong, str) or not isinstance(korean_correct, str):
            return jsonify({
                'success': False,
                'error': 'Korean correction values must be strings'
            }), 400
        
        if len(korean_wrong.strip()) == 0 or len(korean_correct.strip()) == 0:
            return jsonify({
                'success': False,
                'error': 'Korean correction values cannot be empty'
            }), 400
        
        # Import the add_correction function
        try:
            from ocr_corrections import add_correction
        except ImportError as e:
            logger.error(f"Failed to import corrections module: {e}")
            return jsonify({
                'success': False,
                'error': 'Corrections module not available'
            }), 500
        
        # Add the correction
        add_correction(
            korean_wrong=korean_wrong.strip(),
            korean_correct=korean_correct.strip(),
            english_wrong=None,
            english_correct=None
        )
        
        return jsonify({
            'success': True,
            'message': 'Korean correction added successfully',
            'added': {
                'korean': f"{korean_wrong.strip()} -> {korean_correct.strip()}"
            }
        })
        
    except Exception as e:
        logger.error(f"Error adding correction: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to add correction'
        }), 500

@ocr_bp.route('/extract-text', methods=['POST'])
def extract_text_endpoint():
    """
    Extract text from uploaded image with optimized processing and caching
    """
    start_time = time.time()
    
    try:
        # Check if image file is provided
        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No image file provided',
                'korean_text': ''
            }), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No image file selected',
                'korean_text': ''
            }), 400
        
        # Enhanced file validation
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'}
        file_extension = None
        
        if '.' in file.filename:
            file_extension = file.filename.rsplit('.', 1)[1].lower()
        
        if not file_extension or file_extension not in allowed_extensions:
            return jsonify({
                'success': False,
                'error': f'Invalid file type. Supported formats: {", ".join(allowed_extensions)}',
                'korean_text': ''
            }), 400
        
        # Check file size before saving
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            return jsonify({
                'success': False,
                'error': 'File too large. Maximum size is 10MB',
                'korean_text': ''
            }), 400
        
        if file_size == 0:
            return jsonify({
                'success': False,
                'error': 'Empty file provided',
                'korean_text': ''
            }), 400
        
        # Process image directly from memory - no file saving needed
        try:
            # Read image data directly from uploaded file
            file.seek(0)  # Reset file pointer to beginning
            image_data = file.read()
            
            # Convert bytes to numpy array for OpenCV
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return jsonify({
                    'success': False,
                    'error': 'Invalid image format or corrupted file',
                    'korean_text': ''
                }), 400
            
            logger.info(f"Processing image directly from memory: {file.filename} ({file_size} bytes)")
            
        except Exception as e:
            logger.error(f"Failed to process image from memory: {e}")
            return jsonify({
                'success': False,
                'error': 'Failed to process uploaded image',
                'korean_text': ''
            }), 500
        
        # Process image directly from memory - no file operations needed
        result = extract_text_from_image_memory(img)
        
        if not result['success']:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to extract text from image'),
                'korean_text': ''
            }), 500
        
        # Enhanced response with processing information
        response = {
            'success': True,
            'korean_text': str(result.get('korean_text', '')),
            'total_detections': int(result.get('total_detections', 0)),
            'processing_time': round(time.time() - start_time, 3)
        }
        
        logger.info(f"OCR completed in {response['processing_time']}s for {file.filename}")
        return jsonify(response)
                
    except Exception as e:
        logger.error(f"Error in extract text endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'korean_text': ''
        }), 500

