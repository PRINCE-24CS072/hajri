#!/bin/bash
# Quick deployment script for hajri-ocr

echo "🚀 HAJRI OCR - GitHub Deployment"
echo "================================"
echo ""

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "📦 Initializing Git repository..."
    git init
    echo "✅ Git initialized"
else
    echo "✅ Git already initialized"
fi

# Check for remote
if ! git remote get-url origin &> /dev/null; then
    echo ""
    echo "❓ Enter your GitHub repository URL:"
    echo "   Example: https://github.com/YOUR_USERNAME/hajri-ocr.git"
    read -p "   URL: " REPO_URL
    git remote add origin "$REPO_URL"
    echo "✅ Remote added: $REPO_URL"
else
    CURRENT_REMOTE=$(git remote get-url origin)
    echo "✅ Remote already set: $CURRENT_REMOTE"
fi

# Clean up files not needed in production
echo ""
echo "🧹 Cleaning up unnecessary files..."
rm -f debug_*.png
rm -f *.log
rm -rf __pycache__
echo "✅ Cleanup done"

# Show files to be committed
echo ""
echo "📋 Files ready to commit:"
git add .
git status --short

# Commit
echo ""
read -p "💬 Enter commit message (default: 'Production-ready OCR API'): " COMMIT_MSG
COMMIT_MSG=${COMMIT_MSG:-"Production-ready OCR API"}
git commit -m "$COMMIT_MSG"
echo "✅ Committed: $COMMIT_MSG"

# Push
echo ""
read -p "🚀 Push to GitHub? (y/n): " PUSH_CONFIRM
if [ "$PUSH_CONFIRM" = "y" ]; then
    git push -u origin main || git push -u origin master
    echo "✅ Pushed to GitHub!"
    echo ""
    echo "🎉 SUCCESS! Next steps:"
    echo "   1. Go to https://render.com"
    echo "   2. Click 'New +' → 'Web Service'"
    echo "   3. Connect your GitHub repo"
    echo "   4. Render will auto-detect render.yaml"
    echo "   5. Click 'Create Web Service'"
    echo ""
    echo "   Your API will be live in ~5-10 minutes!"
else
    echo "⏸️  Skipped push. Run 'git push' manually when ready."
fi
