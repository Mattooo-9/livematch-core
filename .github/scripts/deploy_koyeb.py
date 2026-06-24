"""Deploy to Koyeb via API."""
import os, json, time, sys, base64, requests

GH_TOKEN   = os.environ.get("GITHUB_TOKEN","")
KOYEB_TOK  = os.environ.get("KOYEB_TOKEN","")
BOT_TOKEN  = os.environ["BOT_TOKEN"]
ADMIN_IDS  = os.environ.get("ADMIN_TG_IDS","8017348770")
DB_URL     = os.environ.get("DATABASE_URL","sqlite+aiosqlite:///./livematch.db")
REDIS_URL  = os.environ.get("REDIS_URL","redis://localhost:6379/0")
OR_KEY     = os.environ.get("OPENROUTER_API_KEY","")
SECRET     = os.environ.get("SECRET_KEY","change-me")
ADMIN_TOK  = os.environ.get("ADMIN_API_TOKEN","change-me")
IMAGE      = "ghcr.io/mattooo-9/livematch-core:latest"
GH_USER    = "Mattooo-9"
REPO       = "Mattooo-9/livematch-core"

logs = []
def log(m): print(m,flush=True); logs.append(m)

def write_status(data):
    if not GH_TOKEN: return
    c = base64.b64encode(json.dumps(data,indent=2).encode()).decode()
    ex = requests.get(f"https://api.github.com/repos/{REPO}/contents/deployment-status.json",
        headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json"})
    sha = ex.json().get("sha") if ex.ok else None
    body = {"message":"ci: koyeb deploy status","content":c,"branch":"main"}
    if sha: body["sha"] = sha
    requests.put(f"https://api.github.com/repos/{REPO}/contents/deployment-status.json",
        json=body, headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json"})

if not KOYEB_TOK:
    log("ERROR: KOYEB_TOKEN not set")
    write_status({"success":False,"error":"KOYEB_TOKEN missing","log":logs})
    sys.exit(1)

h = {"Authorization":f"Bearer {KOYEB_TOK}","Content-Type":"application/json"}
BASE = "https://app.koyeb.com/v1"

def koyeb(method, path, body=None):
    r = requests.request(method, BASE+path, json=body, headers=h, timeout=30)
    if not r.ok and r.status_code not in (404,409):
        log(f"  [{r.status_code}] {method} {path}: {r.text[:300]}")
    return r

try:
    log("=== Deploy to Koyeb (PRIMARY) ===")

    # Who am I
    me = koyeb("GET", "/account/profile")
    if not me.ok:
        raise RuntimeError(f"Invalid Koyeb token: {me.status_code} {me.text[:100]}")
    log(f"Koyeb account: {me.json().get('user',{}).get('email','?')}")

    # ghcr secret
    r = koyeb("POST", "/secrets", {
        "name":"ghcr-creds","type":"REGISTRY",
        "registry":{"username":GH_USER,"password":GH_TOKEN,"server":"ghcr.io"}
    })
    log(f"  ghcr secret: {r.status_code}")

    env = [
        {"key":"BOT_TOKEN","value":BOT_TOKEN},
        {"key":"ADMIN_TG_IDS","value":ADMIN_IDS},
        {"key":"DATABASE_URL","value":DB_URL},
        {"key":"REDIS_URL","value":REDIS_URL},
        {"key":"BOT_USE_WEBHOOK","value":"false"},
        {"key":"SECRET_KEY","value":SECRET},
        {"key":"ADMIN_API_TOKEN","value":ADMIN_TOK},
        {"key":"OPENROUTER_API_KEY","value":OR_KEY},
        {"key":"RUN_SCHEDULER_IN_API","value":"true"},
        {"key":"PYTHONUNBUFFERED","value":"1"},
        {"key":"WATCHDOG_MAX_MEM_MB","value":"380"},
        {"key":"NODE_ROLE","value":"primary"},
    ]

    # Check existing app
    apps = koyeb("GET", "/apps").json().get("apps",[])
    app = next((a for a in apps if a.get("name")=="livematch-core"), None)

    if not app:
        r = koyeb("POST", "/apps", {"name":"livematch-core"})
        log(f"  Create app: {r.status_code}")

    # Deploy service (bot worker)
    svc_def = {
        "app_name": "livematch-core",
        "definition": {
            "name": "bot",
            "type": "WORKER",
            "regions": ["fra"],
            "instance_types": [{"type":"nano"}],
            "scalings": [{"min":1,"max":1}],
            "docker": {"image":IMAGE,"command":"python scripts/run_bot.py","credentials_secret":"ghcr-creds"},
            "env": env,
        }
    }
    svcs = koyeb("GET", "/services").json().get("services",[])
    existing_bot = next((s for s in svcs if s.get("name")=="bot" and s.get("app_name")=="livematch-core"), None)

    if existing_bot:
        r = koyeb("PUT", f"/services/{existing_bot['id']}", {"definition": svc_def["definition"]})
        log(f"  Update bot service: {r.status_code}")
    else:
        r = koyeb("POST", "/services", svc_def)
        log(f"  Create bot service: {r.status_code} {r.text[:200]}")

    # Deploy API web service
    api_env = env.copy()
    api_env_list = [e for e in api_env if e["key"] != "NODE_ROLE"]
    api_env_list.append({"key":"NODE_ROLE","value":"primary-api"})
    api_env_list.append({"key":"RUN_SCHEDULER_IN_API","value":"false"})

    api_def = {
        "app_name": "livematch-core",
        "definition": {
            "name": "api",
            "type": "WEB",
            "regions": ["fra"],
            "instance_types": [{"type":"nano"}],
            "scalings": [{"min":1,"max":1}],
            "ports": [{"port":8000,"protocol":"http","path":"/"}],
            "health_checks": [{"http":{"path":"/health","port":8000}}],
            "docker": {"image":IMAGE,
                       "command":"sh -c 'alembic upgrade head && uvicorn app.api.main:app --host 0.0.0.0 --port 8000'",
                       "credentials_secret":"ghcr-creds"},
            "env": api_env_list,
        }
    }
    existing_api = next((s for s in svcs if s.get("name")=="api" and s.get("app_name")=="livematch-core"), None)
    if existing_api:
        r = koyeb("PUT", f"/services/{existing_api['id']}", {"definition": api_def["definition"]})
    else:
        r = koyeb("POST", "/services", api_def)
    log(f"  API service: {r.status_code}")

    log("✅ Koyeb deploy triggered")
    write_status({
        "success": True,
        "koyeb_bot": "https://livematch-core-mattooo-9.koyeb.app",
        "log": logs
    })

except Exception as e:
    import traceback; traceback.print_exc()
    log(f"FATAL: {e}")
    write_status({"success":False,"error":str(e),"log":logs})
    sys.exit(1)
