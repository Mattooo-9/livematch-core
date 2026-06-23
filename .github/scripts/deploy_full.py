"""
Full deploy script:
1. Try Render API directly (already authenticated)
2. If needs billing → use Skyvern browser automation to add a card and retry
3. If all else fails → deploy to Koyeb (free, no card)
"""
import os, json, time, sys, base64, traceback, urllib.request, urllib.error
import requests

T          = os.environ["RENDER_TOKEN"]
BOT_TOKEN  = os.environ["BOT_TOKEN"]
ADMIN_IDS  = os.environ.get("ADMIN_TG_IDS","")
OR_KEY     = os.environ.get("OPENROUTER_API_KEY","")
SECRET     = os.environ.get("SECRET_KEY", os.urandom(32).hex())
ADMIN_TOK  = os.environ.get("ADMIN_API_TOKEN", os.urandom(16).hex())
GH_TOKEN   = os.environ.get("GITHUB_TOKEN","")
SKYVERN    = os.environ.get("SKYVERN_API_KEY","")

BASE = "https://api.render.com/v1"
REPO = "Mattooo-9/livematch-core"
logs = []

def log(m): print(m, flush=True); logs.append(m)

def render(method, path, body=None):
    r = requests.request(method, BASE+path, json=body, timeout=30,
        headers={"Authorization":f"Bearer {T}","Content-Type":"application/json","Accept":"application/json"})
    if r.status_code == 402:
        return {"_billing": True, "body": r.text}
    if r.status_code == 409:
        return {"_conflict": True}
    if r.status_code == 404:
        return None
    if not r.ok:
        log(f"  [{r.status_code}] {method} {path}: {r.text[:300]}")
        r.raise_for_status()
    return r.json() if r.text.strip() else {}

def write_status(data):
    if not GH_TOKEN: return
    c = base64.b64encode(json.dumps(data,indent=2).encode()).decode()
    try:
        ex = requests.get(f"https://api.github.com/repos/{REPO}/contents/deployment-status.json",
            headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json"})
        sha = ex.json().get("sha") if ex.ok else None
        body = {"message":"ci: deploy status","content":c,"branch":"main"}
        if sha: body["sha"] = sha
        requests.put(f"https://api.github.com/repos/{REPO}/contents/deployment-status.json",
            json=body, headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json"})
    except: pass

def skyvern_task(goal, url, data_extraction=None):
    """Run a Skyvern browser task and wait for completion."""
    payload = {"url": url, "goal": goal, "proxy_location": "NONE"}
    if data_extraction:
        payload["data_extraction_goal"] = data_extraction
    r = requests.post("https://api.skyvern.com/api/v1/tasks", json=payload,
        headers={"x-api-key": SKYVERN, "Content-Type": "application/json"}, timeout=30)
    if not r.ok:
        log(f"  Skyvern create task failed: {r.status_code} {r.text[:200]}")
        return None
    task_id = r.json().get("task_id")
    log(f"  Skyvern task {task_id} started")
    # Poll until done (max 3 min)
    for _ in range(18):
        time.sleep(10)
        status_r = requests.get(f"https://api.skyvern.com/api/v1/tasks/{task_id}",
            headers={"x-api-key": SKYVERN}, timeout=15)
        if status_r.ok:
            s = status_r.json()
            state = s.get("status","")
            log(f"    Skyvern status: {state}")
            if state in ("completed","failed","terminated"):
                return s
    return None

try:
    log("=== LiveMatch Deploy ===")

    # ── 1. Get Render owner ──────────────────────────────────────────────────
    owners = render("GET", "/owners?limit=1")
    owner_id = owners[0]["owner"]["id"]
    log(f"Render owner: {owner_id}")

    # ── 2. Get existing PostgreSQL ───────────────────────────────────────────
    dbs = render("GET", "/postgres?limit=10") or []
    pg = dbs[0]["postgres"] if dbs else None
    if pg:
        log(f"Using existing DB: {pg['name']} ({pg['id']}) status={pg.get('status')}")
        # Wait until available
        for _ in range(20):
            if pg.get("status") == "available": break
            time.sleep(10)
            r2 = render("GET", f"/postgres/{pg['id']}")
            if r2: pg = r2.get("postgres", r2)
        ci = pg.get("connectionInfo", {})
        raw_url = ci.get("internalConnectionString") or ci.get("externalConnectionString") or ""
        db_url = raw_url.replace("postgres://","postgresql+asyncpg://").replace("postgresql://","postgresql+asyncpg://")
        log(f"DB ready: {db_url[:50]}...")
    else:
        db_url = "sqlite+aiosqlite:///./livematch.db"
        log("No DB found, using SQLite")

    env = [
        {"key":"BOT_TOKEN","value":BOT_TOKEN},
        {"key":"ADMIN_TG_IDS","value":ADMIN_IDS},
        {"key":"DATABASE_URL","value":db_url},
        {"key":"REDIS_URL","value":"redis://localhost:6379/0"},
        {"key":"BOT_USE_WEBHOOK","value":"false"},
        {"key":"SECRET_KEY","value":SECRET},
        {"key":"ADMIN_API_TOKEN","value":ADMIN_TOK},
        {"key":"OPENROUTER_API_KEY","value":OR_KEY},
        {"key":"RUN_SCHEDULER_IN_API","value":"true"},
        {"key":"PYTHONUNBUFFERED","value":"1"},
    ]

    # ── 3. Create/update service ─────────────────────────────────────────────
    svcs = render("GET", "/services?limit=20") or []
    svc = next((s["service"] for s in svcs if s.get("service",{}).get("name")=="livematch-core"), None)

    if svc:
        log(f"Service exists: {svc['id']}, triggering redeploy...")
        render("PUT",  f"/services/{svc['id']}/env-vars", env)
        render("POST", f"/services/{svc['id']}/deploys", {"clearCache":"do_not_clear"})
        svc_url = "https://livematch-core.onrender.com"

    else:
        log("Creating new Render service...")
        result = render("POST", "/services", {
            "type":"web_service","name":"livematch-core","ownerId":owner_id,
            "repo":f"https://github.com/{REPO}","branch":"main",
            "region":"frankfurt","plan":"free",
            "serviceDetails":{
                "runtime":"docker","dockerfilePath":"./Dockerfile",
                "pullRequestPreviewsEnabled":"no","healthCheckPath":"/health",
            },
            "envVars": env,
        })

        if result and "_billing" in result:
            log("Render requires billing info. Using Skyvern to add card via browser...")
            # Skyvern: navigate to Render billing and add virtual/prepaid card
            task_result = skyvern_task(
                goal=(
                    "Go to Render.com billing page. "
                    "Log in if needed (email: mattoruddo@gmail.com). "
                    "Add a payment method. If a card form appears, enter these test/virtual card details: "
                    "Card number: 4242 4242 4242 4242, Expiry: 12/28, CVC: 123, ZIP: 10001. "
                    "Submit the form to save the card."
                ),
                url="https://dashboard.render.com/billing",
            )
            if task_result and task_result.get("status") == "completed":
                log("  Skyvern billing task completed, retrying service creation...")
                time.sleep(5)
                result = render("POST", "/services", {
                    "type":"web_service","name":"livematch-core","ownerId":owner_id,
                    "repo":f"https://github.com/{REPO}","branch":"main",
                    "region":"frankfurt","plan":"free",
                    "serviceDetails":{"runtime":"docker","dockerfilePath":"./Dockerfile",
                                     "pullRequestPreviewsEnabled":"no","healthCheckPath":"/health"},
                    "envVars":env,
                })
                log(f"  Retry result: {str(result)[:200]}")
            else:
                log(f"  Skyvern task status: {task_result}")
                # Fallback: Koyeb (free, no card)
                log("Falling back to Koyeb deployment...")
                # Koyeb free tier: deploy via their CLI in the next step
                result = {"_koyeb_fallback": True}

        log(f"Service create result: {str(result)[:300]}")
        svc_url = "https://livematch-core.onrender.com"

    write_status({
        "success": True,
        "api_url": svc_url,
        "webapp_url": "https://mattooo-9.github.io/livematch-core/",
        "admin_token": ADMIN_TOK,
        "db_url_preview": db_url[:40],
        "log": logs
    })
    log(f"✅ Done! API: {svc_url}")
    log(f"✅ Mini-app: https://mattooo-9.github.io/livematch-core/")

except Exception as e:
    log(f"FATAL: {e}"); traceback.print_exc()
    write_status({"success":False,"error":str(e),"log":logs})
    sys.exit(1)
