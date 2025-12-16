# 🎯 HAJRI - Offline-First Attendance Tracker
## Complete Build Plan & Roadmap

---

## 📋 PROJECT OVERVIEW

**What we're building:** Zero-budget, offline-first Android attendance app for university students

**Core Philosophy:** Local device is source of truth. Cloud is optional backup.

**Budget:** $0 (literally)

---

## 🏗️ ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────┐
│                     STUDENT ANDROID APP                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Jetpack      │  │ Room DB      │  │ WorkManager  │      │
│  │ Compose UI   │  │ (SQLite)     │  │ + Alarms     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                           │                                  │
│                  [Offline-First Engine]                      │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │
                   (occasional sync)
                            │
┌───────────────────────────┼──────────────────────────────────┐
│                      SUPABASE (Free)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Auth         │  │ Postgres DB  │  │ Storage      │      │
│  │ (Google)     │  │ (read-only)  │  │ (backups)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└───────────────────────────┬──────────────────────────────────┘
                            │
                   (admin writes only)
                            │
┌───────────────────────────┼──────────────────────────────────┐
│                   ADMIN WEB DASHBOARD                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ React + Vite │  │ Timetable    │  │ Department   │      │
│  │              │  │ Management   │  │ Management   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────────────────────────────────────────────────┘
                            │
                   (OCR on-demand)
                            │
┌───────────────────────────┼──────────────────────────────────┐
│                 OCR BACKEND (Render Free)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ FastAPI      │  │ PaddleOCR    │  │ OpenCV       │      │
│  │              │  │ + Tesseract  │  │ Preprocessing│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎯 BUILD PHASES (REVISED - START WITH OCR)

### **PHASE 1: OCR BACKEND + TESTING (Week 1-2)** 🔥
*Prove the hardest part works first - no UI needed*

#### 1.1 Setup OCR Backend Project
- [ ] Create Python virtual environment
- [ ] Install FastAPI + PaddleOCR + Tesseract
- [ ] Setup project structure (see below)
- [ ] Add environment config (.env)
- [ ] Configure CORS for local testing

#### 1.2 Build Image Preprocessing Pipeline
```python
# image_preprocessor.py
- load_image(file_bytes): ndarray
- convert_to_grayscale(image): ndarray
- apply_thresholding(image): ndarray
- denoise_image(image): ndarray
- enhance_contrast(image): ndarray
- resize_if_needed(image, max_width=1920): ndarray
- preprocess_pipeline(image): ndarray
```

#### 1.3 Build OCR Service (Dual Engine)
```python
# ocr_service.py
- extract_text_paddleocr(image): List[TextBlock]
- extract_text_tesseract(image): str (fallback)
- combine_results(paddle_results, tesseract_results): str
- OCREngine class with error handling
```

#### 1.4 Build Attendance Parser (CORE LOGIC)
```python
# parser.py - Regex + confidence scoring
- find_course_codes(text): List[str]
- find_subject_names(text, codes): List[str]
- find_attendance_pairs(text): List[Tuple(attended, conducted)]
- detect_subject_type(text, context): str  # LECT/LAB
- calculate_confidence(match_data): float
- parse_attendance_table(ocr_text): List[AttendanceEntry]

# Patterns:
COURSE_CODE_PATTERN = r'\b[A-Z]{2,4}[- ]?\d{3,4}[A-Z]?\b'
ATTENDANCE_PATTERN = r'(\d{1,3})\s*[/\\]\s*(\d{1,3})'
TYPE_PATTERN = r'\b(LECT(?:URE)?|LAB(?:ORATORY)?|TUT(?:ORIAL)?)\b'
```

#### 1.5 Build FastAPI Endpoints
```python
# main.py
POST /ocr/extract
  - Accept: multipart/form-data (image file)
  - Process: preprocess → OCR → parse → confidence filter
  - Return: { subjects: [...], metadata: {...} }

POST /ocr/extract-base64
  - Accept: JSON { "image": "base64..." }
  - Same processing

GET /health
  - Return: { status: "ok", paddle: true, tesseract: true }

GET /test/sample
  - Process test images from /test_images/
  - Return accuracy metrics
```

#### 1.6 Testing & Validation
- [ ] Collect 10-15 real dashboard screenshots
- [ ] Create test suite (`pytest`)
- [ ] Test preprocessing variations
- [ ] Measure accuracy per screenshot
- [ ] Test confidence threshold tuning (60/70/80)
- [ ] Benchmark cold start time
- [ ] Test both OCR engines
- [ ] Document failure cases

**Deliverable:** Working OCR API with >80% accuracy on test images

---

### **PHASE 2: DATABASE + ADMIN DASHBOARD (Week 3-4)**
*Build the backend infrastructure*

#### 2.1 Setup Supabase Project
```sql
-- Full schema creation (see original Phase 3.1 for details)
- departments table
- semesters table  
- subjects table
- timetable_entries table
- users table
- user_backups table
- Row Level Security policies
```

#### 2.2 Build Admin Dashboard (React + Vite)
```jsx
// Core pages:
- Login (Google OAuth via Supabase)
- Departments CRUD
- Subjects CRUD (with CSV import)
- Timetable Editor (visual grid)
- Faculty/Rooms management
- Publish timetable (version bump)

// UI Library: shadcn/ui + Tailwind CSS
// State: Zustand
// Forms: React Hook Form
```

#### 2.3 Timetable Management Features
- [ ] Visual week grid (drag-drop slots)
- [ ] Batch filtering (A/B/C/D)
- [ ] Conflict detection (same room/time)
- [ ] Version history
- [ ] CSV bulk import
- [ ] Preview before publish

#### 2.4 Deploy Backend Services
- [ ] Deploy OCR backend to Render (free tier)
- [ ] Deploy admin dashboard to Netlify/Vercel
- [ ] Configure Supabase environment
- [ ] Test admin → Supabase → OCR flow
- [ ] Setup admin email whitelist

**Deliverable:** Admin can create full timetable + OCR API is live

---

### **PHASE 3: ANDROID APP - FAST BUILD (Week 5-6)**
*Use UI components library to ship quickly*

#### 3.1 Project Setup with Modern Stack
```kotlin
// Use Jetpack Compose + Material3
// UI Components: Compose Material3 + custom components
// Architecture: MVVM + Clean Architecture (simplified)
// DI: Hilt (or Koin if simpler)
```

#### 3.2 Core Data Layer (Room + Repository)
```kotlin
// Entities (see original plan)
- SubjectEntity
- TimetableEntryEntity  
- AttendanceRecordEntity
- UserConfigEntity

// Repositories:
- SubjectRepository
- TimetableRepository
- AttendanceRepository
- SyncRepository
```

#### 3.3 Attendance Calculation Engine
```kotlin
// Pure Kotlin math (no dependencies)
- AttendanceCalculator.kt (all formulas)
- TimetableEngine.kt (current/next lecture logic)
- AttendanceStats.kt (data class for results)
```

#### 3.4 Build UI Fast with Component Library
```kotlin
// Use pre-built components:
- Material3 Cards, Lists, Buttons
- Navigation Component
- Pull-to-refresh (accompanist)
- Charts library for stats (Vico/MPAndroidChart)

// Screens:
1. Login (Google Sign-In)
2. Subject List (LazyColumn with cards)
3. Subject Detail (stats + attendance buttons)
4. Timetable View (weekly grid)
5. OCR Upload (image picker + result table)
6. Settings (sync, backup, preferences)
```

#### 3.5 Integrate OCR Feature
- [ ] Image picker (camera/gallery)
- [ ] Upload to OCR backend
- [ ] Show loading (handle cold start)
- [ ] Display editable table
- [ ] Batch update Room DB

**Deliverable:** Functional offline-first app with OCR integration

---

### **PHASE 4: SMART FEATURES + POLISH (Week 7-8)**
*Notifications, widgets, sync - the finishing touches*

#### 4.1 Notifications System
```kotlin
// NotificationManager setup:
- Post-lecture reminder (30min after class ends)
- Evening summary (5-6 PM daily)
- Low attendance alerts (< 75%)
- Repeating reminders (if ignored)
- Notification actions (Mark Present/Absent directly)
```

#### 4.2 WorkManager Background Jobs
- [ ] Daily timetable check
- [ ] Periodic backup (weekly)
- [ ] Notification scheduler
- [ ] Cleanup old records

#### 4.3 Home Screen Widgets
```kotlin
// Two widgets:
1. Current Lecture Widget (4x2)
2. Stats Widget (4x1)
```

#### 4.4 Cloud Sync (Supabase)
- [ ] Timetable sync from cloud
- [ ] Backup/restore JSON
- [ ] Conflict resolution (local wins)

#### 4.5 Polish & Testing
- [ ] Offline mode testing
- [ ] Battery optimization
- [ ] UI polish (animations, transitions)
- [ ] Error handling
- [ ] User onboarding flow

**Deliverable:** Production-ready app with all features

---

## 📁 PROJECT STRUCTURE

### **Android App**
```
hajri-android/
├── app/
│   ├── src/main/
│   │   ├── java/com/hajri/
│   │   │   ├── data/
│   │   │   │   ├── local/
│   │   │   │   │   ├── dao/
│   │   │   │   │   ├── entities/
│   │   │   │   │   └── HajriDatabase.kt
│   │   │   │   ├── remote/
│   │   │   │   │   ├── SupabaseClient.kt
│   │   │   │   │   └── dto/
│   │   │   │   └── repository/
│   │   │   ├── domain/
│   │   │   │   ├── model/
│   │   │   │   ├── usecase/
│   │   │   │   └── AttendanceCalculator.kt
│   │   │   ├── ui/
│   │   │   │   ├── screens/
│   │   │   │   │   ├── login/
│   │   │   │   │   ├── subjects/
│   │   │   │   │   ├── detail/
│   │   │   │   │   ├── timetable/
│   │   │   │   │   └── settings/
│   │   │   │   ├── components/
│   │   │   │   └── theme/
│   │   │   ├── workers/
│   │   │   │   ├── SyncWorker.kt
│   │   │   │   ├── BackupWorker.kt
│   │   │   │   └── NotificationWorker.kt
│   │   │   ├── notifications/
│   │   │   │   └── NotificationHelper.kt
│   │   │   ├── widgets/
│   │   │   │   ├── CurrentLectureWidget.kt
│   │   │   │   └── StatsWidget.kt
│   │   │   └── HajriApp.kt
│   │   └── res/
│   └── build.gradle.kts
└── gradle/
```

### **OCR Backend**
```
hajri-ocr/
├── app/
│   ├── main.py
│   ├── ocr_service.py
│   ├── image_preprocessor.py
│   ├── parser.py
│   ├── models.py
│   └── config.py
├── tests/
├── requirements.txt
├── Dockerfile (for Render)
└── render.yaml
```

### **Admin Dashboard**
```
hajri-admin/
├── src/
│   ├── components/
│   │   ├── DepartmentManager.jsx
│   │   ├── SubjectManager.jsx
│   │   ├── TimetableEditor.jsx
│   │   └── AuthGuard.jsx
│   ├── pages/
│   │   ├── Login.jsx
│   │   ├── Dashboard.jsx
│   │   └── TimetableManagement.jsx
│   ├── services/
│   │   └── supabaseClient.js
│   ├── App.jsx
│   └── main.jsx
├── public/
├── package.json
└── vite.config.js
```

---

## 🔧 DEPENDENCIES

### **Android (build.gradle.kts)**
```kotlin
// Core
implementation("androidx.core:core-ktx:1.12.0")
implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.6.2")
implementation("androidx.activity:activity-compose:1.8.1")

// Compose
implementation(platform("androidx.compose:compose-bom:2023.10.01"))
implementation("androidx.compose.ui:ui")
implementation("androidx.compose.material3:material3")
implementation("androidx.compose.ui:ui-tooling-preview")

// Navigation
implementation("androidx.navigation:navigation-compose:2.7.5")

// Room
implementation("androidx.room:room-runtime:2.6.1")
implementation("androidx.room:room-ktx:2.6.1")
kapt("androidx.room:room-compiler:2.6.1")

// WorkManager
implementation("androidx.work:work-runtime-ktx:2.9.0")

// Networking
implementation("io.ktor:ktor-client-core:2.3.5")
implementation("io.ktor:ktor-client-cio:2.3.5")
implementation("io.ktor:ktor-client-content-negotiation:2.3.5")
implementation("io.ktor:ktor-serialization-kotlinx-json:2.3.5")

// Supabase
implementation("io.github.jan-tennert.supabase:postgrest-kt:2.0.0")
implementation("io.github.jan-tennert.supabase:storage-kt:2.0.0")
implementation("io.github.jan-tennert.supabase:gotrue-kt:2.0.0")

// Google Auth
implementation("com.google.android.gms:play-services-auth:20.7.0")
### **Android (build.gradle.kts) - Phase 3+**
```kotlin
// Core
implementation("androidx.core:core-ktx:1.12.0")
implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.6.2")
implementation("androidx.activity:activity-compose:1.8.1")

// Compose + Material3
implementation(platform("androidx.compose:compose-bom:2024.02.00"))
implementation("androidx.compose.ui:ui")
implementation("androidx.compose.material3:material3")
implementation("androidx.compose.ui:ui-tooling-preview")
implementation("androidx.compose.material:material-icons-extended")

// Navigation
implementation("androidx.navigation:navigation-compose:2.7.7")

// Room
implementation("androidx.room:room-runtime:2.6.1")
implementation("androidx.room:room-ktx:2.6.1")
ksp("androidx.room:room-compiler:2.6.1")  // Use KSP instead of kapt

// WorkManager
implementation("androidx.work:work-runtime-ktx:2.9.0")

// Networking (Ktor)
implementation("io.ktor:ktor-client-core:2.3.8")
implementation("io.ktor:ktor-client-cio:2.3.8")
implementation("io.ktor:ktor-client-content-negotiation:2.3.8")
implementation("io.ktor:ktor-serialization-kotlinx-json:2.3.8")

// Supabase
implementation("io.github.jan-tennert.supabase:postgrest-kt:2.1.3")
implementation("io.github.jan-tennert.supabase:storage-kt:2.1.3")
implementation("io.github.jan-tennert.supabase:gotrue-kt:2.1.3")

// Google Auth
implementation("com.google.android.gms:play-services-auth:21.0.0")

// Image Loading (Coil for Compose)
implementation("io.coil-kt:coil-compose:2.5.0")

// Charts (for attendance visualization)
implementation("com.patrykandpatrick.vico:compose-m3:1.13.1")

// Security
implementation("androidx.security:security-crypto:1.1.0-alpha06")

// Serialization
implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")

// Logging
### **OCR Backend (requirements.txt) - Phase 1**
```txt
# Core Framework
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-multipart==0.0.6

# OCR Engines
paddleocr==2.7.3
paddlepaddle==2.6.0  # CPU version (use paddlepaddle-gpu if needed)
pytesseract==0.3.10

# Image Processing
opencv-python-headless==4.9.0.80  # headless for server
pillow==10.2.0
numpy==1.24.4
### **Admin Dashboard (package.json) - Phase 2**
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.3",
    "@supabase/supabase-js": "^2.39.3",
    "zustand": "^4.5.0",
    "react-hot-toast": "^2.4.1",
    "lucide-react": "^0.314.0",
    "@tanstack/react-table": "^8.11.6",
    "date-fns": "^3.2.0",
    "react-hook-form": "^7.49.3",
    "zod": "^3.22.4",
    "@hookform/resolvers": "^3.3.4"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.0.11",
    "autoprefixer": "^10.4.17",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.3.3",
    "@types/react": "^18.2.48",
    "@types/react-dom": "^18.2.18"
  }
}
```
1. Pick ONE feature from current phase
2. Write data models first (entities/DTOs)
3. Implement business logic (pure Kotlin/Python)
4. Add UI/API layer last
5. Test locally (no cloud dependency)
6. Commit with clear message
7. Move to next feature
```

### **Testing Strategy**
```
Unit Tests (Priority):
- AttendanceCalculator (all math functions)
- OCR parser (regex patterns)
- Timetable logic (current/next lecture)

Integration Tests:
- Room database operations
- Supabase sync flow
- OCR end-to-end

Manual Tests:
- Offline mode (airplane mode)
- Widget updates
- Notifications
- Backup/restore
```

### **Git Workflow**
```
main
├── develop (daily work)
├── feature/attendance-engine
├── feature/notifications
├── feature/ocr-backend
└── hotfix/critical-bugs
```

---

## ⚠️ CRITICAL RULES

### **Never Break Offline-First**
- ✅ App launches without internet
- ✅ All features work without cloud
- ✅ Sync is optional enhancement
- ❌ Never block UI on network calls
- ❌ Never trust cloud data over local

### **Keep It Simple**
- ✅ Pure functions for calculations
- ✅ Clear variable names
- ✅ Comments for WHY, not WHAT
- ❌ No premature optimization
- ❌ No over-engineering

### **No Money Spent**
- ✅ Supabase free tier (500MB DB, 1GB storage)
- ✅ Render free tier (750 hours/month)
- ✅ GitHub Pages/Netlify free tier
- ❌ No paid APIs
- ❌ No paid hosting

---

## 📊 SUCCESS METRICS

### **Phase 1 Done When:**
- [ ] App stores subjects locally
- [ ] Attendance percentage calculates correctly
- [ ] UI shows subject list and details
- [ ] No crashes in offline mode

### **Phase 2 Done When:**
- [ ] Timetable shows current lecture
- [ ] Notifications appear on time
- [ ] Widgets update correctly
- [ ] App feels "smart" without user input

### **Phase 3 Done When:**
- [ ] Google login works
- [ ] Timetable syncs from cloud
- [ ] Backup creates valid JSON
- [ ] Restore recovers all data

### **Phase 4 Done When:**
- [ ] OCR extracts attendance correctly (>80% accuracy)
- [ ] Admin can create full timetable
- [ ] End-to-end flow works (admin → sync → student)
- [ ] App is deployed and accessible

---

## 🎯 IMMEDIATE NEXT STEPS

### **Right Now (Today):**
1. ✅ Review this plan (you're here)
2. Create Android project structure
3. Setup Room database
4. Implement AttendanceCalculator.kt
5. Build basic subject list UI

### **This Week:**
- Complete Phase 1 foundation
### **Phase 1 Done When:**
- [ ] OCR backend extracts text from screenshots
- [ ] Parser identifies course codes correctly (>80%)
- [ ] Attendance numbers extracted (>90%)
- [ ] Confidence scoring filters bad results
- [ ] API deployed and accessible via URL
- [ ] Test suite passes with real images

### **Phase 2 Done When:**
- [ ] Supabase schema created + policies set
- [ ] Admin can login with Google
- [ ] Admin can create departments/subjects/timetable
- [ ] Timetable data visible in Supabase
- [ ] OCR backend integrated with admin (optional)
- [ ] Admin dashboard deployed

### **Phase 3 Done When:**
- [ ] Android app shows subject list
- [ ] Attendance calculation works offline
- [ ] User can mark present/absent
- [ ] OCR upload flow works end-to-end
- [ ] Timetable syncs from Supabase
- [ ] App works fully offline after first sync

### **Phase 4 Done When:**
- [ ] Notifications trigger correctly
- [ ] Widgets update with live data
- [ ] Cloud backup/restore works
- [ ] App is polished and user-tested
- [ ] No major bugs in offline mode
- [ ] Ready for beta release
### **Why PaddleOCR?**
- Free, works offline (if self-hosted)
- Better for non-English text (some subjects have mixed text)
- Tesseract as fallback for reliability

### **Right Now (Today):**
1. ✅ Review this plan (you're here)
2. **Create OCR backend project**
3. Install PaddleOCR + dependencies
4. Build image preprocessing pipeline
5. Test with 1-2 dashboard screenshots

### **This Week:**
- Complete OCR extraction + parsing
- Build FastAPI endpoints
- Test with 10+ real screenshots
- Measure accuracy metrics
- Deploy to Render

### **Next Week:**
- Setup Supabase schema
- Build admin dashboard basics
- Connect admin → Supabase
- Test timetable CRUD flow
### **Compose UI Not Updating?**
- Use `remember` and `mutableStateOf`
- Check `LaunchedEffect` dependencies
- Verify ViewModel is hoisted correctly

### **OCR Low Accuracy?**
- Add preprocessing (grayscale, threshold, denoise)
- Try different confidence thresholds
- Check if image quality is sufficient
- Test with multiple screenshot samples

### **Supabase Auth Issues?**
- Verify redirect URLs in Supabase dashboard
- Check Google OAuth client ID configuration
- Test with Supabase logs (dashboard → Auth → Logs)

### **Notifications Not Showing?**
- Check notification permission granted
- Verify channel creation (Android 8+)
- Test with exact alarm permission
- Use `adb shell dumpsys notification` for debugging

---

## 🎉 YOU'RE READY

This plan is:
- ✅ Actionable (clear steps)
- ✅ Realistic (no magic dependencies)
- ✅ Zero-budget (all free tools)
- ✅ Offline-first (core principle maintained)
- ✅ Buildable (no missing pieces)

**No more planning. Start with Phase 1, Step 1.1.**

**Ship it. 🚀**
