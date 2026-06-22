"""
Full Render deployment script - runs inside GitHub Actions.
Creates PostgreSQL DB + Web Service if they don't exist, then triggers deploy.
"""
import os, json, time, sys
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
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code} {method} {path}: {body[:300]}")
        if e.code == 409:  # already exists
            return None
        raise


def get_owner_id():
    owners = api("GET", "/owners?limit=1")
    return owners[0]["owner"]["id"]


def find_service(name):
    svcs = api("GET", f"/services?limit=20")
    for s in (svcs or []):
        if s.get("service", {}).get("name") == name:
            return s["service"]
    return None


def find_postgres(name):
    dbs = api("GET", "/postgres?limit=20")
    for d in (dbs or []):
        if d.get("postgres", {}).get("name") == name:
            return d["postgres"]
    return None


def wait_for_postgres(pg_id, timeout=180):
    print(f"  Waiting for PostgreSQL {pg_id} to be ready...")
    for _ in range(timeout // 10):
        db = api("GET", f"/postgres/{pg_id}")
        status = db.get("postgres", {}).get("status", "")
        print(f"  status: {status}")
        if status == "available":
            return db["postgres"]
        time.sleep(10)
    raise RuntimeError("PostgreSQL not ready in time")


def main():
    print("=== LiveMatch Core → Render Deploy ===")

    owner_id = get_owner_id()
    print(f"Owner: {owner_id}")

    # --- PostgreSQL ---
    pg = find_postgres("livematch-db")
    if pg:
        print(f"PostgreSQL already exists: {pg['id']}")
        if pg.get("status") != "available":
            pg = wait_for_postgres(pg["id"])
    else:
        print("Creating PostgreSQL (free)...")
        result = api("POST", "/postgres", {
            "name": "livematch-db",
            "databaseName": "livematch",
            "databaseUser": "livematch",
            "plan": "free",
            "region": "frankfurt",
            "ownerId": owner_id,
        })
        if result:
            pg = result.get("postgres", result)
            pg = wait_for_postgres(pg["id"])
        else:
            pg = find_postgres("livematch-db")

    db_url = pg.get("connectionInfo", {}).get("internalConnectionString") or \
             pg.get("databaseUrl") or ""
    # Convert to asyncpg URL
    db_url_async = db_url.replace("postgres://", "postgresql+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")
    print(f"DB URL ready: {db_url_async[:40]}...")

    # --- Web Service ---
    env_vars = [
        {"key": "BOT_TOKEN", "value": BOT_TOKEN},
        {"key": "ADMIN_TG_IDS", "value": ADMIN_TG_IDS},
        {"key": "DATABASE_URL", "value": db_url_async},
        {"key": "REDIS_URL", "value": "redis://localhost:6379/0"},  # fallback to in-memory
        {"key": "BOT_USE_WEBHOOK", "value": "false"},
        {"key": "SECRET_KEY", "value": SECRET_KEY},
        {"key": "ADMIN_API_TOKEN", "value": ADMIN_API_TOKEN},
        {"key": "OPENROUTER_API_KEY", "value": OPENROUTER_KEY},
        {"key": "RUN_SCHEDULER_IN_API", "value": "true"},
        {"key": "PYTHONUNBUFFERED", "value": "1"},
    ]

    svc = find_service("livematch-core")
    if svc:
        print(f"Service already exists: {svc['id']}")
        # Update env vars
        for ev in env_vars:
            try:
                api("PUT", f"/services/{svc['id']}/env-vars", env_vars)
                break
            except Exception:
                pass
        # Trigger redeploy
        try:
            api("POST", f"/services/{svc['id']}/deploys", {"clearCache": "do_not_clear"})
            print("Redeploy triggered.")
        except Exception as e:
            print(f"Redeploy: {e}")
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
                "dockerCommand": "./start.sh",
                "pullRequestPreviewsEnabled": False,
                "healthCheckPath": "/health",
            },
            "envVars": env_vars,
        })
        if result:
            svc = result.get("service", result)
            svc_url = f"https://{svc.get('serviceDetails', {}).get('url') or 'livematch-core.onrender.com'}"
            print(f"Service created: {svc_url}")

    print("\n=== Deploy complete ===")
    print(f"Admin token: {ADMIN_API_TOKEN}")
    print("Bot running in polling mode.")


if __name__ == "__main__":
    main()
