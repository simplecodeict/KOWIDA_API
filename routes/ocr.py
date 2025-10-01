"""
OCR Routes for Korean Text Extraction
This module handles image processing and text extraction using EasyOCR
"""

import os
import logging
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

def initialize_reader():
    """Initialize EasyOCR reader"""
    global reader
    if reader is None:
        try:
            # Initialize EasyOCR with Korean and English languages
            reader = easyocr.Reader(['ko', 'en'], gpu=False)  # Set gpu=True if you have CUDA
            logger.info("EasyOCR initialized successfully with Korean and English support")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {e}")
            reader = None
            return False
    return True

def preprocess_image(image_path):
    """
    Preprocess image to improve OCR accuracy
    """
    try:
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Could not read image")
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to clean up the image
        kernel = np.ones((1, 1), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    except Exception as e:
        logger.error(f"Error preprocessing image: {e}")
        return None

def extract_text_from_image(image_path, use_preprocessing=True):
    """
    Extract Korean text from image using EasyOCR with improved detection
    """
    if not initialize_reader():
        raise Exception("Failed to initialize EasyOCR reader")
    
    try:
        # Read and process the image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Could not read the image")
        
        # Enhanced preprocessing for better Korean text accuracy on large/unclear images
        if use_preprocessing:
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Resize image if it's too large (for better processing)
            height, width = gray.shape
            if width > 1000:
                scale = 1000 / width
                new_width = int(width * scale)
                new_height = int(height * scale)
                gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
            # Apply lighter preprocessing to preserve more text
            # Apply bilateral filter to reduce noise while preserving edges
            filtered = cv2.bilateralFilter(gray, 9, 75, 75)
            
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) for better contrast
            clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8,8))  # Reduced clip limit
            enhanced = clahe.apply(filtered)
            
            # Apply adaptive thresholding for better text clarity
            thresh = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            
            # Apply morphological operations to clean up text
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            # Convert back to RGB for EasyOCR
            img_rgb = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2RGB)
            pil_img = Image.fromarray(img_rgb)
        else:
            # Use original image
            pil_img = Image.open(image_path)
        
        # Fast OCR - use optimized configuration directly
        results = reader.readtext(np.array(pil_img), detail=1)
        
        # Extract text and confidence scores
        extracted_texts = []
        korean_text = ""
        # english_text = ""  # Commented out - Korean only mode
        
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
                # else:
                #     english_text += text.strip() + " "  # Commented out - Korean only mode
        
        # Clean up text
        korean_description = ' '.join(korean_text.strip().split())
        
        # Apply comprehensive corrections using the corrections module
        korean_description, _ = apply_all_corrections(
            korean_description, ""  # Pass empty string for English - Korean only mode
        )
        
        return {
            'success': True,
            'korean_text': korean_description,
            'total_detections': len(extracted_texts)
        }
        
    except Exception as e:
        logger.error(f"Error extracting text from image: {e}")
        return {
            'success': False,
            'error': str(e),
            'korean_text': '',
            'total_detections': 0
        }



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
    Extract text from uploaded image
    """
    try:
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
        
        # Validate file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff'}
        if not ('.' in file.filename and 
                file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Please upload an image file (PNG, JPG, JPEG, GIF, BMP, TIFF)',
                'korean_text': ''
            }), 400
        
        # Secure filename and save temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join('temp', filename)
        
        # Create temp directory if it doesn't exist
        try:
            os.makedirs('temp', exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create temp directory: {e}")
            return jsonify({
                'success': False,
                'error': 'Failed to create temporary directory',
                'korean_text': ''
            }), 500
        
        # Save uploaded file
        try:
            file.save(temp_path)
        except Exception as e:
            logger.error(f"Failed to save uploaded file: {e}")
            return jsonify({
                'success': False,
                'error': 'Failed to save uploaded file',
                'korean_text': ''
            }), 500
        
        try:
            # Initialize OCR reader if not already done
            if not initialize_reader():
                return jsonify({
                    'success': False,
                    'error': 'Failed to initialize OCR engine',
                    'korean_text': ''
                }), 500
            
            # Extract text
            result = extract_text_from_image(temp_path)
            
            if not result['success']:
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Failed to extract text from image'),
                    'korean_text': ''
                }), 500
            
            # Simplified response with only Korean text
            response = {
                'success': True,
                'korean_text': str(result.get('korean_text', '')),
                'total_detections': int(result.get('total_detections', 0))
            }
            
            return jsonify(response)
            
        except Exception as e:
            logger.error(f"Error during text extraction: {e}")
            return jsonify({
                'success': False,
                'error': 'Failed to process image',
                'korean_text': ''
            }), 500
        finally:
            # Clean up temporary file
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_path}: {e}")
                
    except Exception as e:
        logger.error(f"Error in extract text endpoint: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'korean_text': ''
        }), 500

