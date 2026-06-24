"""
Автоматическая регистрация на Koyeb и Vercel через GitHub OAuth (без пароля).
Запускается из GitHub Actions где есть полный интернет.
Результат — API токены записываются в GitHub Secrets.
"""
import os, json, time, base64, sys, requests
from nacl import encoding, public

GH_TOKEN = os.environ["GITHUB_TOKEN"]
SKYVERN  = os.environ["SKYVERN_API_KEY"]
REPO     = "Mattooo-9/livematch-core"
GH_USER  = "Mattooo-9"

def set_gh_secret(name, value):
    """Store token as GitHub Actions secret."""
    pk = requests.get(f"https://api.github.com/repos/{REPO}/actions/secrets/public-key",
        headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json"}).json()
    box = public.SealedBox(public.PublicKey(base64.b64decode(pk["key"]), encoding.RawEncoder))
    encrypted = base64.b64encode(box.encrypt(value.encode())).decode()
    r = requests.put(f"https://api.github.com/repos/{REPO}/actions/secrets/{name}",
        json={"encrypted_value":encrypted,"key_id":pk["key_id"]},
        headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json","Content-Type":"application/json"})
    return r.status_code in (201,204)

def skyvern(goal, url, wait=240):
    """Run Skyvern browser task, return extracted info."""
    r = requests.post("https://api.skyvern.com/api/v1/tasks",
        json={"url":url,"goal":goal,"proxy_location":"NONE"},
        headers={"x-api-key":SKYVERN}, timeout=30)
    if not r.ok:
        print(f"Skyvern error: {r.status_code} {r.text[:100]}")
        return None
    task_id = r.json()["task_id"]
    print(f"  Task {task_id} running...")
    for _ in range(wait//8):
        time.sleep(8)
        s = requests.get(f"https://api.skyvern.com/api/v1/tasks/{task_id}",
            headers={"x-api-key":SKYVERN}, timeout=15)
        if s.ok:
            d = s.json(); state = d.get("status","")
            print(f"    [{state}]", str(d.get("extracted_information",""))[:80])
            if state in ("completed","failed","terminated"):
                return d
    return None

print("=== Platform Registration ===")

# ── Koyeb ────────────────────────────────────────────────────────────────────
koyeb_token = os.environ.get("KOYEB_TOKEN","")
if not koyeb_token:
    print("\n[1/2] Registering on Koyeb via GitHub OAuth...")
    result = skyvern(
        url="https://app.koyeb.com",
        goal="""
        1. Click 'Continue with GitHub' or 'Sign in with GitHub' button
        2. If GitHub authorization page appears, click 'Authorize koyeb'
        3. Wait for Koyeb dashboard to load
        4. Navigate to https://app.koyeb.com/user/settings/api
        5. Click 'Create API token'  
        6. Set token name to 'livematch-github-actions'
        7. Set expiration to 'Never' or maximum available
        8. Click 'Create' or 'Generate'
        9. COPY the generated token value (it starts with 'ky_' usually)
        10. Return ONLY the token string in your response, nothing else
        """,
        wait=300
    )
    if result and result.get("status") == "completed":
        info = result.get("extracted_information") or result.get("action_results","")
        token = ""
        if isinstance(info, str) and len(info) > 10:
            token = info.strip().split()[-1]  # last word
        elif isinstance(info, dict):
            token = info.get("token") or info.get("api_token") or info.get("value","")
        if token and len(token) > 10:
            koyeb_token = token
            ok = set_gh_secret("KOYEB_TOKEN", token)
            print(f"  ✅ KOYEB_TOKEN saved to GitHub secrets: {ok}")
        else:
            print(f"  ⚠️  Could not extract token from: {info}")
    else:
        print(f"  ❌ Skyvern task failed: {result}")
else:
    print(f"  ✅ KOYEB_TOKEN already set")

# ── Vercel ────────────────────────────────────────────────────────────────────
vercel_token = os.environ.get("VERCEL_TOKEN","")
if not vercel_token:
    print("\n[2/2] Registering on Vercel via GitHub OAuth...")
    result = skyvern(
        url="https://vercel.com/login",
        goal="""
        1. Click 'Continue with GitHub' button
        2. If GitHub authorization page appears, click 'Authorize Vercel'  
        3. Complete any onboarding if shown (can skip or complete quickly)
        4. Wait for Vercel dashboard to load
        5. Navigate to https://vercel.com/account/tokens
        6. Click 'Create' token
        7. Set name to 'livematch-github-actions', scope 'Full Account'
        8. Click 'Create Token'
        9. COPY the generated token value
        10. Return ONLY the token string, nothing else
        """,
        wait=300
    )
    if result and result.get("status") == "completed":
        info = result.get("extracted_information") or result.get("action_results","")
        token = ""
        if isinstance(info, str) and len(info) > 10:
            token = info.strip().split()[-1]
        elif isinstance(info, dict):
            token = info.get("token") or info.get("value","")
        if token and len(token) > 10:
            vercel_token = token
            ok = set_gh_secret("VERCEL_TOKEN", token)
            print(f"  ✅ VERCEL_TOKEN saved to GitHub secrets: {ok}")
        else:
            print(f"  ⚠️  Could not extract token from: {info}")
    else:
        print(f"  ❌ Skyvern task failed: {result}")
else:
    print(f"  ✅ VERCEL_TOKEN already set")

# ── Upstash Redis ─────────────────────────────────────────────────────────────
redis_url = os.environ.get("REDIS_URL","")
if not redis_url or "localhost" in redis_url:
    print("\n[3/3] Creating Upstash Redis (free)...")
    # Upstash имеет публичный API для создания БД
    # Сначала попробуем через их REST API с GitHub OAuth
    result = skyvern(
        url="https://console.upstash.com/login",
        goal="""
        1. Click 'Continue with GitHub' or GitHub login button
        2. Authorize Upstash if prompted
        3. After dashboard loads, click 'Create Database'
        4. Set name: 'livematch-redis'
        5. Select region: 'EU-West-1' or closest European region
        6. Select FREE tier
        7. Click 'Create'
        8. After creation, go to the database page
        9. Find and copy the 'UPSTASH_REDIS_REST_URL' and 'UPSTASH_REDIS_REST_TOKEN'
        10. Also find the full Redis URL (starts with rediss://)
        11. Return JSON: {"redis_url": "rediss://...", "rest_url": "...", "rest_token": "..."}
        """,
        wait=240
    )
    if result and result.get("status") == "completed":
        info = result.get("extracted_information") or {}
        if isinstance(info, dict):
            redis_url = info.get("redis_url","")
            if redis_url:
                ok = set_gh_secret("REDIS_URL", redis_url)
                print(f"  ✅ REDIS_URL saved: {redis_url[:40]}...")
        elif isinstance(info, str) and "redis" in info.lower():
            print(f"  Got: {info[:200]}")

print("\n=== Registration complete ===")
print(f"Koyeb: {'✅' if koyeb_token else '❌'}")
print(f"Vercel: {'✅' if vercel_token else '❌'}")
print(f"Redis: {'✅' if redis_url and 'localhost' not in redis_url else '⚠️ using local'}")
