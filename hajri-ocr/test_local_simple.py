"""
Simple local test - process one screenshot directly
"""
import sys
sys.path.insert(0, 'b:/hajri/hajri-ocr')

from pathlib import Path
from image_preprocessor import ImagePreprocessor
from table_extractor import TableExtractor
import cv2
import json

print("[*] Initializing...")
preprocessor = ImagePreprocessor()
extractor = TableExtractor(use_gpu=False)

print("[*] Loading image...")
image_path = "b:/hajri/hajri-ocr/test_images/dashboard.png"
image = cv2.imread(image_path)
print(f"    Image size: {image.shape[1]}x{image.shape[0]}")

print("\n[*] Running OCR extraction...")
try:
    entries = extractor.extract_table_data(image)
    print(f"\n[OK] Extracted {len(entries)} entries\n")
    
    for entry in entries[:5]:  # Show first 5
        attendance_str = f"{entry.present}/{entry.total}" if entry.present and entry.total else "N/A"
        print(f"  - {entry.course_code} ({entry.class_type}): {attendance_str} = {entry.percentage}%")
    
    if len(entries) > 5:
        print(f"  ... and {len(entries) - 5} more")
    
    # Save to JSON
    output = [e.__dict__ for e in entries]
    with open("test_output_local.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n[OK] Saved to: test_output_local.json")
    
except Exception as e:
    print(f"\n[FAIL] Error: {e}")
    import traceback
    traceback.print_exc()
