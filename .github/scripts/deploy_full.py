"""
Deploy LiveMatch Core:
1. Build Docker image already done by the workflow (ghcr.io)
2. Register/login to Koyeb via Skyvern browser automation → get API token
3. Deploy service via Koyeb API
"""
import os, json, time, sys, base64, traceback
import requests

GH_TOKEN   = os.environ.get("GITHUB_TOKEN","")
GH_USER    = "Mattooo-9"
REPO       = "Mattooo-9/livematch-core"
IMAGE      = f"ghcr.io/{GH_USER.lower()}/livematch-core:latest"
BOT_TOKEN  = os.environ["BOT_TOKEN"]
ADMIN_IDS  = os.environ.get("ADMIN_TG_IDS","")
OR_KEY     = os.environ.get("OPENROUTER_API_KEY","")
SECRET     = os.environ.get("SECRET_KEY", os.urandom(32).hex())
ADMIN_TOK  = os.environ.get("ADMIN_API_TOKEN", os.urandom(16).hex())
KOYEB_TOK  = os.environ.get("KOYEB_TOKEN","")
SKYVERN    = os.environ.get("SKYVERN_API_KEY","")

logs = []
def log(m): print(m,flush=True); logs.append(m)

def write_status(data):
    if not GH_TOKEN: return
    c = base64.b64encode(json.dumps(data,indent=2).encode()).decode()
    ex = requests.get(f"https://api.github.com/repos/{REPO}/contents/deployment-status.json",
        headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json"})
    sha = ex.json().get("sha") if ex.ok else None
    body = {"message":"ci: deploy status","content":c,"branch":"main"}
    if sha: body["sha"] = sha
    requests.put(f"https://api.github.com/repos/{REPO}/contents/deployment-status.json",
        json=body, headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json"})

def skyvern_task(goal, url, max_wait=180):
    r = requests.post("https://api.skyvern.com/api/v1/tasks",
        json={"url":url,"goal":goal,"proxy_location":"NONE","extract_data":True},
        headers={"x-api-key":SKYVERN,"Content-Type":"application/json"}, timeout=30)
    if not r.ok: 
        log(f"  Skyvern error: {r.status_code} {r.text[:200]}")
        return None
    task_id = r.json().get("task_id")
    log(f"  Skyvern task: {task_id}")
    for _ in range(max_wait//10):
        time.sleep(10)
        s = requests.get(f"https://api.skyvern.com/api/v1/tasks/{task_id}",
            headers={"x-api-key":SKYVERN}, timeout=15)
        if s.ok:
            d = s.json(); state = d.get("status","")
            log(f"    [{state}] {str(d.get('extracted_information',''))[:100]}")
            if state in ("completed","failed","terminated"):
                return d
    return None

try:
    log("=== LiveMatch Core → Koyeb Deploy ===")

    env_vars = {
        "BOT_TOKEN": BOT_TOKEN, "ADMIN_TG_IDS": ADMIN_IDS,
        "DATABASE_URL": "sqlite+aiosqlite:///./data/livematch.db",
        "REDIS_URL": "redis://localhost:6379/0",
        "BOT_USE_WEBHOOK": "false", "SECRET_KEY": SECRET,
        "ADMIN_API_TOKEN": ADMIN_TOK, "OPENROUTER_API_KEY": OR_KEY,
        "RUN_SCHEDULER_IN_API": "true", "PYTHONUNBUFFERED": "1",
    }

    # ── 1. Get Koyeb token ───────────────────────────────────────────────────
    if not KOYEB_TOK:
        log("Getting Koyeb token via Skyvern...")
        result = skyvern_task(
            url="https://app.koyeb.com/login",
            goal=(
                "Login to Koyeb using GitHub OAuth. "
                "Click 'Continue with GitHub' button. "
                "Authorize the GitHub app if prompted. "
                "After login, go to https://app.koyeb.com/user/settings/api "
                "and create a new API token named 'livematch-deploy'. "
                "Extract and return the token value."
            ),
            max_wait=240
        )
        if result and result.get("status") == "completed":
            extracted = result.get("extracted_information") or result.get("action_results",[{}])
            log(f"  Extracted: {str(extracted)[:300]}")
            # Try to find token in extracted data
            if isinstance(extracted, dict):
                KOYEB_TOK = extracted.get("token") or extracted.get("api_token") or extracted.get("value","")
            elif isinstance(extracted, str):
                KOYEB_TOK = extracted.strip()
            log(f"  Token preview: {KOYEB_TOK[:10]}..." if KOYEB_TOK else "  No token extracted")

    if not KOYEB_TOK:
        raise RuntimeError(
            "Could not get Koyeb token automatically. "
            "Please: 1) Go to https://app.koyeb.com/user/settings/api "
            "2) Create a token 3) Add as KOYEB_TOKEN GitHub secret "
            "4) Re-run this workflow"
        )

    # ── 2. Deploy via Koyeb API ──────────────────────────────────────────────
    h = {"Authorization":f"Bearer {KOYEB_TOK}","Content-Type":"application/json"}

    # Create ghcr secret
    r = requests.post("https://app.koyeb.com/v1/secrets", headers=h, timeout=20, json={
        "name":"ghcr-creds","registry":{
            "username":GH_USER,"password":GH_TOKEN,
            "server":"ghcr.io","type":"DOCKER_HUB"
        }
    })
    log(f"  Secret create: {r.status_code}")

    env_list = [{"key":k,"value":v} for k,v in env_vars.items()]

    # Check existing app
    apps = requests.get("https://app.koyeb.com/v1/apps", headers=h, timeout=15).json()
    app = next((a for a in apps.get("apps",[]) if a.get("name")=="livematch-core"), None)

    svc_def = {
        "name":"web","regions":["fra"],
        "instance_types":[{"type":"nano"}],
        "scalings":[{"min":1,"max":1}],
        "ports":[{"port":8000,"protocol":"http","path":"/"}],
        "health_checks":[{"http":{"path":"/health","port":8000}}],
        "docker":{"image":IMAGE,"command":"./start.sh","credentials_secret":"ghcr-creds"},
        "env":env_list,
    }

    if not app:
        r = requests.post("https://app.koyeb.com/v1/apps",
            json={"name":"livematch-core"}, headers=h, timeout=15)
        log(f"  App create: {r.status_code} {r.text[:100]}")

    r = requests.post("https://app.koyeb.com/v1/services",
        json={"app_name":"livematch-core","definition":svc_def}, headers=h, timeout=30)
    log(f"  Service deploy: {r.status_code} {r.text[:200]}")

    if r.ok:
        svc_url = "https://livematch-core-mattooo-9.koyeb.app"
        write_status({"success":True,"api_url":svc_url,
                      "webapp_url":"https://mattooo-9.github.io/livematch-core/",
                      "admin_token":ADMIN_TOK,"log":logs})
        log(f"✅ DEPLOYED → {svc_url}")
    else:
        raise RuntimeError(f"Service deploy failed: {r.status_code} {r.text[:300]}")

except Exception as e:
    log(f"FATAL: {e}"); traceback.print_exc()
    write_status({"success":False,"error":str(e),"log":logs})
    sys.exit(1)
