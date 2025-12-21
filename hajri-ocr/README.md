# HAJRI OCR

FastAPI backend that extracts attendance entries from university dashboard screenshots using a **hosted PaddleOCR PP-Structure (layout-parsing) API**.

## Quick Start (local)

```bash
cd hajri-ocr
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set:
# PADDLEOCR_VL_API_URL=https://.../layout-parsing
# PADDLEOCR_VL_API_TOKEN=...

uvicorn main:app --reload
```

Useful URLs:
- `http://localhost:8000/ping.html`
- `http://localhost:8000/health`

If `ENABLE_DEBUG_UI=true`:
- `http://localhost:8000/admin/login`
- `http://localhost:8000/debug.html`

## Configuration

Required:
- `PADDLEOCR_VL_API_URL`
- `PADDLEOCR_VL_API_TOKEN`

Recommended (public deployments):
- `ENV=production`
- `APP_API_KEY` (required when `ENV=production`)

Optional:
- `ENABLE_DEBUG_UI` (default `false` in `render.yaml`)
- `ENABLE_DOCS` (default `false` in `render.yaml`)

If `ENABLE_DEBUG_UI=true` in production:
- `ADMIN_COOKIE_SECRET` (required)
- `ADMIN_USERS_JSON` (required, map of username → password)

Optional (Postman/curl):
- `DEBUG_ADMIN_KEY` (header-based admin access via `X-Admin-Key`)

## Course Mapping

Course name resolution is loaded from `course_config.json`.

Edit `course_config.json` to add/update courses (the app reads it from disk).

`course_config.example.json` is included as a reference/template.

## API Endpoints

- `POST /ocr/extract` (requires `APP_API_KEY` when `ENV=production`)
- `POST /ocr/extract/tuning` (legacy alias of `/ocr/extract`)
- `GET /health`
- `GET /ping` (JSON by default)
- `GET /ping.html` (terminal-style HTML)

Debug/admin (only when `ENABLE_DEBUG_UI=true`):
- `GET /admin/login` / `POST /admin/login` / `POST /admin/logout`
- `GET /debug.html` (requires admin)
- `POST /ocr/debug` (requires admin)

Example request:

```bash
curl -X POST http://localhost:8000/ocr/extract \
  -H "X-API-Key: YOUR_APP_API_KEY" \
  -F "file=@dashboard.png"
```

## Deploy to Render

This repo includes `render.yaml`. In Render, set the **Root Directory** to `hajri-ocr`, and configure secrets in Environment:
- `PADDLEOCR_VL_API_URL`
- `PADDLEOCR_VL_API_TOKEN`
- `APP_API_KEY`

If you enable debug UI on Render:
- `ADMIN_COOKIE_SECRET`
- `ADMIN_USERS_JSON`

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
