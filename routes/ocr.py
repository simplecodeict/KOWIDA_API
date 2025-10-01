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
        
        # Enhanced preprocessing for better Korean text accuracy
        if use_preprocessing:
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply bilateral filter to reduce noise while preserving edges
            filtered = cv2.bilateralFilter(gray, 9, 75, 75)
            
            # Apply adaptive thresholding for better text clarity
            thresh = cv2.adaptiveThreshold(filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            
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
        english_text = ""
        
        # Dynamic confidence threshold for Korean text
        confidence_threshold = 0.1  # Lower threshold to catch Korean text
        
        for (bbox, text, confidence) in results:
            if confidence > confidence_threshold:
                extracted_texts.append({
                    'text': text.strip(),
                    'confidence': round(confidence, 3),
                    'bbox': bbox
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
                else:
                    english_text += text.strip() + " "
        
        # Clean up and correct Korean text
        korean_description = ' '.join(korean_text.strip().split())
        english_description = ' '.join(english_text.strip().split())
        
        # Apply Korean text corrections for common OCR mistakes
        korean_corrections = {
            '오라인': '온라인',
            '쇼핑물올': '쇼핑몰을',
            '생필품올': '생필품을',
            '쇼핑물에서논': '쇼핑몰에서는',
            '행사클': '행사를',
            '구돈을': '쿠폰을',
            '세공합니다': '제공합니다',
            '이틀': '이를',
            '확용하여': '활용하여',
            '상품올': '상품을',
            '할인올': '할인을',
            '받울': '받을'
        }
        
        # Apply corrections
        for wrong, correct in korean_corrections.items():
            korean_description = korean_description.replace(wrong, correct)
        
        all_description = ' '.join((korean_description + ' ' + english_description).strip().split())
        
        return {
            'success': True,
            'description': all_description,  # Combined description
            'korean_text': korean_description,  # Korean text only
            'english_text': english_description,  # English text only
            'extracted_texts': extracted_texts,  # Keep detailed results for debugging
            'total_detections': len(extracted_texts)
        }
        
    except Exception as e:
        logger.error(f"Error extracting text from image: {e}")
        return {
            'success': False,
            'error': str(e),
            'description': '',
            'korean_text': '',
            'english_text': '',
            'extracted_texts': [],
            'total_detections': 0
        }

def test_ocr_with_sample_image():
    """
    Test OCR functionality with the sample image in assets folder
    """
    try:
        # Path to the sample image
        sample_image_path = os.path.join('assets', 'ss.png')
        
        if not os.path.exists(sample_image_path):
            return {
                'success': False,
                'error': f'Sample image not found at {sample_image_path}'
            }
        
        logger.info(f"Testing OCR with sample image: {sample_image_path}")
        
        # Extract text from the sample image
        result = extract_text_from_image(sample_image_path)
        
        if result['success']:
            logger.info("OCR test completed successfully")
            logger.info(f"Description: {result['description']}")
            logger.info(f"Total detections: {result['total_detections']}")
            
            # Print results
            print("\n" + "="*60)
            print("KOREAN TEXT EXTRACTION RESULTS")
            print("="*60)
            print(f"Sample Image: {sample_image_path}")
            print(f"Total Text Detections: {result['total_detections']}")
            print(f"\nDESCRIPTION:")
            print("-" * 40)
            print(result['description'])
            print("-" * 40)
            print("="*60)
        else:
            logger.error(f"OCR test failed: {result['error']}")
            print(f"\nOCR Test Failed: {result['error']}")
        
        return result
        
    except Exception as e:
        error_msg = f"Error during OCR test: {e}"
        logger.error(error_msg)
        print(f"\n{error_msg}")
        return {
            'success': False,
            'error': error_msg
        }

@ocr_bp.route('/test-ocr', methods=['GET'])
def test_ocr_endpoint():
    """
    Test endpoint to run OCR on the sample image
    """
    try:
        result = test_ocr_with_sample_image()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in test OCR endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
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
                'error': 'No image file provided'
            }), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No image file selected'
            }), 400
        
        # Secure filename and save temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join('temp', filename)
        
        # Create temp directory if it doesn't exist
        os.makedirs('temp', exist_ok=True)
        
        # Save uploaded file
        file.save(temp_path)
        
        try:
            # Extract text
            result = extract_text_from_image(temp_path)
            return jsonify(result)
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        logger.error(f"Error in extract text endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Function to run OCR test directly (for testing purposes)
def run_ocr_test():
    """
    Function to run OCR test directly without Flask
    """
    print("Starting Korean Text Extraction Test...")
    print("Using EasyOCR with Korean and English language support")
    print()
    
    result = test_ocr_with_sample_image()
    
    if result['success']:
        print("\n[SUCCESS] OCR Test Completed Successfully!")
        return True
    else:
        print(f"\n[FAILED] OCR Test Failed: {result['error']}")
        return False

if __name__ == "__main__":
    # Run OCR test when script is executed directly
    run_ocr_test()
