"""
Test script for modal detection system
Tests the modal detector with sample images
"""

import sys
from pathlib import Path
import cv2
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from modal_detector import ModalDetector
from paddleocr import PaddleOCR


def create_mock_screenshot(width=1920, height=1080, modal_ratio=0.6):
    """
    Create a mock screenshot for testing
    
    Simulates:
    - Background UI (gray)
    - White modal in center
    - Header text at top of modal
    - Tables inside modal
    """
    # Create gray background
    image = np.ones((height, width, 3), dtype=np.uint8) * 180
    
    # Calculate modal dimensions
    modal_width = int(width * modal_ratio)
    modal_height = int(height * 0.65)
    
    # Center the modal
    x1 = (width - modal_width) // 2
    y1 = int(height * 0.15)
    x2 = x1 + modal_width
    y2 = y1 + modal_height
    
    # Draw white modal background
    cv2.rectangle(image, (x1, y1), (x2, y2), (255, 255, 255), -1)
    
    # Draw blue header bar
    header_height = 60
    cv2.rectangle(image, (x1, y1), (x2, y1 + header_height), (66, 135, 245), -1)
    
    # Add header text
    cv2.putText(
        image, 
        "Lecture Gross Attendance of Semester 5",
        (x1 + 30, y1 + 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )
    
    # Add close button
    cv2.circle(image, (x2 - 30, y1 + 30), 15, (255, 255, 255), 2)
    cv2.line(image, (x2 - 38, y1 + 22), (x2 - 22, y1 + 38), (255, 255, 255), 2)
    cv2.line(image, (x2 - 22, y1 + 22), (x2 - 38, y1 + 38), (255, 255, 255), 2)
    
    # Add table-like content
    table_y = y1 + header_height + 40
    for i in range(5):
        y = table_y + i * 50
        cv2.putText(image, f"CSUC20{i+1}", (x1 + 50, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        cv2.putText(image, "LECT", (x1 + 300, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        cv2.putText(image, f"{40+i}/{50+i}", (x1 + 500, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        cv2.putText(image, f"{70+i}%", (x1 + 700, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    
    # Add footer
    footer_y = y2 - 30
    cv2.putText(
        image,
        "© 2024 Charotar University",
        (x1 + 30, footer_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (128, 128, 128),
        1
    )
    
    return image


def test_modal_detection():
    """Test modal detection on mock screenshots"""
    print("=" * 70)
    print("MODAL DETECTION TEST")
    print("=" * 70)
    
    # Create mock screenshots at different zoom levels
    test_cases = [
        ("Full HD zoomed out", 1920, 1080, 0.6),
        ("Full HD zoomed in", 1920, 1080, 0.85),
        ("Mobile screenshot", 720, 1280, 0.90),
        ("Desktop zoomed out", 2560, 1440, 0.55),
    ]
    
    # Initialize OCR engine (needed for header detection)
    print("\n[*] Initializing PaddleOCR...")
    ocr_engine = PaddleOCR(use_textline_orientation=False, lang='en')
    print("[OK] PaddleOCR ready\n")
    
    # Initialize detector
    detector = ModalDetector(ocr_engine=ocr_engine)
    
    for name, width, height, modal_ratio in test_cases:
        print(f"\n{'='*70}")
        print(f"Test Case: {name}")
        print(f"{'='*70}")
        print(f"Image size: {width}x{height}px")
        print(f"Modal ratio: {modal_ratio}")
        
        # Create mock screenshot
        screenshot = create_mock_screenshot(width, height, modal_ratio)
        
        # Save input for inspection
        output_dir = Path("test_output")
        output_dir.mkdir(exist_ok=True)
        input_path = output_dir / f"{name.replace(' ', '_')}_input.png"
        cv2.imwrite(str(input_path), screenshot)
        print(f"Input saved: {input_path}")
        
        try:
            # Detect and crop modal
            cropped, debug_info = detector.detect_and_crop_modal(screenshot)
            
            # Print results
            print(f"\n[OK] Modal detected!")
            print(f"   Method: {debug_info['detection_method']}")
            print(f"   Header found: {debug_info['header_found']}")
            print(f"   Original size: {debug_info['original_size']}")
            print(f"   Crop bounds: {debug_info['crop_bounds']}")
            print(f"   Normalized size: {debug_info['normalized_size']}")
            
            # Calculate crop percentage
            x1, y1, x2, y2 = debug_info['crop_bounds']
            crop_width = x2 - x1
            crop_height = y2 - y1
            crop_area_pct = (crop_width * crop_height) / (width * height) * 100
            print(f"   Cropped area: {crop_area_pct:.1f}% of original")
            
            # Save cropped result
            output_path = output_dir / f"{name.replace(' ', '_')}_cropped.png"
            cv2.imwrite(str(output_path), cropped)
            print(f"   Cropped saved: {output_path}")
            
            # Visual comparison
            visual = np.hstack([
                cv2.resize(screenshot, (640, int(640 * height / width))),
                cv2.resize(cropped, (640, int(640 * cropped.shape[0] / cropped.shape[1])))
            ])
            visual_path = output_dir / f"{name.replace(' ', '_')}_comparison.png"
            cv2.imwrite(str(visual_path), visual)
            print(f"   Comparison saved: {visual_path}")
            
        except Exception as e:
            print(f"\n[FAIL] Detection failed: {e}")
    
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"✓ Test output saved to: {output_dir.absolute()}")
    print("✓ Check the comparison images to verify modal detection")
    print("\nNext steps:")
    print("1. Review the cropped images")
    print("2. Test with real screenshots")
    print("3. Adjust detection parameters if needed")


def test_header_detection():
    """Test header detection specifically"""
    print("\n" + "=" * 70)
    print("HEADER DETECTION TEST")
    print("=" * 70)
    
    # Create a simple test image with header text
    image = np.ones((400, 1200, 3), dtype=np.uint8) * 255
    
    # Add header text
    cv2.putText(
        image,
        "Lecture Gross Attendance of Semester 5",
        (50, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 0),
        2
    )
    
    # Initialize OCR
    print("\n[*] Initializing PaddleOCR...")
    ocr_engine = PaddleOCR(use_textline_orientation=False, lang='en')
    
    # Test header detection
    detector = ModalDetector(ocr_engine=ocr_engine)
    header_bbox = detector._detect_header(image)
    
    if header_bbox:
        print(f"[OK] Header detected at: {header_bbox}")
        x1, y1, x2, y2 = header_bbox
        
        # Draw bounding box
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Save result
        output_dir = Path("test_output")
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / "header_detection_test.png"
        cv2.imwrite(str(output_path), image)
        print(f"Result saved: {output_path}")
    else:
        print("[FAIL] Header not detected")


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("MODAL DETECTION SYSTEM - TEST SUITE")
    print("=" * 70 + "\n")
    
    try:
        # Test 1: Header detection
        test_header_detection()
        
        # Test 2: Full modal detection
        test_modal_detection()
        
        print("\n" + "✅" * 35)
        print("ALL TESTS COMPLETE")
        print("✅" * 35)
        
    except Exception as e:
        print(f"\n[FAIL] Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
