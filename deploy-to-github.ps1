# Deploy HAJRI project to GitHub (parent folder with hajri-ocr)

Write-Host "`n🚀 HAJRI PROJECT - GitHub Deployment" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Green
Write-Host "Deploying parent 'hajri' folder with hajri-ocr subfolder`n" -ForegroundColor Cyan

# Navigate to hajri parent folder
cd b:\hajri

# Check if git is initialized
if (!(Test-Path .git)) {
    Write-Host "📦 Initializing Git repository in hajri/..." -ForegroundColor Yellow
    git init
    Write-Host "✅ Git initialized`n" -ForegroundColor Green
} else {
    Write-Host "✅ Git already initialized`n" -ForegroundColor Green
}

# Check for remote
$remoteExists = git remote get-url origin 2>$null
if (!$remoteExists) {
    Write-Host "❓ Enter your GitHub repository URL:" -ForegroundColor Cyan
    Write-Host "   Example: https://github.com/YOUR_USERNAME/hajri.git" -ForegroundColor Gray
    $repoUrl = Read-Host "   URL"
    git remote add origin $repoUrl
    Write-Host "✅ Remote added: $repoUrl`n" -ForegroundColor Green
} else {
    $currentRemote = git remote get-url origin
    Write-Host "✅ Remote already set: $currentRemote`n" -ForegroundColor Green
}

# Clean up debug files in hajri-ocr
Write-Host "🧹 Cleaning up hajri-ocr debug files..." -ForegroundColor Yellow
cd hajri-ocr
if (Test-Path debug_*.png) { Remove-Item debug_*.png -Force }
if (Test-Path *.log) { Remove-Item *.log -Force }
if (Test-Path __pycache__) { Remove-Item -Recurse -Force __pycache__ }
if (Test-Path table_extractor_old.py) { Remove-Item table_extractor_old.py -Force }
if (Test-Path QUICK_START.md) { Remove-Item QUICK_START.md -Force }
if (Test-Path run.ps1) { Remove-Item run.ps1 -Force }
cd ..
Write-Host "✅ Cleanup done`n" -ForegroundColor Green

# Show file structure
Write-Host "📂 Repository structure:" -ForegroundColor Cyan
Write-Host "hajri/" -ForegroundColor White
Write-Host "├── README.md" -ForegroundColor Gray
Write-Host "├── BUILD_PLAN.md" -ForegroundColor Gray
Write-Host "└── hajri-ocr/" -ForegroundColor White
Write-Host "    ├── main.py (FastAPI app)" -ForegroundColor Gray
Write-Host "    ├── requirements.txt" -ForegroundColor Gray
Write-Host "    ├── render.yaml (Render config)" -ForegroundColor Gray
Write-Host "    └── ... (all OCR backend files)`n" -ForegroundColor Gray

# Show files to be committed
Write-Host "📋 Files ready to commit:" -ForegroundColor Cyan
git add .
git status --short

# Commit
Write-Host ""
$commitMsg = Read-Host "💬 Enter commit message (press Enter for default)"
if ([string]::IsNullOrWhiteSpace($commitMsg)) {
    $commitMsg = "Add HAJRI attendance system with OCR backend"
}
git commit -m "$commitMsg"
Write-Host "✅ Committed: $commitMsg`n" -ForegroundColor Green

# Push
Write-Host ""
$pushConfirm = Read-Host "🚀 Push to GitHub? (y/n)"
if ($pushConfirm -eq 'y') {
    git branch -M main 2>$null
    git push -u origin main 2>&1 | Out-Null
    
    if ($LASTEXITCODE -ne 0) {
        git push -u origin master 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Push failed. You may need to:" -ForegroundColor Red
            Write-Host "   1. Create the repo on GitHub first" -ForegroundColor Yellow
            Write-Host "   2. Verify the remote URL is correct" -ForegroundColor Yellow
            Write-Host "   3. Check your GitHub authentication" -ForegroundColor Yellow
            exit
        }
    }
    Write-Host "✅ Pushed to GitHub!`n" -ForegroundColor Green
    
    Write-Host "═══════════════════════════════════════" -ForegroundColor Green
    Write-Host "🎉 SUCCESS! Next Steps:" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════" -ForegroundColor Green
    Write-Host ""
    Write-Host "📦 Your code is now on GitHub!" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "🚀 Deploy hajri-ocr to Render:" -ForegroundColor Yellow
    Write-Host "   1. Go to https://render.com" -ForegroundColor White
    Write-Host "   2. Click 'New +' → 'Web Service'" -ForegroundColor White
    Write-Host "   3. Connect your GitHub repo" -ForegroundColor White
    Write-Host "   4. Set Root Directory: hajri-ocr" -ForegroundColor Cyan
    Write-Host "   5. Render will detect render.yaml automatically" -ForegroundColor White
    Write-Host "   6. Click 'Create Web Service'" -ForegroundColor White
    Write-Host ""
    Write-Host "⏱️  Build time: ~5-10 minutes" -ForegroundColor Gray
    Write-Host "🌐 Your API will be live at: https://YOUR_APP.onrender.com`n" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════`n" -ForegroundColor Green
    
    # Open GitHub and Render in browser
    $openBrowser = Read-Host "🌐 Open GitHub and Render in browser? (y/n)"
    if ($openBrowser -eq 'y') {
        Start-Process "https://github.com"
        Start-Sleep 1
        Start-Process "https://render.com"
        Write-Host "✅ Opened in browser`n" -ForegroundColor Green
    }
} else {
    Write-Host "⏸️  Skipped push. Run 'git push' manually when ready.`n" -ForegroundColor Yellow
}
