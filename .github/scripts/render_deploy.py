"""Render deployment script - runs inside GitHub Actions."""
import os, json, time, sys, traceback
import urllib.request, urllib.error

TOKEN = os.environ["RENDER_TOKEN"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_TG_IDS = os.environ.get("ADMIN_TG_IDS", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())
ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", os.urandom(16).hex())

BASE = "https://api.render.com/v1"


def api(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_bytes = e.read().decode()
        print(f"  HTTP {e.code} {method} {path}: {body_bytes[:500]}")
        if e.code in (409, 400):
            return {"_error": e.code, "_body": body_bytes}
        raise


def get_owner_id():
    owners = api("GET", "/owners?limit=1")
    print(f"  owners raw: {json.dumps(owners)[:200]}")
    if isinstance(owners, list):
        return owners[0]["owner"]["id"]
    return owners.get("owners", [{}])[0].get("owner", {}).get("id")


def find_service(name):
    svcs = api("GET", "/services?limit=20")
    if isinstance(svcs, list):
        for s in svcs:
            if s.get("service", {}).get("name") == name:
                return s["service"]
    return None


def find_postgres(name):
    dbs = api("GET", "/postgres?limit=20")
    print(f"  postgres raw: {json.dumps(dbs)[:300]}")
    if isinstance(dbs, list):
        for d in dbs:
            if d.get("postgres", {}).get("name") == name:
                return d["postgres"]
    return None


def wait_for_postgres(pg_id, timeout=240):
    print(f"  Waiting for PostgreSQL...")
    for i in range(timeout // 10):
        db = api("GET", f"/postgres/{pg_id}")
        pg = db.get("postgres", db) if isinstance(db, dict) else db
        status = pg.get("status", "unknown")
        print(f"  [{i*10}s] status: {status}")
        if status == "available":
            return pg
        time.sleep(10)
    raise RuntimeError("PostgreSQL not ready")


def main():
    print("=== LiveMatch Core → Render Deploy ===")
    
    try:
        owner_id = get_owner_id()
        print(f"Owner ID: {owner_id}")
    except Exception as e:
        print(f"ERROR getting owner: {e}")
        traceback.print_exc()
        sys.exit(1)

    # --- PostgreSQL ---
    pg = find_postgres("livematch-db")
    if pg and pg.get("status") == "available":
        print(f"✅ PostgreSQL exists and ready")
    elif pg:
        pg = wait_for_postgres(pg["id"])
    else:
        print("Creating PostgreSQL (free tier)...")
        result = api("POST", "/postgres", {
            "name": "livematch-db",
            "databaseName": "livematch",
            "databaseUser": "livematch",
            "plan": "free",
            "region": "frankfurt",
            "ownerId": owner_id,
            "version": "15",
        })
        print(f"  Create result: {json.dumps(result)[:300]}")
        if result and "_error" not in result:
            pg_obj = result.get("postgres", result)
            pg = wait_for_postgres(pg_obj["id"])
        else:
            # Maybe it was created despite error (409)
            pg = find_postgres("livematch-db")
            if pg:
                pg = wait_for_postgres(pg["id"])
            else:
                print("WARNING: Could not create PostgreSQL, will use SQLite fallback")
                pg = None

    if pg:
        conn_info = pg.get("connectionInfo", {})
        db_url = (conn_info.get("internalConnectionString") or 
                  conn_info.get("externalConnectionString") or
                  pg.get("connectionString", ""))
        db_url_async = db_url.replace("postgres://", "postgresql+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")
        print(f"  DB URL: {db_url_async[:50]}...")
    else:
        db_url_async = "sqlite+aiosqlite:///./livematch.db"
        print("  Using SQLite fallback")

    env_vars = [
        {"key": "BOT_TOKEN", "value": BOT_TOKEN},
        {"key": "ADMIN_TG_IDS", "value": ADMIN_TG_IDS},
        {"key": "DATABASE_URL", "value": db_url_async},
        {"key": "REDIS_URL", "value": "redis://localhost:6379/0"},
        {"key": "BOT_USE_WEBHOOK", "value": "false"},
        {"key": "SECRET_KEY", "value": SECRET_KEY},
        {"key": "ADMIN_API_TOKEN", "value": ADMIN_API_TOKEN},
        {"key": "OPENROUTER_API_KEY", "value": OPENROUTER_KEY},
        {"key": "RUN_SCHEDULER_IN_API", "value": "true"},
        {"key": "PYTHONUNBUFFERED", "value": "1"},
    ]

    # --- Web Service ---
    svc = find_service("livematch-core")
    if svc:
        print(f"✅ Service exists: {svc['id']}")
        # Update env vars and redeploy
        try:
            api("PUT", f"/services/{svc['id']}/env-vars", env_vars)
            print("  Env vars updated")
        except Exception as e:
            print(f"  Env var update: {e}")
        try:
            r = api("POST", f"/services/{svc['id']}/deploys", {"clearCache": "do_not_clear"})
            print(f"  Redeploy triggered: {json.dumps(r)[:100]}")
        except Exception as e:
            print(f"  Redeploy error: {e}")
    else:
        print("Creating web service...")
        result = api("POST", "/services", {
            "type": "web_service",
            "name": "livematch-core",
            "ownerId": owner_id,
            "repo": "https://github.com/Mattooo-9/livematch-core",
            "branch": "main",
            "region": "frankfurt",
            "plan": "free",
            "serviceDetails": {
                "runtime": "docker",
                "dockerfilePath": "./Dockerfile",
                "pullRequestPreviewsEnabled": "no",
                "healthCheckPath": "/health",
            },
            "envVars": env_vars,
        })
        print(f"  Result: {json.dumps(result)[:400]}")

    print("\n=== Deploy script finished ===")
    print(f"ADMIN_API_TOKEN={ADMIN_API_TOKEN}")
    print("Check: https://dashboard.render.com")

if __name__ == "__main__":
    main()
