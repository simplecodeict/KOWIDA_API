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
        
        # Try different image preprocessing techniques for better Korean text detection
        if use_preprocessing:
            # Method 1: Original image
            img_rgb1 = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Method 2: Grayscale with contrast enhancement
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            enhanced = cv2.convertScaleAbs(gray, alpha=1.5, beta=30)
            img_rgb2 = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
            
            # Method 3: Denoised image
            denoised = cv2.fastNlMeansDenoising(gray)
            img_rgb3 = cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB)
            
            # Method 4: Sharpened image
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            sharpened = cv2.filter2D(gray, -1, kernel)
            img_rgb4 = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)
            
            # Test all preprocessing methods and choose the best
            test_images = [img_rgb1, img_rgb2, img_rgb3, img_rgb4]
            best_image = img_rgb1
            best_detections = 0
            
            for test_img in test_images:
                try:
                    test_results = reader.readtext(test_img, detail=1)
                    detection_count = len([r for r in test_results if r[2] > 0.1])
                    if detection_count > best_detections:
                        best_detections = detection_count
                        best_image = test_img
                except:
                    continue
            
            pil_img = Image.fromarray(best_image)
        else:
            # Use original image
            pil_img = Image.open(image_path)
        
        # Perform OCR with multiple configurations
        results1 = reader.readtext(np.array(pil_img))
        results2 = reader.readtext(np.array(pil_img), paragraph=True)
        results3 = reader.readtext(np.array(pil_img), detail=1)
        
        # Use the configuration with most detections
        all_results = [results1, results2, results3]
        best_results = max(all_results, key=len)
        results = best_results
        
        # If still no results, try with very low confidence
        if len(results) == 0:
            results = reader.readtext(np.array(pil_img), detail=1)
            results = [(bbox, text, conf) for bbox, text, conf in results if conf > 0.1]
        
        # Extract text and confidence scores
        extracted_texts = []
        korean_text = ""
        english_text = ""
        
        # Use dynamic confidence threshold
        confidence_threshold = 0.1 if len(results) < 5 else 0.5
        
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
        
        # Clean up the descriptions
        korean_description = ' '.join(korean_text.strip().split())
        english_description = ' '.join(english_text.strip().split())
        all_description = ' '.join((korean_text + english_text).strip().split())
        
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
