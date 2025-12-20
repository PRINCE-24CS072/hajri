"""
Test PaddleOCR's built-in table recognition (PP-Structure)
"""
import os
import cv2
import json
from paddleocr import PPStructure

def test_table_recognition():
    """Test PP-Structure on real screenshots"""
    
    # Initialize PP-Structure with table recognition
    print("[*] Initializing PP-Structure...")
    table_engine = PPStructure(
        table=True,
        ocr=True,
        show_log=False,
        lang='en'
    )
    print("[OK] Ready\n")
    
    # Test on first image
    test_image = "test_images/dashboard.png"
    print(f"[*] Processing: {test_image}")
    
    image = cv2.imread(test_image)
    
    # Run table detection + recognition
    result = table_engine(image)
    
    print(f"\n[*] Found {len(result)} regions")
    
    for i, region in enumerate(result):
        print(f"\n--- Region {i+1} ---")
        print(f"Type: {region.get('type', 'unknown')}")
        
        if region['type'] == 'table':
            print(f"Bbox: {region.get('bbox', 'N/A')}")
            
            # Check if table HTML or structured data exists
            if 'res' in region:
                print(f"Table data: {region['res'][:200]}...")  # First 200 chars
            
            if 'html' in region:
                print("HTML structure available")
    
    # Save full result
    output_file = "test_output_real/ppstructure_result.json"
    os.makedirs("test_output_real", exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n[OK] Full result saved to: {output_file}")

if __name__ == "__main__":
    test_table_recognition()
