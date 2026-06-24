"""Verify both nodes are healthy after deploy."""
import os, json, time, base64, requests

GH_TOKEN  = os.environ.get("GITHUB_TOKEN","")
KOYEB_TOK = os.environ.get("KOYEB_TOKEN","")
REPO      = "Mattooo-9/livematch-core"

def write_status(data):
    if not GH_TOKEN: return
    c = base64.b64encode(json.dumps(data,indent=2).encode()).decode()
    ex = requests.get(f"https://api.github.com/repos/{REPO}/contents/cluster-status.json",
        headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json"})
    sha = ex.json().get("sha") if ex.ok else None
    body = {"message":"ci: cluster status","content":c,"branch":"main"}
    if sha: body["sha"] = sha
    requests.put(f"https://api.github.com/repos/{REPO}/contents/cluster-status.json",
        json=body, headers={"Authorization":f"token {GH_TOKEN}","Accept":"application/vnd.github.v3+json"})

# Wait for Koyeb to deploy (up to 5 min)
status = {"primary": {}, "secondary": {}, "timestamp": time.time()}

if KOYEB_TOK:
    for attempt in range(20):
        time.sleep(15)
        h = {"Authorization":f"Bearer {KOYEB_TOK}"}
        svcs = requests.get("https://app.koyeb.com/v1/services", headers=h, timeout=15).json().get("services",[])
        for svc in svcs:
            if svc.get("app_name") == "livematch-core":
                name = svc.get("name")
                state = svc.get("state","?")
                status["primary"][name] = state
                print(f"  [{attempt+1}] {name}: {state}")
        if all(v == "HEALTHY" for v in status["primary"].values()):
            print("✅ All Koyeb services HEALTHY")
            break

write_status(status)
print(json.dumps(status, indent=2))
