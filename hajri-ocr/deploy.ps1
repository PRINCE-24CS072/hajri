# Quick deployment script for hajri-ocr (PowerShell)

Write-Host "`n🚀 HAJRI OCR - GitHub Deployment" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""

# Check if git is initialized
if (!(Test-Path .git)) {
    Write-Host "📦 Initializing Git repository..." -ForegroundColor Yellow
    git init
    Write-Host "✅ Git initialized`n" -ForegroundColor Green
} else {
    Write-Host "✅ Git already initialized`n" -ForegroundColor Green
}

# Check for remote
$remoteExists = git remote get-url origin 2>$null
if (!$remoteExists) {
    Write-Host "❓ Enter your GitHub repository URL:" -ForegroundColor Cyan
    Write-Host "   Example: https://github.com/YOUR_USERNAME/hajri-ocr.git" -ForegroundColor Gray
    $repoUrl = Read-Host "   URL"
    git remote add origin $repoUrl
    Write-Host "✅ Remote added: $repoUrl`n" -ForegroundColor Green
} else {
    $currentRemote = git remote get-url origin
    Write-Host "✅ Remote already set: $currentRemote`n" -ForegroundColor Green
}

# Clean up files not needed in production
Write-Host "🧹 Cleaning up unnecessary files..." -ForegroundColor Yellow
if (Test-Path debug_*.png) { Remove-Item debug_*.png }
if (Test-Path *.log) { Remove-Item *.log }
if (Test-Path __pycache__) { Remove-Item -Recurse -Force __pycache__ }
if (Test-Path table_extractor_old.py) { Remove-Item table_extractor_old.py }
Write-Host "✅ Cleanup done`n" -ForegroundColor Green

# Show files to be committed
Write-Host "📋 Files ready to commit:" -ForegroundColor Cyan
git add .
git status --short

# Commit
Write-Host ""
$commitMsg = Read-Host "💬 Enter commit message (press Enter for default)"
if ([string]::IsNullOrWhiteSpace($commitMsg)) {
    $commitMsg = "Production-ready OCR API with fuzzy matching"
}
git commit -m $commitMsg
Write-Host "✅ Committed: $commitMsg`n" -ForegroundColor Green

# Push
Write-Host ""
$pushConfirm = Read-Host "🚀 Push to GitHub? (y/n)"
if ($pushConfirm -eq 'y') {
    try {
        git push -u origin main
    } catch {
        git push -u origin master
    }
    Write-Host "✅ Pushed to GitHub!`n" -ForegroundColor Green
    Write-Host "🎉 SUCCESS! Next steps:" -ForegroundColor Green
    Write-Host "   1. Go to https://render.com" -ForegroundColor White
    Write-Host "   2. Click 'New +' → 'Web Service'" -ForegroundColor White
    Write-Host "   3. Connect your GitHub repo" -ForegroundColor White
    Write-Host "   4. Render will auto-detect render.yaml" -ForegroundColor White
    Write-Host "   5. Click 'Create Web Service'" -ForegroundColor White
    Write-Host ""
    Write-Host "   Your API will be live in ~5-10 minutes!`n" -ForegroundColor Cyan
} else {
    Write-Host "⏸️  Skipped push. Run 'git push' manually when ready.`n" -ForegroundColor Yellow
}
