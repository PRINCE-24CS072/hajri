"""Debug: See what OCR actually detects"""
import sys
sys.path.insert(0, 'b:/hajri/hajri-ocr')

from table_extractor import TableExtractor
import cv2

extractor = TableExtractor(use_gpu=False)
image = cv2.imread("b:/hajri/hajri-ocr/test_images/dashboard.png")

print("[*] Running OCR...")
result = extractor._get_ocr().ocr(image, cls=True)

print(f"\n[*] OCR found {len(result[0])} text regions\n")

for i, line in enumerate(result[0][:30], 1):  # First 30 regions
    box = line[0]
    text = line[1][0]
    conf = line[1][1]
    x_center = (box[0][0] + box[2][0]) / 2
    y_center = (box[0][1] + box[2][1]) / 2
    
    print(f"{i:2d}. [{int(x_center):4d},{int(y_center):3d}] '{text}' (conf={conf:.2f})")
