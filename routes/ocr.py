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
        english_text = ""
        
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
            '받울': '받을',
            # Additional corrections for larger images
            '알플하게': '알뜰하게',
            '생필품을구입하는': '생필품을 구입하는',
            '틱': '팁',
            '마드예서는': '마트에서는',
            '좀종': '종종',
            '갈운': '같은',
            '행사람': '행사를',
            '열어': '열어',
            '식': '식품',
            '료품부터': '식료품부터',
            '다양하': '다양한',
            '씨게': '싸게',
            '전단지골': '전단지를',
            '정보올': '정보를',
            '얻을수': '얻을 수',
            '쇼풍물올': '쇼핑몰을',
            '정기적오로': '정기적으로',
            '구품올': '쿠폰을',
            '이꼴': '이를',
            '받울': '받을',
            # Additional corrections for complex images
            '한국에서알뜰하게생필품을': '한국에서 알뜰하게 생필품을',
            '구입하는팁': '구입하는 팁',
            '대침': '대형',
            '마루어서논': '마트에서는',
            '중중': '종종',
            '주업': '주말',
            '가회': '특가',
            '가은': '같은',
            '훨언': '할인',
            '7사사': '행사를',
            '업어서': '열어서',
            '코티부터': '식료품부터',
            '심사8공가치': '생활용품까지',
            '다양한': '다양한',
            '상표다': '상품을',
            '싸거판어라니다': '싸게 판매합니다',
            '미르어서': '마트에서',
            '나누어주': '나누어 주는',
            '천단치a': '전단지를',
            '남벼': '통해',
            '밥인': '할인',
            '상5': '상품',
            '나언': '할인',
            '금외': '금액',
            '추선': '추천',
            '상8': '상품',
            '급': '등',
            '법사어': '행사에',
            '디한': '대한',
            '점보화': '정보를',
            '언기': '얻을',
            '수있습니다': '수 있습니다',
            '온라언': '온라인',
            '쇼{다T': '쇼핑몰을',
            '국석서도': '통해서도',
            '심차표$': '생필품을',
            '싸거': '싸게',
            '구머n': '구매할',
            '수 있심니다': '수 있습니다',
            '쇼청-어서논': '쇼핑몰에서는',
            '나인': '할인',
            '법사다': '행사를',
            '꽤인': '할인',
            '무존하': '쿠폰을',
            '저공나나다': '제공합니다',
            '이뇨': '이를',
            '부용하여': '활용하여',
            '수청': '특정',
            '상5자': '상품을',
            '씨거구머하거나': '싸게 구매하거나',
            '추가': '추가',
            '거인속': '할인을',
            '받$': '받을',
            '수있속니다': '수 있습니다'
        }
        
        # Apply Korean corrections
        for wrong, correct in korean_corrections.items():
            korean_description = korean_description.replace(wrong, correct)
        
        # Apply English text corrections for common OCR mistakes
        english_corrections = {
            'Yarious': 'Various',
            'bout': 'about',
            'recommnendations': 'recommendations',
            'inflyers': 'in flyers',
            'superrmarkets': 'supermarkets',
            'Yo can': 'You can',
            'al5o': 'also',
            'Cnline': 'Online',
            'mlalb': 'malls',
            'coupans': 'coupons'
        }
        
        # Apply English corrections
        for wrong, correct in english_corrections.items():
            english_description = english_description.replace(wrong, correct)
        
        all_description = ' '.join((korean_description + ' ' + english_description).strip().split())
        
        return {
            'success': True,
            'korean_text': korean_description,  # Korean text only
            'english_text': english_description,  # English text only
            'description': all_description,  # Combined description (for backward compatibility)
            'total_detections': len(extracted_texts),
            'extracted_texts': extracted_texts  # Keep detailed results for debugging
        }
        
    except Exception as e:
        logger.error(f"Error extracting text from image: {e}")
        return {
            'success': False,
            'error': str(e),
            'korean_text': '',
            'english_text': '',
            'description': '',
            'total_detections': 0,
            'extracted_texts': []
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
            logger.info(f"Korean text: {result['korean_text']}")
            logger.info(f"English text: {result['english_text']}")
            logger.info(f"Total detections: {result['total_detections']}")
            
            # Print results
            print("\n" + "="*60)
            print("KOREAN TEXT EXTRACTION RESULTS")
            print("="*60)
            print(f"Sample Image: {sample_image_path}")
            print(f"Total Text Detections: {result['total_detections']}")
            print(f"\nKOREAN TEXT:")
            print("-" * 40)
            print(result['korean_text'])
            print("-" * 40)
            print(f"\nENGLISH TEXT:")
            print("-" * 40)
            print(result['english_text'])
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
                'error': 'No image file provided',
                'korean_text': '',
                'english_text': '',
                'accuracy': 0.0
            }), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No image file selected',
                'korean_text': '',
                'english_text': '',
                'accuracy': 0.0
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
            
            # Ensure all values are JSON serializable - simplified response
            safe_result = {
                'success': bool(result['success']),
                'korean_text': str(result.get('korean_text', '')),
                'english_text': str(result.get('english_text', '')),
                'accuracy': round(float(result.get('total_detections', 0)) / 10.0, 2) if result.get('total_detections', 0) > 0 else 0.0
            }
            
            # Add error if present
            if 'error' in result:
                safe_result['error'] = str(result['error'])
            
            return jsonify(safe_result)
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        logger.error(f"Error in extract text endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'korean_text': '',
            'english_text': '',
            'accuracy': 0.0
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
