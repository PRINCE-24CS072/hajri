"""
Test script for anchor-based OCR extraction
Run this to verify the new system works correctly
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from table_extractor import TableExtractor
import cv2
import json


def test_anchor_detection():
    """Test anchor detection logic"""
    print("\n=== Testing Anchor Detection ===")
    
    extractor = TableExtractor(use_gpu=False)
    
    # Mock tokens
    tokens = [
        {'text': 'CSUC201', 'x_center': 100, 'y_center': 200, 'conf': 0.9},
        {'text': 'LECT', 'x_center': 300, 'y_center': 205, 'conf': 0.9},
        {'text': 'MATH101', 'x_center': 100, 'y_center': 250, 'conf': 0.9},
        {'text': 'LAB', 'x_center': 300, 'y_center': 252, 'conf': 0.9},
    ]
    
    anchors = extractor._detect_anchors(tokens, image_width=1000)
    
    print(f"Detected {len(anchors)} anchors:")
    for anchor in anchors:
        print(f"  - {anchor['course_code']} {anchor['class_type']} at Y={anchor['y_center']}")
    
    assert len(anchors) == 2, f"Expected 2 anchors, got {len(anchors)}"
    assert anchors[0]['course_code'] == 'CSUC201', "First anchor should be CSUC201"
    assert anchors[0]['class_type'] == 'LECT', "First anchor should be LECT"
    
    print("✅ Anchor detection test passed!")
    return True


def test_field_detection():
    """Test attendance and percentage field detection"""
    print("\n=== Testing Field Detection ===")
    
    extractor = TableExtractor(use_gpu=False)
    
    # Mock tokens
    tokens = [
        {'text': '42/59', 'x_center': 600, 'y_center': 200, 'conf': 0.9},
        {'text': '71.2%', 'x_center': 900, 'y_center': 203, 'conf': 0.9},
        {'text': '38/52', 'x_center': 600, 'y_center': 250, 'conf': 0.9},
        {'text': '73%', 'x_center': 900, 'y_center': 252, 'conf': 0.9},
    ]
    
    attendance_fields = extractor._detect_attendance_fields(tokens, image_width=1000)
    percentage_fields = extractor._detect_percentage_fields(tokens, image_width=1000)
    
    print(f"Detected {len(attendance_fields)} attendance fields:")
    for field in attendance_fields:
        print(f"  - {field['present']}/{field['total']} at Y={field['y_center']}")
    
    print(f"Detected {len(percentage_fields)} percentage fields:")
    for field in percentage_fields:
        print(f"  - {field['percentage']}% at Y={field['y_center']}")
    
    assert len(attendance_fields) == 2, f"Expected 2 attendance fields, got {len(attendance_fields)}"
    assert len(percentage_fields) == 2, f"Expected 2 percentage fields, got {len(percentage_fields)}"
    
    print("✅ Field detection test passed!")
    return True


def test_field_matching():
    """Test geometry-based field matching"""
    print("\n=== Testing Field Matching ===")
    
    extractor = TableExtractor(use_gpu=False)
    
    # Mock anchors
    anchors = [
        {'course_code': 'CSUC201', 'class_type': 'LECT', 
         'x_center': 100, 'y_center': 200},
        {'course_code': 'MATH101', 'class_type': 'LAB', 
         'x_center': 100, 'y_center': 250}
    ]
    
    # Mock fields
    attendance_fields = [
        {'present': 42, 'total': 59, 'x_center': 600, 'y_center': 205},
        {'present': 38, 'total': 52, 'x_center': 600, 'y_center': 252}
    ]
    
    percentage_fields = [
        {'percentage': 71.2, 'x_center': 900, 'y_center': 203},
        {'percentage': 73.0, 'x_center': 900, 'y_center': 251}
    ]
    
    entries = extractor._match_fields_to_anchors(
        anchors, attendance_fields, percentage_fields
    )
    
    print(f"Matched {len(entries)} entries:")
    for entry in entries:
        print(f"  - {entry['course_code']} {entry['class_type']}: "
              f"{entry['present']}/{entry['total']} ({entry['percentage']}%)")
    
    assert len(entries) == 2, f"Expected 2 entries, got {len(entries)}"
    assert entries[0]['present'] == 42, "First entry should have present=42"
    assert entries[0]['percentage'] == 71.2, "First entry should have percentage=71.2"
    assert entries[1]['present'] == 38, "Second entry should have present=38"
    
    print("✅ Field matching test passed!")
    return True


def test_course_code_normalization():
    """Test course code normalization"""
    print("\n=== Testing Course Code Normalization ===")
    
    extractor = TableExtractor(use_gpu=False)
    
    test_cases = [
        ('CSUC201', 'CSUC201'),  # Already normalized
        ('CSUCO01', 'CSUC001'),  # O->0
        ('CSUCIO1', 'CSUC101'),  # I->1
        ('CSUC2O1', 'CSUC201'),  # O->0
        ('MATH1O1', 'MATH101'),  # O->0
    ]
    
    for raw, expected in test_cases:
        result = extractor._normalize_course_code(raw)
        print(f"  {raw} -> {result} {'✓' if result == expected else '✗ Expected: ' + expected}")
        assert result == expected, f"Failed: {raw} -> {result}, expected {expected}"
    
    print("✅ Course code normalization test passed!")
    return True


def test_column_zoning():
    """Test column zone detection"""
    print("\n=== Testing Column Zoning ===")
    
    extractor = TableExtractor(use_gpu=False)
    image_width = 1000
    
    test_cases = [
        (100, 'COURSE_CODE', extractor.COURSE_CODE_ZONE),
        (400, 'CLASS_TYPE', extractor.CLASS_TYPE_ZONE),
        (600, 'ATTENDANCE', extractor.ATTENDANCE_ZONE),
        (900, 'PERCENTAGE', extractor.PERCENTAGE_ZONE),
    ]
    
    for x_center, expected_zone_name, expected_zone in test_cases:
        x_ratio = extractor._get_x_ratio(x_center, image_width)
        in_zone = extractor._in_zone(x_ratio, expected_zone)
        print(f"  x={x_center} (ratio={x_ratio:.2f}) -> {expected_zone_name} zone: {'✓' if in_zone else '✗'}")
        assert in_zone, f"x={x_center} should be in {expected_zone_name} zone"
    
    print("✅ Column zoning test passed!")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("ANCHOR-BASED OCR EXTRACTION - TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_anchor_detection,
        test_field_detection,
        test_field_matching,
        test_course_code_normalization,
        test_column_zoning,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ Test error: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 All tests passed! Anchor-based system is working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Check implementation.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
