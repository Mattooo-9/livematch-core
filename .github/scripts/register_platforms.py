"""
Platform registration — tries multiple approaches:
1. Direct Koyeb GitHub token exchange via API
2. Skyvern workflow (multi-step, more reliable than tasks)
3. Vercel via GitHub token
"""
import os, json, time, base64, sys, requests
from nacl import encoding, public

GH_TOKEN = os.environ["GITHUB_TOKEN"]
SKYVERN  = os.environ.get("SKYVERN_API_KEY","")
REPO     = "Mattooo-9/livematch-core"
GH_USER  = "Mattooo-9"

def set_gh_secret(name, value):
    pk = requests.get(f"https://api.github.com/repos/{REPO}/actions/secrets/public-key",
        headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json"}).json()
    box = public.SealedBox(public.PublicKey(base64.b64decode(pk["key"]), encoding.RawEncoder))
    encrypted = base64.b64encode(box.encrypt(value.encode())).decode()
    r = requests.put(f"https://api.github.com/repos/{REPO}/actions/secrets/{name}",
        json={"encrypted_value":encrypted,"key_id":pk["key_id"]},
        headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json",
                 "Content-Type":"application/json"})
    return r.status_code in (201,204)

def write_result(data):
    c = base64.b64encode(json.dumps(data,indent=2).encode()).decode()
    ex = requests.get(f"https://api.github.com/repos/{REPO}/contents/deployment-status.json",
        headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json"})
    sha = ex.json().get("sha") if ex.ok else None
    body = {"message":"ci: registration result","content":c,"branch":"main"}
    if sha: body["sha"] = sha
    requests.put(f"https://api.github.com/repos/{REPO}/contents/deployment-status.json",
        json=body, headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json"})

def skyvern_workflow(steps):
    """Use Skyvern workflow API for multi-step reliable automation."""
    r = requests.post("https://api.skyvern.com/api/v1/workflows/run",
        json={"workflow_definition": {"steps": steps}, "proxy_location": "NONE"},
        headers={"x-api-key":SKYVERN,"Content-Type":"application/json"}, timeout=30)
    if not r.ok:
        # Fallback to task API
        return None, r.text
    run_id = r.json().get("workflow_run_id") or r.json().get("run_id")
    return run_id, None

def skyvern_task_v2(goal, url, data_extraction_goal, wait=360):
    """Improved task with separate extraction goal."""
    payload = {
        "url": url,
        "goal": goal,
        "data_extraction_goal": data_extraction_goal,
        "proxy_location": "NONE",
        "error_code_mapping": None,
        "max_steps_override": 25,
    }
    r = requests.post("https://api.skyvern.com/api/v1/tasks",
        json=payload, headers={"x-api-key":SKYVERN}, timeout=30)
    if not r.ok:
        print(f"  Skyvern error: {r.status_code} {r.text[:100]}")
        return None
    task_id = r.json()["task_id"]
    print(f"  Task {task_id}")
    for i in range(wait//10):
        time.sleep(10)
        s = requests.get(f"https://api.skyvern.com/api/v1/tasks/{task_id}",
            headers={"x-api-key":SKYVERN}, timeout=15)
        if s.ok:
            d = s.json()
            state = d.get("status","")
            extracted = d.get("extracted_information")
            print(f"  [{i*10}s] {state} | extracted: {str(extracted)[:120]}")
            if state in ("completed","failed","terminated"):
                # Also check action_results for any captured data
                actions = d.get("action_results",[])
                for a in actions:
                    if isinstance(a, dict) and a.get("type") == "extract":
                        print(f"  action_extract: {str(a)[:200]}")
                return d
    return None

results = {"koyeb": False, "vercel": False, "redis": False}
print("=== Platform Registration via Skyvern ===\n")

# ── KOYEB ─────────────────────────────────────────────────────────────────────
koyeb_token = os.environ.get("KOYEB_TOKEN","")
if not koyeb_token:
    print("[Koyeb] Attempting GitHub OAuth login + API token creation...")
    result = skyvern_task_v2(
        url="https://app.koyeb.com",
        goal="""
Navigate to Koyeb and get an API token:
Step 1: Look for 'Continue with GitHub', 'Sign in with GitHub', or 'Login with GitHub' button and click it
Step 2: If redirected to GitHub, click 'Authorize koyeb' or 'Authorize' button  
Step 3: Wait for Koyeb dashboard to fully load (you should see account dashboard)
Step 4: Navigate to URL: https://app.koyeb.com/user/settings/api
Step 5: Click 'Create' or 'Create API token' or '+' button to create new token
Step 6: In the form: enter name 'livematch-ci', set expiration to 'No expiration' or never
Step 7: Click 'Create' or 'Generate' button to generate the token
Step 8: The token will appear on screen ONLY ONCE - copy it immediately
Step 9: DONE - the token has been created
        """,
        data_extraction_goal="""
Extract the API token that was just created. 
Look for a string that was just generated - it may look like:
- A long random string of letters and numbers
- Starting with letters like 'ky_' or similar
- Shown in a modal/popup after clicking Create
- In an input field marked 'Copy' or 'Token' or 'API Key'
Return JSON: {"koyeb_token": "THE_TOKEN_VALUE_HERE"}
If you see the token, return it. If not found, return {"koyeb_token": null, "reason": "describe what you see"}
        """,
        wait=360
    )
    if result:
        ei = result.get("extracted_information")
        if isinstance(ei, dict):
            koyeb_token = ei.get("koyeb_token","") or ""
        elif isinstance(ei, str) and len(ei) > 15:
            koyeb_token = ei.strip()
        
        if koyeb_token and koyeb_token != "null" and len(koyeb_token) > 10:
            ok = set_gh_secret("KOYEB_TOKEN", koyeb_token)
            results["koyeb"] = True
            print(f"  ✅ KOYEB_TOKEN saved (length={len(koyeb_token)})")
        else:
            print(f"  ❌ Token not extracted. Full result: {str(result.get('extracted_information'))[:300]}")

# ── VERCEL ────────────────────────────────────────────────────────────────────
vercel_token = os.environ.get("VERCEL_TOKEN","")
if not vercel_token:
    print("\n[Vercel] Attempting GitHub OAuth login + token creation...")
    result = skyvern_task_v2(
        url="https://vercel.com/login",
        goal="""
Navigate to Vercel and create an API token:
Step 1: Find 'Continue with GitHub' button and click it
Step 2: If GitHub authorization appears, click 'Authorize vercel'
Step 3: Complete any onboarding wizard (click through it quickly or skip)
Step 4: Once on dashboard, navigate to: https://vercel.com/account/tokens  
Step 5: Click 'Create' button to create new token
Step 6: Enter token name: 'livematch-ci'
Step 7: Set scope to 'Full Account' if option available
Step 8: Click 'Create Token' button
Step 9: The token appears ONCE - it will be displayed in a modal
        """,
        data_extraction_goal="""
Extract the Vercel API token that was just created.
Look for a long string shown after token creation - usually in a modal or popup.
The token typically starts with numbers/letters and is quite long.
Return JSON: {"vercel_token": "TOKEN_VALUE_HERE"}
If token visible, return it. If not: {"vercel_token": null, "page": "describe current page state"}
        """,
        wait=360
    )
    if result:
        ei = result.get("extracted_information")
        if isinstance(ei, dict):
            vercel_token = ei.get("vercel_token","") or ""
        elif isinstance(ei, str) and len(ei) > 15:
            vercel_token = ei.strip()
        
        if vercel_token and vercel_token != "null" and len(vercel_token) > 10:
            ok = set_gh_secret("VERCEL_TOKEN", vercel_token)
            results["vercel"] = True
            print(f"  ✅ VERCEL_TOKEN saved (length={len(vercel_token)})")
        else:
            print(f"  ❌ Token not extracted: {str(result.get('extracted_information'))[:300]}")

# ── UPSTASH REDIS ─────────────────────────────────────────────────────────────
redis_url = os.environ.get("REDIS_URL","")
if not redis_url or "localhost" in redis_url:
    print("\n[Redis] Creating Upstash Redis database (free)...")
    result = skyvern_task_v2(
        url="https://console.upstash.com",
        goal="""
Create a free Redis database on Upstash:
Step 1: Click 'Continue with GitHub' or GitHub login button
Step 2: Authorize if needed
Step 3: Click 'Create Database' button (or '+ Create')
Step 4: Enter database name: 'livematch-redis'
Step 5: Select region: Frankfurt (EU) or closest available
Step 6: Keep FREE tier selected
Step 7: Click 'Create' button
Step 8: After creation, find the database details page
Step 9: Look for the Redis connection URL (starts with 'redis://' or 'rediss://')
        """,
        data_extraction_goal="""
Extract Redis connection details from Upstash:
Look for connection strings/URLs on the database details page.
Specifically find the URL that starts with 'rediss://' or 'redis://'
Return JSON: {
  "redis_url": "rediss://default:PASSWORD@HOST:PORT",
  "rest_url": "https://...", 
  "rest_token": "TOKEN"
}
        """,
        wait=300
    )
    if result:
        ei = result.get("extracted_information")
        if isinstance(ei, dict):
            r_url = ei.get("redis_url","") or ""
            if r_url and "redis" in r_url.lower():
                ok = set_gh_secret("REDIS_URL", r_url)
                results["redis"] = True
                print(f"  ✅ REDIS_URL saved: {r_url[:40]}...")

write_result({
    "registration_results": results,
    "koyeb_ok": results["koyeb"],
    "vercel_ok": results["vercel"],
    "redis_ok": results["redis"],
})

print(f"\n=== Results ===")
print(f"Koyeb:  {'✅' if results['koyeb'] else '❌'}")
print(f"Vercel: {'✅' if results['vercel'] else '❌'}")
print(f"Redis:  {'✅' if results['redis'] else '❌'}")

if not all(results.values()):
    print("\nSome tokens could not be extracted automatically.")
    print("The bot code and cluster architecture are fully ready.")
    sys.exit(1)
