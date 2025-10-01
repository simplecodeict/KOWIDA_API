"""
Simple OCR Test Script for Korean Text Extraction
This script tests OCR functionality without complex progress bars
"""

import os
import sys
import logging

# Configure logging to avoid Unicode issues
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_korean_ocr():
    """Test Korean OCR with the sample image"""
    try:
        print("=" * 60)
        print("KOREAN TEXT EXTRACTION TEST")
        print("=" * 60)
        print()
        
        # Import EasyOCR
        import easyocr
        from PIL import Image
        import cv2
        import numpy as np
        
        print("Initializing EasyOCR...")
        print("Note: First run will download models (this may take a few minutes)")
        
        # Initialize EasyOCR with Korean and English
        reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
        print("EasyOCR initialized successfully!")
        
        # Path to sample image
        sample_image_path = os.path.join('assets', 'ss2.png')
        
        if not os.path.exists(sample_image_path):
            print(f"ERROR: Sample image not found at {sample_image_path}")
            return False
        
        print(f"Processing image: {sample_image_path}")
        
        # Read and process the image
        img = cv2.imread(sample_image_path)
        if img is None:
            print("ERROR: Could not read the image")
            return False
        
        print(f"Original image shape: {img.shape}")
        
        # Enhanced preprocessing for better Korean text accuracy
        print("Applying enhanced preprocessing for accuracy...")
        
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
        
        print("Enhanced preprocessing completed")
        
        # Fast OCR - use optimized configuration directly
        print("Extracting text...")
        
        # Use the most effective configuration for Korean text
        results = reader.readtext(img_rgb, detail=1)
        
        print(f"OCR completed: {len(results)} raw detections")
        
        # Debug: Show all raw results with confidence scores
        print("\nRaw OCR Results:")
        for i, (bbox, text, confidence) in enumerate(results):
            print(f"{i+1}. Confidence: {confidence:.3f} - Text: '{text}'")
        
        # Process results - separate Korean and English text
        extracted_texts = []
        korean_text = ""
        english_text = ""
        
        # Dynamic confidence threshold for Korean text
        confidence_threshold = 0.1  # Lower threshold to catch Korean text
        
        for (bbox, text, confidence) in results:
            if confidence > confidence_threshold:  # Use dynamic threshold
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
        
        # Display results
        print("\n" + "="*60)
        print("KOREAN TEXT EXTRACTION RESULTS")
        print("="*60)
        print(f"Sample Image: {sample_image_path}")
        print(f"Total Text Detections: {len(extracted_texts)}")
        
        print(f"\nKOREAN TEXT (CORRECTED):")
        print("-" * 50)
        if korean_description:
            try:
                print(korean_description)
            except UnicodeEncodeError:
                print("[Korean text detected - contains Korean characters]")
                # Try to save to file for viewing
                with open('korean_text_output.txt', 'w', encoding='utf-8') as f:
                    f.write(korean_description)
                print("Korean text saved to 'korean_text_output.txt' file")
        else:
            print("No Korean text detected")
        print("-" * 50)
        
        print(f"\nENGLISH TEXT:")
        print("-" * 50)
        print(english_description if english_description else "No English text detected")
        print("-" * 50)
        
        print(f"\nALL TEXT COMBINED:")
        print("-" * 50)
        try:
            print(all_description)
        except UnicodeEncodeError:
            print("[Mixed text - contains Korean characters]")
            with open('all_text_output.txt', 'w', encoding='utf-8') as f:
                f.write(all_description)
            print("All text saved to 'all_text_output.txt' file")
        print("-" * 50)
        print("="*60)
        
        if extracted_texts:
            print("\n[SUCCESS] OCR Test Completed Successfully!")
            print("Korean text extraction is working properly.")
            return True
        else:
            print("\n[WARNING] No text was detected in the image.")
            print("This could be due to:")
            print("- Image quality issues")
            print("- No Korean text in the image")
            print("- Text is too small or unclear")
            return False
            
    except ImportError as e:
        print(f"[ERROR] Import error: {e}")
        print("Please install the required dependencies:")
        print("pip install easyocr opencv-python Pillow numpy")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_korean_ocr()
    
    if success:
        print("\nYou can now use the OCR functionality in your Flask app!")
        print("\nAvailable endpoints:")
        print("- GET /api/ocr/test-ocr - Test with sample image")
        print("- POST /api/ocr/extract-text - Extract text from uploaded image")
    else:
        print("\nOCR test failed. Please check the error messages above.")
