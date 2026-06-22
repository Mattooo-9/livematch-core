"""Deploy to Render — runs from GitHub Actions runner (full internet access)."""
import os, json, time, sys
import urllib.request, urllib.error

T = os.environ["RENDER_TOKEN"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_TG_IDS = os.environ.get("ADMIN_TG_IDS", "")
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")
SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())
ADMIN_TOKEN = os.environ.get("ADMIN_API_TOKEN", os.urandom(16).hex())
BASE = "https://api.render.com/v1"

def req(method, path, body=None, expect_404_ok=False):
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
        headers={"Authorization": f"Bearer {T}", "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": "livematch-deploy/1.0"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        msg = e.read().decode()
        print(f"  [{e.code}] {method} {path}: {msg[:200]}")
        if e.code == 404 and expect_404_ok:
            return None
        if e.code == 409:
            return {"_conflict": True, "msg": msg}
        raise

# 1. Get owner
owners = req("GET", "/owners?limit=1")
print("owners raw:", str(owners)[:200])
if isinstance(owners, list):
    owner_id = owners[0]["owner"]["id"]
elif isinstance(owners, dict) and "owners" in owners:
    owner_id = owners["owners"][0]["owner"]["id"]
else:
    print("ERROR: unexpected owners response"); sys.exit(1)
print(f"Owner: {owner_id}")

# 2. PostgreSQL
dbs = req("GET", "/postgres?limit=10")
pg = None
if isinstance(dbs, list):
    for d in dbs:
        if d.get("postgres", {}).get("name") == "livematch-db":
            pg = d["postgres"]; break

if pg:
    print(f"✅ PostgreSQL exists: {pg['id']} status={pg.get('status')}")
else:
    print("Creating PostgreSQL...")
    r = req("POST", "/postgres", {
        "name": "livematch-db", "databaseName": "livematch", "databaseUser": "livematch",
        "plan": "free", "region": "frankfurt", "ownerId": owner_id, "version": "15"
    })
    print("  result:", str(r)[:200])
    if r and "_conflict" not in r:
        pg = r.get("postgres", r)
    else:
        # 409 = already exists, find it
        dbs2 = req("GET", "/postgres?limit=10")
        for d in (dbs2 if isinstance(dbs2, list) else []):
            if d.get("postgres", {}).get("name") == "livematch-db":
                pg = d["postgres"]; break

if pg:
    for _ in range(30):
        if pg.get("status") == "available":
            break
        time.sleep(10)
        pg_r = req("GET", f"/postgres/{pg['id']}")
        pg = pg_r.get("postgres", pg_r) if isinstance(pg_r, dict) else pg
        print(f"  pg status: {pg.get('status')}")
    ci = pg.get("connectionInfo", {})
    db_url = ci.get("internalConnectionString") or ci.get("externalConnectionString") or ""
    db_url = db_url.replace("postgres://","postgresql+asyncpg://").replace("postgresql://","postgresql+asyncpg://")
    print(f"  DB: {db_url[:50]}...")
else:
    db_url = "sqlite+aiosqlite:///./data/livematch.db"
    print("  Using SQLite fallback")

# 3. Web service
svcs = req("GET", "/services?limit=20")
svc = None
if isinstance(svcs, list):
    for s in svcs:
        if s.get("service", {}).get("name") == "livematch-core":
            svc = s["service"]; break

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

if svc:
    sid = svc["id"]
    print(f"✅ Service exists: {sid}")
    req("PUT", f"/services/{sid}/env-vars", env)
    print("  Env updated")
    dep = req("POST", f"/services/{sid}/deploys", {"clearCache":"do_not_clear"})
    print(f"  Deploy triggered: {str(dep)[:100]}")
else:
    print("Creating service...")
    r = req("POST", "/services", {
        "type": "web_service", "name": "livematch-core", "ownerId": owner_id,
        "repo": "https://github.com/Mattooo-9/livematch-core", "branch": "main",
        "region": "frankfurt", "plan": "free",
        "serviceDetails": {
            "runtime": "docker", "dockerfilePath": "./Dockerfile",
            "pullRequestPreviewsEnabled": "no", "healthCheckPath": "/health",
        },
        "envVars": env,
    })
    print("  Service result:", str(r)[:300])

print("\n✅ Deploy script done")
print(f"   Bot running at: https://livematch-core.onrender.com")
print(f"   Mini-app: https://mattooo-9.github.io/livematch-core/")
