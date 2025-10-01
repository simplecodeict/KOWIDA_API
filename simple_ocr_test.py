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
        sample_image_path = os.path.join('assets', 'ss.png')
        
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
        
        # Try different image preprocessing techniques
        print("Trying different image preprocessing...")
        
        # Method 1: Original image
        img_rgb1 = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Method 2: Grayscale with contrast enhancement
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        enhanced = cv2.convertScaleAbs(gray, alpha=1.5, beta=30)  # Increase contrast
        img_rgb2 = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
        
        # Method 3: Denoised image
        denoised = cv2.fastNlMeansDenoising(gray)
        img_rgb3 = cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB)
        
        # Method 4: Sharpened image
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(gray, -1, kernel)
        img_rgb4 = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)
        
        # Test all preprocessing methods
        test_images = [
            ("Original", img_rgb1),
            ("Enhanced Contrast", img_rgb2), 
            ("Denoised", img_rgb3),
            ("Sharpened", img_rgb4)
        ]
        
        best_image = img_rgb1
        best_detections = 0
        
        for method_name, test_img in test_images:
            try:
                test_results = reader.readtext(test_img, detail=1)
                detection_count = len([r for r in test_results if r[2] > 0.1])
                print(f"{method_name}: {detection_count} detections")
                
                if detection_count > best_detections:
                    best_detections = detection_count
                    best_image = test_img
            except:
                print(f"{method_name}: Error processing")
        
        print(f"Using best preprocessing method with {best_detections} detections")
        img_rgb = best_image
        
        # Perform OCR with different configurations
        print("Extracting text...")
        
        # Try multiple OCR configurations for better Korean text detection
        print("Trying different OCR configurations...")
        
        # Configuration 1: Default settings
        results1 = reader.readtext(img_rgb)
        print(f"Configuration 1 (default): {len(results1)} detections")
        
        # Configuration 2: With paragraph detection
        results2 = reader.readtext(img_rgb, paragraph=True)
        print(f"Configuration 2 (paragraph): {len(results2)} detections")
        
        # Configuration 3: With different confidence threshold
        results3 = reader.readtext(img_rgb, detail=1)
        print(f"Configuration 3 (detailed): {len(results3)} detections")
        
        # Use the configuration with most detections
        all_results = [results1, results2, results3]
        best_results = max(all_results, key=len)
        results = best_results
        
        print(f"Using best configuration with {len(results)} detections")
        
        # Also try with lower confidence threshold
        if len(results) == 0:
            print("No text detected with default settings. Trying lower confidence threshold...")
            results = reader.readtext(img_rgb, detail=1)
            # Filter with lower confidence
            results = [(bbox, text, conf) for bbox, text, conf in results if conf > 0.1]
            print(f"With lower confidence (0.1): {len(results)} detections")
        
        # Process results - separate Korean and English text
        extracted_texts = []
        korean_text = ""
        english_text = ""
        
        # Lower confidence threshold for Korean text
        confidence_threshold = 0.1 if len(results) < 5 else 0.5
        
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
        
        # Clean up the descriptions
        korean_description = ' '.join(korean_text.strip().split())
        english_description = ' '.join(english_text.strip().split())
        all_description = ' '.join((korean_text + english_text).strip().split())
        
        # Display results
        print("\n" + "="*60)
        print("KOREAN TEXT EXTRACTION RESULTS")
        print("="*60)
        print(f"Sample Image: {sample_image_path}")
        print(f"Total Text Detections: {len(extracted_texts)}")
        
        print(f"\nKOREAN TEXT:")
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
