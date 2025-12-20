"""
Test modal detection with real screenshots from test_images/
"""
import os
import cv2
import numpy as np
from paddleocr import PaddleOCR
from modal_detector import ModalDetector
from table_extractor import TableExtractor
import json

def test_real_screenshots():
    """Test modal detection and full extraction pipeline on real images"""
    
    # Create output directory
    output_dir = "test_output_real"
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all test images
    test_dir = "test_images"
    image_files = [f for f in os.listdir(test_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
    
    print("=" * 70)
    print(f"TESTING {len(image_files)} REAL SCREENSHOTS")
    print("=" * 70 + "\n")
    
    # Initialize OCR once
    print("[*] Initializing PaddleOCR...")
    ocr_engine = PaddleOCR(use_textline_orientation=False, lang='en')
    detector = ModalDetector(ocr_engine=ocr_engine)
    extractor = TableExtractor(ocr_engine=ocr_engine)
    print("[OK] System ready\n")
    
    results = []
    
    for i, filename in enumerate(image_files, 1):
        print("=" * 70)
        print(f"Test {i}/{len(image_files)}: {filename}")
        print("=" * 70)
        
        # Load image
        image_path = os.path.join(test_dir, filename)
        image = cv2.imread(image_path)
        
        if image is None:
            print(f"[FAIL] Could not load image\n")
            continue
        
        original_h, original_w = image.shape[:2]
        print(f"Image size: {original_w}x{original_h}px")
        
        try:
            # Step 1: Modal detection
            print("\n[1] Modal Detection...")
            cropped, debug_info = detector.detect_and_crop_modal(image)
            
            print(f"   Method: {debug_info.get('detection_method', 'unknown')}")
            print(f"   Header found: {debug_info.get('header_found', False)}")
            print(f"   Crop bounds: {debug_info.get('crop_bounds', 'unknown')}")
            
            # Save cropped modal
            crop_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}_cropped.png")
            cv2.imwrite(crop_path, cropped)
            print(f"   Saved: {crop_path}")
            
            # Step 2: Table extraction
            print("\n[2] Table Extraction...")
            courses_entries = extractor.extract_table_data(cropped)
            courses = [entry.__dict__ for entry in courses_entries]
            
            print(f"   Courses extracted: {len(courses)}")
            for course in courses[:3]:  # Show first 3
                print(f"      - {course.get('course_code', 'N/A')}: {course.get('attendance', 'N/A')}")
            if len(courses) > 3:
                print(f"      ... and {len(courses) - 3} more")
            
            # Save JSON
            json_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.json")
            with open(json_path, 'w') as f:
                json.dump({
                    'filename': filename,
                    'original_size': f"{original_w}x{original_h}",
                    'modal_detection': debug_info,
                    'courses': courses
                }, f, indent=2)
            print(f"   Saved: {json_path}")
            
            results.append({
                'filename': filename,
                'status': 'success',
                'courses_found': len(courses)
            })
            print("\n[OK] Processing complete\n")
            
        except Exception as e:
            print(f"\n[FAIL] Error: {e}\n")
            results.append({
                'filename': filename,
                'status': 'failed',
                'error': str(e)
            })
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    successful = sum(1 for r in results if r['status'] == 'success')
    print(f"[*] Processed: {len(results)} images")
    print(f"[*] Successful: {successful}")
    print(f"[*] Failed: {len(results) - successful}")
    print(f"[*] Output directory: {os.path.abspath(output_dir)}")
    print("\n" + "=" * 70 + "\n")
    
    return results

if __name__ == "__main__":
    test_real_screenshots()
