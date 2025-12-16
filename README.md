# HAJRI - Attendance Tracking System

University attendance tracking system with OCR-powered dashboard screenshot extraction.

## 📁 Project Structure

```
hajri/
├── hajri-ocr/          # OCR Backend API (FastAPI + PaddleOCR)
└── BUILD_PLAN.md       # Project planning
```

## 🚀 hajri-ocr Backend

FastAPI backend that extracts attendance data from university dashboard screenshots using OCR + fuzzy matching.

### Features
- 📸 Screenshot-optimized image preprocessing
- 🤖 PaddleOCR for text detection
- 🎯 Fuzzy matching for course code auto-correction
- 📚 Course database for accurate course names
- 🌐 Course management web UI

### Quick Start

```bash
cd hajri-ocr
pip install -r requirements.txt
uvicorn main:app --reload
```

**Server runs at:** `http://localhost:8000`
- OCR Test UI: `http://localhost:8000/test.html`
- Course Manager: `http://localhost:8000/courses.html`

### Deploy to Render

See [hajri-ocr/README.md](hajri-ocr/README.md) for deployment instructions.

## 📱 Future Components

- Android App (coming soon)
- Student Dashboard (coming soon)

## 🛠️ Tech Stack

- **Backend**: FastAPI + PaddleOCR
- **Image Processing**: OpenCV + Pillow
- **Fuzzy Matching**: difflib
- **Deployment**: Render (backend)

## 📄 License

MIT
