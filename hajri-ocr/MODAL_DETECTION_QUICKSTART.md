# Modal Detection - Quick Reference

## 🚀 Quick Start

### Enable Modal Detection (Default):
```python
from image_preprocessor import ImagePreprocessor
from table_extractor import TableExtractor

preprocessor = ImagePreprocessor(enable_modal_detection=True)
extractor = TableExtractor(use_gpu=False)

# Process screenshot
with open('screenshot.png', 'rb') as f:
    image_bytes = f.read()

processed, debug = preprocessor.preprocess_screenshot(
    image_bytes,
    ocr_engine=extractor._get_ocr()
)

entries = extractor.extract_table_data(processed)
```

### Disable Modal Detection:
```python
processed, debug = preprocessor.preprocess_screenshot(
    image_bytes,
    detect_modal=False  # Skip modal detection
)
```

---

## 📊 Debug Info

```python
debug_info = {
    'original_size': (1920, 1080),
    'modal_detected': True,
    'modal_bounds': (384, 145, 1536, 847),
    'modal_detection_method': 'ocr_anchor',  # or 'heuristic'
    'normalized_size': (1280, 587),
    'final_size': (1280, 587)
}
```

---

## 🎛️ Quick Tuning

### Header not found? Increase search region:
```python
# In modal_detector.py
self.header_search_region = 0.40  # Was 0.30
```

### Modal too small/large? Adjust ratios:
```python
# In modal_detector.py
self.min_modal_height_ratio = 0.35  # Was 0.40
self.max_modal_height_ratio = 0.90  # Was 0.95
```

### Different header text? Add patterns:
```python
# In modal_detector.py
self.header_patterns = [
    r'Lecture\s+Gross\s+Attendance',
    r'Your\s+Custom\s+Pattern',  # Add custom
]
```

---

## 🧪 Testing

```bash
# Run tests
python test_modal_detector.py

# Check output
ls test_output/
```

---

## 📚 Full Documentation

- Complete guide: [MODAL_DETECTION.md](MODAL_DETECTION.md)
- Summary: [MODAL_DETECTION_SUMMARY.md](MODAL_DETECTION_SUMMARY.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## ⚡ Performance

- **Time**: <3s total (modal + OCR + extraction)
- **Memory**: <400MB peak
- **CPU-only**: Works on Render free tier ✅
