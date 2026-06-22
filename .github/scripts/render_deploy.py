import os, json, time, sys, base64, traceback
import urllib.request, urllib.error

T = os.environ["RENDER_TOKEN"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_TG_IDS = os.environ.get("ADMIN_TG_IDS", "")
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")
SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())
ADMIN_TOKEN = os.environ.get("ADMIN_API_TOKEN", os.urandom(16).hex())
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
BASE = "https://api.render.com/v1"
log_lines = []

def log(msg): print(msg, flush=True); log_lines.append(msg)

def req(method, path, body=None, base=BASE, token=None, extra_headers=None):
    data = json.dumps(body).encode() if body else None
    t = token or T
    headers = {"Authorization": f"Bearer {t}", "Content-Type": "application/json", "Accept": "application/json"}
    if extra_headers: headers.update(extra_headers)
    r = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read(); return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        msg = e.read().decode()
        log(f"  [{e.code}] {method} {path}: {msg[:300]}")
        if e.code == 409: return {"_conflict": True}
        if e.code == 404: return None
        raise

def write_status(data):
    if not GH_TOKEN: return
    content = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
    try:
        existing = req("GET", "/repos/Mattooo-9/livematch-core/contents/deployment-status.json",
                      base="https://api.github.com", token=GH_TOKEN,
                      extra_headers={"Authorization": f"token {GH_TOKEN}"})
        sha = existing.get("sha") if existing else None
        body = {"message": "ci: deployment status", "content": content, "branch": "main"}
        if sha: body["sha"] = sha
        req("PUT", "/repos/Mattooo-9/livematch-core/contents/deployment-status.json",
            body=body, base="https://api.github.com", token=GH_TOKEN,
            extra_headers={"Authorization": f"token {GH_TOKEN}"})
    except Exception as e: log(f"  status write failed: {e}")

try:
    log("=== LiveMatch Render Deploy ===")

    # Owner
    owners = req("GET", "/owners?limit=1")
    owner_id = owners[0]["owner"]["id"]
    log(f"Owner: {owner_id}")

    # ── Postgres: берём ЛЮБУЮ существующую free DB ──────────────────────────
    dbs = req("GET", "/postgres?limit=10")
    log(f"Existing DBs: {[d.get('postgres',{}).get('name') for d in (dbs or [])]}")

    pg = None
    # Сначала ищем нашу по имени
    for d in (dbs or []):
        if d.get("postgres", {}).get("name") == "livematch-db":
            pg = d["postgres"]; break
    # Если нет - берём первую доступную (уже есть free db на аккаунте)
    if not pg and dbs:
        pg = dbs[0]["postgres"]
        log(f"Using existing DB: {pg.get('name')} ({pg.get('id')})")

    if not pg:
        # Нет вообще никакой - пробуем создать (может у них удалена)
        r = req("POST", "/postgres", {
            "name":"livematch-db","databaseName":"livematch","databaseUser":"livematch",
            "plan":"free","region":"frankfurt","ownerId":owner_id,"version":"15"
        })
        pg = r.get("postgres", r) if r and "_conflict" not in r else None

    if pg:
        pg_id = pg["id"]
        for _ in range(25):
            if pg.get("status") == "available": break
            time.sleep(10)
            r2 = req("GET", f"/postgres/{pg_id}")
            if r2: pg = r2.get("postgres", r2)
            log(f"  pg status: {pg.get('status')}")

        ci = pg.get("connectionInfo", {})
        db_url = ci.get("internalConnectionString") or ci.get("externalConnectionString") or ""
        db_url = db_url.replace("postgres://","postgresql+asyncpg://").replace("postgresql://","postgresql+asyncpg://")
        # Render internal URLs: если пустой - строим из деталей
        if not db_url:
            db_info = pg.get("databaseName","livematch")
            db_user = pg.get("databaseUser","livematch")
            db_host = pg.get("host") or f"dpg-{pg_id}-a.frankfurt-postgres.render.com"
            db_pass = ci.get("password","")
            db_url = f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}/{db_info}"
        log(f"DB URL: {db_url[:50]}...")
    else:
        db_url = "sqlite+aiosqlite:///./livematch.db"
        log("SQLite fallback")

    env = [
        {"key":"BOT_TOKEN","value":BOT_TOKEN},
        {"key":"ADMIN_TG_IDS","value":ADMIN_TG_IDS},
        {"key":"DATABASE_URL","value":db_url},
        {"key":"REDIS_URL","value":"redis://localhost:6379/0"},
        {"key":"BOT_USE_WEBHOOK","value":"false"},
        {"key":"SECRET_KEY","value":SECRET_KEY},
        {"key":"ADMIN_API_TOKEN","value":ADMIN_TOKEN},
        {"key":"OPENROUTER_API_KEY","value":OR_KEY},
        {"key":"RUN_SCHEDULER_IN_API","value":"true"},
        {"key":"PYTHONUNBUFFERED","value":"1"},
    ]

    # ── Service ─────────────────────────────────────────────────────────────
    svcs = req("GET", "/services?limit=20")
    svc = None
    for s in (svcs if isinstance(svcs, list) else []):
        if s.get("service", {}).get("name") == "livematch-core":
            svc = s["service"]; break

    if svc:
        sid = svc["id"]
        log(f"Service exists: {sid}")
        req("PUT", f"/services/{sid}/env-vars", env)
        req("POST", f"/services/{sid}/deploys", {"clearCache":"do_not_clear"})
        svc_url = f"https://{svc.get('serviceDetails',{}).get('url','livematch-core.onrender.com')}"
    else:
        log("Creating service...")
        r = req("POST", "/services", {
            "type":"web_service","name":"livematch-core","ownerId":owner_id,
            "repo":"https://github.com/Mattooo-9/livematch-core","branch":"main",
            "region":"frankfurt","plan":"free",
            "serviceDetails":{"runtime":"docker","dockerfilePath":"./Dockerfile",
                              "pullRequestPreviewsEnabled":"no","healthCheckPath":"/health"},
            "envVars":env,
        })
        log(f"Create result: {str(r)[:300]}")
        svc_url = "https://livematch-core.onrender.com"

    write_status({
        "success": True,
        "webapp_url": "https://mattooo-9.github.io/livematch-core/",
        "api_url": svc_url,
        "admin_api_token": ADMIN_TOKEN,
        "log": log_lines
    })
    log(f"✅ DEPLOYED → {svc_url}")

except Exception as e:
    log(f"FATAL: {e}"); traceback.print_exc()
    write_status({"success": False, "error": str(e), "log": log_lines})
    sys.exit(1)
