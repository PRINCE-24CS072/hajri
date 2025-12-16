# Production Deployment Checklist

## ✅ Pre-Deployment

- [x] requirements.txt with pinned versions
- [x] render.yaml configuration
- [x] .env.example for environment variables
- [x] .gitignore to exclude venv, debug files, .env
- [x] Health check endpoint at /health
- [x] Removed debug logging and file saves
- [x] README.md with deployment guide

## 📦 Files to Push to GitHub

```
hajri-ocr/
├── main.py                 # FastAPI app
├── table_extractor.py      # OCR + fuzzy matching
├── image_preprocessor.py   # Screenshot preprocessing
├── models.py               # Pydantic models
├── config.py               # Settings
├── ocr_config.py          # OCR configurations
├── interactive_tuning.py   # Tuning endpoints
├── imghdr_compat.py       # Image validation
├── course_config.json      # Course database
├── courses.html           # Course manager UI
├── test.html              # OCR test UI
├── tune.html              # Tuning UI
├── tuning_ui.html         # Alternative tuning UI
├── requirements.txt       # Dependencies
├── render.yaml            # Render config
├── .env.example           # Environment template
├── .gitignore            # Git ignore rules
└── README.md             # Documentation
```

## 🚫 Files to Exclude (already in .gitignore)

- venv/
- __pycache__/
- .env
- debug_preprocessed.png
- *.log
- table_extractor_old.py
- QUICK_START.md
- run.ps1

## 🚀 Deployment Steps

1. **Clean up workspace**
   ```bash
   rm debug_preprocessed.png
   rm -rf __pycache__
   ```

2. **Initialize Git (if not already)**
   ```bash
   git init
   git add .
   git commit -m "Production-ready OCR API with fuzzy matching"
   ```

3. **Push to GitHub**
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/hajri-ocr.git
   git push -u origin main
   ```

4. **Deploy to Render**
   - Go to https://render.com
   - New → Web Service
   - Connect GitHub repo
   - Render detects render.yaml automatically
   - Click "Create Web Service"
   - Wait 5-10 minutes for build

5. **Verify Deployment**
   - Check https://YOUR_APP.onrender.com/health
   - Should return: `{"status": "healthy", "service": "hajri-ocr-api"}`

## ⚙️ Environment Variables (Set in Render Dashboard)

Optional - defaults are production-ready:
- `LOG_LEVEL=info`
- `PORT=8000` (Render sets this automatically)

## 🧪 Test Production API

```bash
# Health check
curl https://YOUR_APP.onrender.com/health

# Upload test image
curl -X POST https://YOUR_APP.onrender.com/ocr/extract \
  -F "file=@test.png"

# View courses
curl https://YOUR_APP.onrender.com/courses
```

## 📱 Android App Integration

Update your Android app API base URL:
```kotlin
const val BASE_URL = "https://YOUR_APP.onrender.com/"
```

## 🔧 Troubleshooting

**Build fails?**
- Check Render logs
- Verify requirements.txt versions match Python 3.11

**OCR slow?**
- Expected: 2-5s per image on free tier
- Upgrade to paid tier for better CPU

**Out of memory?**
- Free tier has 512MB RAM limit
- Reduce image size in preprocessing if needed

## 🎯 Production Ready!

Your OCR API is now:
- ✅ Optimized for screenshots
- ✅ Auto-corrects OCR errors with fuzzy matching
- ✅ Database-driven course names
- ✅ Web UI for course management
- ✅ Health checks for monitoring
- ✅ Clean logging
- ✅ Production dependencies
