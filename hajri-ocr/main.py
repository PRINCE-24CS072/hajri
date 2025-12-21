"""
FastAPI OCR Backend for Hajri Attendance Tracker
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, Header, Form, Depends, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
import os
from pathlib import Path
import logging
import json
import time
import base64
import hmac
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

from config import settings
from models import OCRResponse
from table_extractor import TableExtractor

APP_DIR = Path(__file__).resolve().parent

# Load environment variables (use absolute path so it works regardless of CWD)
load_dotenv(dotenv_path=APP_DIR / ".env", override=False)

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


ENV = (os.getenv("ENV") or "").strip().lower()
IS_PROD = ENV in {"prod", "production"}

ENABLE_DEBUG_UI = _env_bool("ENABLE_DEBUG_UI", default=not IS_PROD)
ENABLE_DOCS = _env_bool("ENABLE_DOCS", default=not IS_PROD)

ADMIN_COOKIE_NAME = "hajri_admin"
ADMIN_SESSION_TTL_SECONDS = int(os.getenv("ADMIN_SESSION_TTL_SECONDS") or "28800")  # 8h

# Process metrics (best-effort, resets on restart)
BOOT_ID = uuid.uuid4().hex
STARTED_AT = datetime.now(timezone.utc)
TOTAL_REQUESTS = 0
PING_COUNT = 0
LAST_REQUEST_AT: Optional[datetime] = None


def _load_admin_users() -> dict:
    """Load admin users from env.

    Expected: ADMIN_USERS_JSON='{"alice":"pw1","bob":"pw2"}'

    Notes:
    - Values are treated as secrets; store them in Render "Secret" env vars.
    - This is for a personal/admin panel. If you need stronger auth, put the service
      behind an identity proxy (e.g. Cloudflare Access).
    """
    raw = (os.getenv("ADMIN_USERS_JSON") or "").strip()
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return {}
        users: dict = {}
        for k, v in obj.items():
            username = (k or "").strip()
            password = (v or "").strip() if isinstance(v, str) else ""
            if username and password:
                users[username] = password
        return users
    except Exception:
        return {}


def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0].strip().lower(), parts[1].strip()
    if scheme != "bearer":
        return None
    return token or None


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    padded = text + "=" * ((4 - (len(text) % 4)) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _admin_cookie_secret() -> Optional[bytes]:
    secret = (os.getenv("ADMIN_COOKIE_SECRET") or "").strip()
    if not secret:
        return None
    return secret.encode("utf-8")


def _is_debug_auth_configured() -> bool:
    has_cookie_auth = bool(_admin_cookie_secret() and _load_admin_users())
    has_header_auth = bool((os.getenv("DEBUG_ADMIN_KEY") or "").strip())
    return has_cookie_auth or has_header_auth


def _sign_admin_cookie(payload_b64: str, secret: bytes) -> str:
    return hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()


def _mint_admin_cookie(secret: bytes, ttl_seconds: int, username: str) -> str:
    now = int(time.time())
    payload = {
        "v": 1,
        "u": (username or "").strip(),
        "iat": now,
        "exp": now + max(60, int(ttl_seconds)),
    }
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _sign_admin_cookie(payload_b64, secret)
    return f"{payload_b64}.{sig}"


def _decode_admin_cookie(cookie_value: str, secret: bytes) -> Optional[dict]:
    try:
        parts = (cookie_value or "").split(".", 1)
        if len(parts) != 2:
            return None
        payload_b64, sig = parts[0], parts[1]
        expected_sig = _sign_admin_cookie(payload_b64, secret)
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload_raw = _b64url_decode(payload_b64)
        payload = json.loads(payload_raw.decode("utf-8"))
        exp = int(payload.get("exp") or 0)
        if exp <= int(time.time()):
            return None
        if not isinstance(payload, dict):
            return None
        return payload
    except Exception:
        return None


def require_app_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> None:
    expected = os.getenv("APP_API_KEY")
    if not expected:
        if IS_PROD:
            raise HTTPException(status_code=500, detail="Server misconfigured: APP_API_KEY missing")
        return

    token = _extract_bearer(authorization) or x_api_key
    if not token or token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _require_admin(request: Request, x_admin_key: Optional[str], authorization: Optional[str]) -> None:
    # Developer experience:
    # - In production: always require auth.
    # - In local/dev: if you haven't configured any admin auth yet, allow access.
    if not IS_PROD and not _is_debug_auth_configured():
        return

    # 1) Cookie session (browser-friendly)
    secret = _admin_cookie_secret()
    if secret:
        cv = request.cookies.get(ADMIN_COOKIE_NAME)
        if cv and _decode_admin_cookie(cv, secret):
            return

    # 2) Header-based admin key (automation / curl)
    expected = (os.getenv("DEBUG_ADMIN_KEY") or "").strip()
    token = _extract_bearer(authorization) or x_admin_key
    if expected and token and token == expected:
        return

    raise HTTPException(status_code=403, detail="Forbidden")


def require_admin(
    request: Request,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None),
) -> None:
    _require_admin(request, x_admin_key=x_admin_key, authorization=authorization)


def require_debug_admin(
    request: Request,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None),
) -> None:
    _ensure_debug_enabled()
    _require_admin(request, x_admin_key=x_admin_key, authorization=authorization)


def _ensure_debug_enabled() -> None:
    if not ENABLE_DEBUG_UI:
        raise HTTPException(status_code=404, detail="Not found")


def _ensure_debug_auth_configured() -> None:
    if not IS_PROD or not ENABLE_DEBUG_UI:
        return
    if not _load_admin_users():
        raise RuntimeError("ADMIN_USERS_JSON must be set when ENABLE_DEBUG_UI=true in production")
    if not (os.getenv("ADMIN_COOKIE_SECRET") or "").strip():
        raise RuntimeError("ADMIN_COOKIE_SECRET must be set when ENABLE_DEBUG_UI=true in production")


# Initialize FastAPI app
app = FastAPI(
    title="Hajri OCR API",
    description="Attendance extraction from university dashboard screenshots",
    version="2.0.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)


@app.get("/")
async def root():
    # Convenience entrypoint:
    # - When debug UI is enabled, go to admin login -> debug console.
    # - Otherwise, show the lightweight ping/status page.
    if ENABLE_DEBUG_UI:
        return RedirectResponse(url="/admin/login?next=/debug.html", status_code=303)
    return RedirectResponse(url="/ping.html", status_code=303)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Validate API credentials
if not settings.paddleocr_vl_api_url or not settings.paddleocr_vl_api_token:
    raise RuntimeError("API credentials missing in .env")

if IS_PROD and not os.getenv("APP_API_KEY"):
    raise RuntimeError("APP_API_KEY must be set in production")

_ensure_debug_auth_configured()

extractor = TableExtractor(
    api_url=settings.paddleocr_vl_api_url,
    api_token=settings.paddleocr_vl_api_token,
    api_options={
        "markdownIgnoreLabels": settings.paddleocr_markdown_ignore_labels,
        "useChartRecognition": settings.paddleocr_use_chart_recognition,
        "useRegionDetection": settings.paddleocr_use_region_detection,
        "useDocOrientationClassify": settings.paddleocr_use_doc_orientation_classify,
        "useDocUnwarping": settings.paddleocr_use_doc_unwarping,
        "useTextlineOrientation": settings.paddleocr_use_textline_orientation,
        "useSealRecognition": settings.paddleocr_use_seal_recognition,
        "useFormulaRecognition": settings.paddleocr_use_formula_recognition,
        "useTableRecognition": settings.paddleocr_use_table_recognition,
        "layoutThreshold": settings.paddleocr_layout_threshold,
        "layoutNms": settings.paddleocr_layout_nms,
        "layoutUnclipRatio": settings.paddleocr_layout_unclip_ratio,
        "textDetLimitType": settings.paddleocr_text_det_limit_type,
        "textDetLimitSideLen": settings.paddleocr_text_det_limit_side_len,
        "textDetThresh": settings.paddleocr_text_det_thresh,
        "textDetBoxThresh": settings.paddleocr_text_det_box_thresh,
        "textDetUnclipRatio": settings.paddleocr_text_det_unclip_ratio,
        "textRecScoreThresh": settings.paddleocr_text_rec_score_thresh,
        "sealDetLimitType": settings.paddleocr_seal_det_limit_type,
        "sealDetLimitSideLen": settings.paddleocr_seal_det_limit_side_len,
        "sealDetThresh": settings.paddleocr_seal_det_thresh,
        "sealDetBoxThresh": settings.paddleocr_seal_det_box_thresh,
        "sealDetUnclipRatio": settings.paddleocr_seal_det_unclip_ratio,
        "sealRecScoreThresh": settings.paddleocr_seal_rec_score_thresh,
        "useTableOrientationClassify": settings.paddleocr_use_table_orientation_classify,
        "useOcrResultsWithTableCells": settings.paddleocr_use_ocr_results_with_table_cells,
        "useE2eWiredTableRecModel": settings.paddleocr_use_e2e_wired_table_rec_model,
        "useE2eWirelessTableRecModel": settings.paddleocr_use_e2e_wireless_table_rec_model,
        "useWiredTableCellsTransToHtml": settings.paddleocr_use_wired_table_cells_trans_to_html,
        "useWirelessTableCellsTransToHtml": settings.paddleocr_use_wireless_table_cells_trans_to_html,
        "parseLanguage": settings.paddleocr_parse_language,
    }
)


def _load_course_db() -> dict:
    """Load course mapping from course_config.json (best-effort)."""
    try:
        config_path = APP_DIR / "course_config.json"
        if not config_path.exists():
            return {}
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        courses = cfg.get("courses")
        return courses if isinstance(courses, dict) else {}
    except Exception:
        return {}


# Load course map once at startup (endpoints will refresh as needed)
extractor.course_db = _load_course_db()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "hajri-ocr-api"}


@app.get("/debug.html")
async def serve_debug(request: Request):
    """Serve debug UI"""
    _ensure_debug_enabled()
    try:
        _require_admin(request, request.headers.get("X-Admin-Key"), request.headers.get("Authorization"))
    except HTTPException:
        return RedirectResponse(url="/admin/login?next=/debug.html", status_code=303)
    return FileResponse(str(APP_DIR / "debug.html"))


@app.get("/admin/login")
async def admin_login(next: Optional[str] = None, err: Optional[str] = None):
    _ensure_debug_enabled()

    # only allow relative paths
    nxt = (next or "/debug.html").strip()
    if not nxt.startswith("/"):
        nxt = "/debug.html"

    err_banner = "" if not err else "<div class=\"err\">Invalid username or password</div>"

    html = f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Admin Login</title>
<style>
    body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial; background:#0f1115; color:#fff; margin:0; padding:24px;}}
    .card{{max-width:420px; margin:60px auto; background:#171b21; border:1px solid rgba(255,255,255,.12); border-radius:12px; padding:18px;}}
    .h{{font-weight:800; margin:0 0 6px 0;}}
    .p{{opacity:.75; margin:0 0 14px 0; font-size:13px;}}
    .err{{margin:10px 0 12px 0; padding:10px 12px; border-radius:10px; border:1px solid rgba(239,68,68,.35); background:rgba(239,68,68,.12); color:rgba(255,255,255,.92); font-size:13px;}}
    input{{width:100%; padding:10px 12px; border-radius:10px; border:1px solid rgba(255,255,255,.18); background:rgba(255,255,255,.06); color:#fff;}}
    button{{margin-top:12px; width:100%; padding:10px 12px; border-radius:10px; border:1px solid rgba(255,255,255,.18); background:rgba(96,165,250,.22); color:#fff; font-weight:800; cursor:pointer;}}
    .hint{{opacity:.65; font-size:12px; margin-top:10px;}}
</style></head>
<body>
    <div class=\"card\">
        <h2 class=\"h\">Admin Login</h2>
        <p class=\"p\">Login to access debug tools.</p>
        {err_banner}
        <form method=\"post\" action=\"/admin/login\">
            <input type=\"text\" name=\"username\" placeholder=\"Username\" autocomplete=\"username\" required style=\"margin-bottom:10px;\" />
            <input type=\"password\" name=\"password\" placeholder=\"Password\" autocomplete=\"current-password\" required />
            <input type=\"hidden\" name=\"next\" value=\"{nxt}\" />
            <button type=\"submit\">Login</button>
        </form>
        
    </div>
</body></html>"""
    return HTMLResponse(content=html)


@app.post("/admin/login")
async def admin_login_post(username: str = Form(...), password: str = Form(...), next: Optional[str] = Form(None)):
    _ensure_debug_enabled()
    users = _load_admin_users()
    if not users:
        raise HTTPException(status_code=500, detail="Server misconfigured: ADMIN_USERS_JSON missing")

    u = (username or "").strip()
    p = (password or "").strip()
    expected_pw = users.get(u)
    if not expected_pw or not hmac.compare_digest(p, expected_pw):
        nxt = (next or "/debug.html").strip()
        if not nxt.startswith("/"):
            nxt = "/debug.html"
        return RedirectResponse(url=f"/admin/login?next={nxt}&err=1", status_code=303)

    secret = _admin_cookie_secret()
    if not secret:
        raise HTTPException(status_code=500, detail="Server misconfigured: ADMIN_COOKIE_SECRET missing")

    nxt = (next or "/debug.html").strip()
    if not nxt.startswith("/"):
        nxt = "/debug.html"

    cookie_value = _mint_admin_cookie(secret, ADMIN_SESSION_TTL_SECONDS, username=u)
    resp = RedirectResponse(url=nxt, status_code=303)
    resp.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        max_age=ADMIN_SESSION_TTL_SECONDS,
        path="/",
    )
    return resp


@app.get("/admin/me", dependencies=[Depends(require_debug_admin)])
async def admin_me(request: Request):
    secret = _admin_cookie_secret()
    username = None
    if secret:
        payload = _decode_admin_cookie(request.cookies.get(ADMIN_COOKIE_NAME) or "", secret)
        if payload:
            username = (payload.get("u") or "").strip() or None
    return {"authenticated": True, "username": username}


@app.post("/admin/refresh", dependencies=[Depends(require_debug_admin)])
async def admin_refresh(request: Request):
    secret = _admin_cookie_secret()
    if not secret:
        # If cookie auth isn't configured, nothing to refresh.
        return {"refreshed": False}

    payload = _decode_admin_cookie(request.cookies.get(ADMIN_COOKIE_NAME) or "", secret)
    username = (payload or {}).get("u") if payload else None
    username = (username or "").strip() or "admin"

    cookie_value = _mint_admin_cookie(secret, ADMIN_SESSION_TTL_SECONDS, username=username)
    resp = HTMLResponse(content="", status_code=204)
    resp.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=cookie_value,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        max_age=ADMIN_SESSION_TTL_SECONDS,
        path="/",
    )
    return resp


@app.post("/admin/logout")
async def admin_logout():
    resp = RedirectResponse(url="/admin/login?next=/debug.html", status_code=303)
    resp.delete_cookie(key=ADMIN_COOKIE_NAME, path="/")
    return resp


@app.get("/courses", dependencies=[Depends(require_debug_admin)])
async def list_courses():
    """Admin-only: list all configured courses."""
    return {"courses": extractor.course_db or {}}


@app.post("/courses/{code}", dependencies=[Depends(require_debug_admin)])
async def upsert_course(code: str, payload: dict = Body(...)):
    """Admin-only: add or update a course mapping."""
    course_code = (code or "").strip().upper()
    if not course_code:
        raise HTTPException(status_code=400, detail="Course code is required")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")

    name = (payload.get("name") or "").strip()
    abbr = (payload.get("abbr") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not abbr:
        raise HTTPException(status_code=400, detail="abbr is required")

    config_path = APP_DIR / "course_config.json"
    doc: dict = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                doc = json.load(f) if f.readable() else {}
        except Exception:
            doc = {}

    if not isinstance(doc, dict):
        doc = {}

    courses = doc.get("courses")
    if not isinstance(courses, dict):
        courses = {}

    courses[course_code] = {"name": name, "abbr": abbr}
    doc["courses"] = courses

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write course_config.json: {e}")

    extractor.course_db = _load_course_db()
    return {"ok": True, "code": course_code, "course": courses[course_code]}


@app.delete("/courses/{code}", dependencies=[Depends(require_debug_admin)])
async def delete_course(code: str):
    """Admin-only: delete a course mapping."""
    course_code = (code or "").strip().upper()
    if not course_code:
        raise HTTPException(status_code=400, detail="Course code is required")

    config_path = APP_DIR / "course_config.json"
    if not config_path.exists():
        return {"ok": True, "deleted": False}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read course_config.json: {e}")

    if not isinstance(doc, dict):
        doc = {}
    courses = doc.get("courses")
    if not isinstance(courses, dict):
        courses = {}

    deleted = course_code in courses
    if deleted:
        courses.pop(course_code, None)
        doc["courses"] = courses
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
                f.write("\n")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to write course_config.json: {e}")

    extractor.course_db = _load_course_db()
    return {"ok": True, "deleted": deleted}


@app.middleware("http")
async def _metrics_middleware(request: Request, call_next):
    global TOTAL_REQUESTS, LAST_REQUEST_AT
    TOTAL_REQUESTS += 1
    LAST_REQUEST_AT = datetime.now(timezone.utc)
    return await call_next(request)


def _uptime_seconds() -> int:
    return int((datetime.now(timezone.utc) - STARTED_AT).total_seconds())


def _fmt_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if d:
        return f"{d}d {h:02}h {m:02}m {s:02}s"
    return f"{h:02}h {m:02}m {s:02}s"


def _ping_data() -> dict:
        global PING_COUNT
        PING_COUNT += 1
        up = _uptime_seconds()
        return {
                "ok": True,
                "boot_id": BOOT_ID,
                "started_at": STARTED_AT.isoformat(),
                "uptime_seconds": up,
                "uptime": _fmt_duration(up),
                "total_requests": TOTAL_REQUESTS,
                "ping_count": PING_COUNT,
                "last_request_at": LAST_REQUEST_AT.isoformat() if LAST_REQUEST_AT else None,
                "note": "Counts reset when the server restarts.",
        }


def _render_ping_terminal(data: dict) -> HTMLResponse:
        now = datetime.now(timezone.utc).isoformat()
        ok = "OK" if data.get("ok") else "FAIL"
        html = f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Ping</title>
<style>
    :root{{
        --bg:#070a0e;
        --panel:#0b1016;
        --border:rgba(120,255,180,.18);
        --text:rgba(233,255,243,.92);
        --muted:rgba(233,255,243,.65);
        --green:rgba(120,255,180,.95);
        --green2:rgba(120,255,180,.18);
    }}
    html,body{{height:100%;}}
    body{{margin:0; background:radial-gradient(1200px 600px at 25% 0%, rgba(120,255,180,.08), transparent 55%), var(--bg);
             color:var(--text);
             font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;}}
    .wrap{{max-width:980px; margin:34px auto; padding:0 18px;}}
    .win{{border:1px solid var(--border); background:linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02)), var(--panel);
             border-radius:14px; overflow:hidden; box-shadow: 0 20px 60px rgba(0,0,0,.55);}}
    .bar{{display:flex; align-items:center; justify-content:space-between; gap:10px; padding:12px 14px;
             border-bottom:1px solid rgba(255,255,255,.08); background:rgba(255,255,255,.03);}}
    .dots{{display:flex; gap:8px; align-items:center;}}
    .dot{{width:10px; height:10px; border-radius:999px; background:rgba(255,255,255,.18);}}
    .title{{font-weight:900; letter-spacing:.02em; color:var(--muted); font-size:12px;}}
    .btns{{display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;}}
    .btn{{border:1px solid rgba(120,255,180,.22); background:rgba(120,255,180,.08); color:var(--text);
             padding:8px 10px; border-radius:10px; font-weight:900; text-decoration:none; cursor:pointer;}}
    .btn:hover{{background:rgba(120,255,180,.12);}}
    .screen{{padding:16px 14px 18px 14px;}}
    .line{{display:flex; gap:10px; align-items:flex-start; margin:8px 0;}}
    .prompt{{color:var(--green); user-select:none;}}
    .k{{min-width:180px; color:var(--muted);}}
    .v{{flex:1; word-break:break-word;}}
    .hr{{height:1px; background:rgba(255,255,255,.08); margin:14px 0;}}
    .badge{{display:inline-block; padding:2px 8px; border-radius:999px; border:1px solid var(--green2); color:var(--green);
                font-weight:900; font-size:12px;}}
    .foot{{margin-top:12px; color:var(--muted); font-size:12px;}}
</style></head>
<body>
    <div class=\"wrap\">
        <div class=\"win\">
            <div class=\"bar\">
                <div class=\"dots\"><span class=\"dot\"></span><span class=\"dot\"></span><span class=\"dot\"></span></div>
                <div class=\"title\">HAJRI :: STATUS TERMINAL</div>
                <div class=\"btns\">
                    <button class=\"btn\" type=\"button\" onclick=\"location.reload()\">Refresh</button>
                    <a class=\"btn\" href=\"/ping?format=json\">JSON</a>
                    <a class=\"btn\" href=\"/admin/login?next=/debug.html\">Admin Login</a>
                </div>
            </div>
            <div class=\"screen\">
                <div class=\"line\"><div class=\"prompt\">$</div><div class=\"v\">ping <span class=\"badge\">{ok}</span> <span style=\"color:var(--muted)\">@ {now}</span></div></div>
                <div class=\"hr\"></div>

                <div class=\"line\"><div class=\"prompt\">&gt;</div><div class=\"k\">boot_id</div><div class=\"v\">{data.get('boot_id')}</div></div>
                <div class=\"line\"><div class=\"prompt\">&gt;</div><div class=\"k\">started_at</div><div class=\"v\">{data.get('started_at')}</div></div>
                <div class=\"line\"><div class=\"prompt\">&gt;</div><div class=\"k\">uptime</div><div class=\"v\">{data.get('uptime')} ({data.get('uptime_seconds')}s)</div></div>
                <div class=\"line\"><div class=\"prompt\">&gt;</div><div class=\"k\">total_requests</div><div class=\"v\">{data.get('total_requests')}</div></div>
                <div class=\"line\"><div class=\"prompt\">&gt;</div><div class=\"k\">ping_count</div><div class=\"v\">{data.get('ping_count')}</div></div>
                <div class=\"line\"><div class=\"prompt\">&gt;</div><div class=\"k\">last_request_at</div><div class=\"v\">{data.get('last_request_at')}</div></div>
                <div class=\"foot\">{data.get('note')}</div>
            </div>
        </div>
    </div>
</body></html>"""
        return HTMLResponse(content=html)


@app.get("/ping")
async def ping(request: Request, format: Optional[str] = None):
        data = _ping_data()
        fmt = (format or "").strip().lower()
        if fmt == "html":
                return _render_ping_terminal(data)
        if fmt == "json":
                return data

        accept = (request.headers.get("accept") or "").lower()
        wants_html = "text/html" in accept and "application/json" not in accept
        if wants_html:
                return _render_ping_terminal(data)
        return data


@app.get("/ping.html")
async def ping_page():
        data = _ping_data()
        return _render_ping_terminal(data)


@app.post("/ocr/extract", response_model=OCRResponse, dependencies=[Depends(require_app_key)])
async def extract_attendance(file: UploadFile = File(...)):
    """Extract attendance entries from dashboard screenshot using PaddleOCR-VL API"""
    try:
        # Validate file type
        if not (file.content_type or "").startswith('image/'):
            raise HTTPException(400, "File must be an image")
        
        # Read and validate file size
        image_bytes = await file.read()
        size_mb = len(image_bytes) / (1024 * 1024)
        
        if size_mb > settings.max_image_size_mb:
            raise HTTPException(400, f"File too large: {size_mb:.2f}MB")
        
        # Decode image
        import numpy as np
        import cv2
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(400, "Invalid image file")
        
        logger.info(f"Image dimensions: {image.shape}")
        
        # Refresh courses from disk so changes to course_config.json apply without restart
        extractor.course_db = _load_course_db()

        # Extract using API
        entries = extractor.extract_table_data(image)
        
        return OCRResponse(
            success=True,
            message=f"Extracted {len(entries)} attendance entries",
            entries=entries
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR failed: {str(e)}")


@app.post("/ocr/extract/tuning", dependencies=[Depends(require_app_key)])
async def extract_attendance_tuning(
    file: UploadFile = File(...),
    x_tuning_params: Optional[str] = Header(None)
):
    """Legacy endpoint - redirects to main extract (API has no tuning params)"""
    return await extract_attendance(file)


@app.post("/ocr/debug")
async def debug_extraction(
    request: Request,
    file: UploadFile = File(...),
    api_options_override: Optional[str] = Form(None),
    course_db_override: Optional[str] = Form(None),
    _auth: None = Depends(require_debug_admin),
):
    """Debug endpoint - returns full API response and parsing details"""
    try:
        # require_debug_admin runs before handler
        if not (file.content_type or "").startswith('image/'):
            raise HTTPException(400, "File must be an image")
        
        image_bytes = await file.read()
        
        import numpy as np
        import cv2
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(400, "Invalid image file")
        
        # Refresh base course DB and apply optional overrides for this run
        base_course_db = _load_course_db()
        merged_course_db = dict(base_course_db) if isinstance(base_course_db, dict) else {}

        if course_db_override:
            try:
                override_obj = json.loads(course_db_override)
                if not isinstance(override_obj, dict):
                    raise ValueError("course_db_override must be a JSON object")
                merged_course_db.update(override_obj)
            except Exception as e:
                raise HTTPException(400, f"Invalid course_db_override JSON: {e}")

        merged_api_options = dict(extractor.api_options or {})
        if api_options_override:
            try:
                override_obj = json.loads(api_options_override)
                if not isinstance(override_obj, dict):
                    raise ValueError("api_options_override must be a JSON object")
                merged_api_options.update(override_obj)
            except Exception as e:
                raise HTTPException(400, f"Invalid api_options_override JSON: {e}")

        debug_extractor = TableExtractor(
            api_url=extractor.api_url,
            api_token=extractor.api_token,
            api_options=merged_api_options,
        )
        debug_extractor.course_db = merged_course_db

        # Build request payload once (and reuse it for the API call)
        file_data = debug_extractor._encode_image(image)
        request_payload = debug_extractor._build_payload(file_data=file_data)
        request_payload_sanitized = dict(request_payload)
        request_payload_sanitized["file"] = "<base64 omitted>"
        request_payload_sanitized["file_base64_length"] = len(file_data)

        # Call API directly
        t0 = time.perf_counter()
        api_result = debug_extractor._call_api(image, file_data=file_data)
        server_latency_ms = int((time.perf_counter() - t0) * 1000)
        
        # Get markdown
        markdown_text = api_result["layoutParsingResults"][0].get("markdown", {}).get("text", "")
        
        # Parse entries
        entries = debug_extractor._parse_markdown_to_entries(markdown_text)
        
        return {
            "success": True,
            "image_dimensions": {"width": image.shape[1], "height": image.shape[0]},
            "server_latency_ms": server_latency_ms,
            "request_payload": request_payload_sanitized,
            "api_response": api_result,
            "markdown_text": markdown_text,
            "markdown_length": len(markdown_text),
            "entries_found": len(entries),
            "entries": [e.dict() for e in entries],
            "parsing_details": {
                "has_layoutParsingResults": bool(api_result.get("layoutParsingResults")),
                "has_markdown": bool(markdown_text),
                "has_table_tag": "<table" in markdown_text,
                "has_img_tag": "<img" in markdown_text
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

