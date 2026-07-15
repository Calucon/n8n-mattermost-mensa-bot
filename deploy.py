#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request

WORKFLOWS_DIR = "workflows"
UPDATE_FIELDS = ("name", "nodes", "connections", "settings", "staticData")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_workflow(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_payload(workflow):
    return {k: workflow[k] for k in UPDATE_FIELDS if k in workflow}


def api_request(base_url, api_key, method, path, body=None):
    url = f"{base_url.rstrip('/')}/api/v1{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-N8N-API-KEY", api_key)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", errors="replace")}


def main():
    base_url = os.environ["N8N_BASE_URL"]
    api_key = os.environ["N8N_API_KEY"]
    dry_run = os.environ.get("DRY_RUN", "true").lower() == "true"
    only_file = os.environ.get("ONLY_FILE", "").strip()

    files = sorted(f for f in os.listdir(WORKFLOWS_DIR) if f.endswith(".json"))
    if only_file:
        files = [f for f in files if f == only_file]
        if not files:
            print(f"❌ No matching workflow file: {only_file}")
            sys.exit(1)

    print(f"{'🔍 Dry run' if dry_run else '🚀 Deploying'} against {base_url}\n")

    failures = 0
    for filename in files:
        path = os.path.join(WORKFLOWS_DIR, filename)
        workflow = load_workflow(path)
        wf_id = workflow.get("id")
        name = workflow.get("name", filename)

        if not wf_id:
            print(f"⚠️  SKIP {filename}: no 'id' field, cannot target an existing workflow")
            failures += 1
            continue

        status, current = api_request(base_url, api_key, "GET", f"/workflows/{wf_id}")
        if status != 200:
            print(f"❌ FAIL {filename}: could not fetch current workflow {wf_id} (HTTP {status}): {current}")
            failures += 1
            continue

        changed = (
            workflow.get("nodes") != current.get("nodes")
            or workflow.get("connections") != current.get("connections")
            or workflow.get("settings") != current.get("settings")
        )

        if dry_run:
            marker = "would UPDATE" if changed else "no changes"
            print(f"🔍 {filename} -> id={wf_id} name='{name}': {marker}")
            continue

        if not changed:
            print(f"⏭️  SKIP {filename}: no changes detected")
            continue

        payload = build_payload(workflow)
        status, result = api_request(base_url, api_key, "PUT", f"/workflows/{wf_id}", payload)
        if status == 200:
            print(f"✅ {filename} -> id={wf_id} name='{name}' updated")
        else:
            print(f"❌ FAIL {filename} -> id={wf_id}: HTTP {status}: {result}")
            failures += 1

    if failures:
        print(f"\n🏁 {failures} workflow(s) failed")
        sys.exit(1)
    print("\n🏁 All workflows processed successfully")


if __name__ == "__main__":
    main()
