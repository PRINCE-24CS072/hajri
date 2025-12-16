# 🚀 Quick Deploy Guide

## ✅ Git is Ready!

Your code is committed and ready to push to GitHub.

## 📝 Next Steps

### 1. Create GitHub Repository

Go to https://github.com/new and create a new repository named **hajri**

### 2. Push to GitHub

Run these commands in PowerShell:

```powershell
cd b:\hajri

# Add your GitHub repo URL (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/hajri.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### 3. Deploy hajri-ocr to Render

1. Go to https://render.com
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository (**YOUR_USERNAME/hajri**)
4. **IMPORTANT**: Set **Root Directory** to `hajri-ocr`
5. Render will auto-detect `render.yaml`
6. Click **"Create Web Service"**

### 4. Wait for Deployment

- Build time: ~5-10 minutes
- Your API will be live at: `https://YOUR_APP.onrender.com`

### 5. Test Your API

```bash
# Health check
curl https://YOUR_APP.onrender.com/health

# Should return: {"status": "healthy", "service": "hajri-ocr-api"}
```

## 🎯 Important Render Settings

When creating the web service on Render:

- **Name**: hajri-ocr-api (or any name you want)
- **Root Directory**: `hajri-ocr` ← **CRITICAL!**
- **Environment**: Python
- **Build Command**: Auto-detected from render.yaml
- **Start Command**: Auto-detected from render.yaml
- **Plan**: Free

## 📱 Android App Integration

Once deployed, update your Android app API endpoint:

```kotlin
object ApiConfig {
    const val BASE_URL = "https://YOUR_APP.onrender.com/"
}
```

## 🔧 Manage Courses

Visit: `https://YOUR_APP.onrender.com/courses.html`

## ✨ Done!

Your HAJRI OCR backend is now live and ready for production! 🎉
