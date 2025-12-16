# HAJRI OCR - Attendance Table Extractor

FastAPI backend that extracts attendance data from university dashboard screenshots using OCR + fuzzy matching.

## Features

- 📸 Screenshot-optimized image preprocessing
- 🤖 PaddleOCR for text detection
- 🎯 Fuzzy matching for course code auto-correction
- 📚 Course database for accurate course names
- 🌐 Course management web UI
- ⚡ Production-ready for Render deployment

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run server
uvicorn main:app --reload
```

Server runs at: `http://localhost:8000`
- OCR Test UI: `http://localhost:8000/test.html`
- Course Manager: `http://localhost:8000/courses.html`

## Deploy to Render

1. **Push to GitHub**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/hajri-ocr.git
git push -u origin main
```

2. **Create Render Web Service**
   - Go to [render.com](https://render.com)
   - Click "New +" → "Web Service"
   - Connect your GitHub repo
   - Render auto-detects `render.yaml`
   - Click "Create Web Service"

3. **Done!** Your API will be live at `https://YOUR_APP.onrender.com`

## API Endpoints

### `POST /ocr/extract`
Extract attendance from screenshot
- **Body**: `file` (multipart/form-data image)
- **Returns**: JSON array of attendance entries

### `GET /courses`
List all configured courses

### `POST /courses/{code}`
Add/update course
- **Body**: `{"name": "Course Name", "abbr": "CODE"}`

### `DELETE /courses/{code}`
Remove course

### `GET /health`
Health check for monitoring

## Configuration

Edit `.env`:
```bash
PORT=8000
LOG_LEVEL=info  # info, warning, error
```

## Course Database

Manage courses at `/courses.html` or edit `course_config.json`:
```json
{
  "courses": {
    "CEUC201": {
      "name": "FUNDAMENTALS OF SOFTWARE ENGINEERING",
      "abbr": "FSE"
    }
  }
}
```

## Tech Stack

- **Framework**: FastAPI + Uvicorn
- **OCR**: PaddleOCR 2.7.3
- **Image Processing**: OpenCV + Pillow
- **Fuzzy Matching**: difflib
- **Python**: 3.11+

## License

MIT
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Test with Sample Image

1. Create a `test_images/` folder
2. Add your dashboard screenshot
3. Visit: http://localhost:8000/test/sample

## API Endpoints

### `POST /ocr/extract`

Upload an image file for extraction.

**Request:**
```bash
curl -X POST http://localhost:8000/ocr/extract \
  -F "file=@dashboard.png"
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully extracted 7 attendance entries",
  "entries": [
    {
      "course_code": "CEUC201/FSE",
      "course_name": "FUNDAMENTALS OF SOFTWARE ENGINEERING",
      "class_type": "LECT",
      "present": 12,
      "total": 15,
      "percentage": 80.0,
      "confidence": 0.95
    }
  ],
  "metadata": {
    "total_rows": 8,
    "filtered_rows": 0,
    "avg_confidence": 0.89,
    "processing_time_ms": 1234
  }
}
```

### `GET /health`

Check service health.

```bash
curl http://localhost:8000/health
```

## Configuration

Edit `.env` file:

```env
# OCR Engine (paddle or tesseract)
OCR_ENGINE=paddle

# Confidence threshold (0.0 - 1.0)
CONFIDENCE_THRESHOLD=0.70

# Max image size in MB
MAX_IMAGE_SIZE_MB=10

# CORS origins (comma-separated)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

## Troubleshooting

### PaddleOCR Not Working?

If you get errors about PaddlePaddle, try:

```powershell
pip uninstall paddlepaddle
pip install paddlepaddle==2.6.0 -i https://mirror.baidu.com/pypi/simple
```

### Image Not Processing?

- Ensure image is clear and well-lit
- Check image size (< 10MB)
- Try preprocessing manually with higher contrast

### Low Accuracy?

- Adjust `CONFIDENCE_THRESHOLD` in `.env` (lower = more results, less reliable)
- Check if table has clear borders
- Ensure text is not too small (resize before upload)

## Next Steps

1. **Test with real screenshots** - Add to `test_images/`
2. **Deploy to Render** - See `DEPLOYMENT.md` (coming soon)
3. **Integrate with Android app** - Use `/ocr/extract` endpoint

## Development

### Run Tests

```powershell
pytest tests/ -v
```

### Enable Debug Logging

In `.env`:
```env
DEBUG=True
```

## License

MIT
