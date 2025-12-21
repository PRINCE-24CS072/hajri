# HAJRI

University attendance tracking system with an OCR-powered backend that extracts attendance entries from dashboard screenshots.

## 📁 Project Structure

```
hajri/
├── hajri-ocr/          # OCR Backend API (FastAPI + hosted PaddleOCR PP-Structure API)
└── BUILD_PLAN.md       # Project planning
```

## 🚀 hajri-ocr Backend

FastAPI backend that extracts attendance data from university dashboard screenshots using OCR + fuzzy matching.

### Features
- 🤖 Hosted PaddleOCR PP-Structure API integration
- ⚡ FastAPI REST API for mobile app usage
- 🔐 Optional API-key auth for public deployments
- 🧰 Owner-only debug console (when enabled)

### Quick Start

```bash
cd hajri-ocr
pip install -r requirements.txt
uvicorn main:app --reload
```

**Server runs at:** `http://localhost:8000`
- Status: `http://localhost:8000/ping.html`

### Deploy to Render

See [hajri-ocr/README.md](hajri-ocr/README.md) for deployment instructions.

## 📱 Future Components

- Android App (coming soon)
- Student Dashboard (coming soon)

## 🛠️ Tech Stack

- **Backend**: FastAPI + hosted PaddleOCR API
- **Image Processing**: OpenCV + Pillow
- **Fuzzy Matching**: difflib
- **Deployment**: Render (backend)

## 📄 License

MIT
