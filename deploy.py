#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request

WORKFLOWS_DIR = "workflows"
UPDATE_FIELDS = ("name", "nodes", "connections", "settings", "staticData")
CREATE_FIELDS = ("name", "nodes", "connections", "settings")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_workflow(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_workflow(path, workflow):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
        f.write("\n")


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


def list_live_workflows(base_url, api_key):
    """Returns {name: id} for every workflow currently on the instance."""
    by_name = {}
    cursor = None
    while True:
        path = "/workflows?limit=250"
        if cursor:
            path += f"&cursor={cursor}"
        status, result = api_request(base_url, api_key, "GET", path)
        if status != 200:
            raise RuntimeError(f"failed to list live workflows (HTTP {status}): {result}")
        for wf in result.get("data", []):
            by_name[wf["name"]] = wf["id"]
        cursor = result.get("nextCursor")
        if not cursor:
            return by_name


def find_workflow_refs(nodes):
    """Yield each list-mode workflowId resource-locator dict found in these nodes."""
    for node in nodes:
        ref = node.get("parameters", {}).get("workflowId")
        if isinstance(ref, dict) and ref.get("__rl") and ref.get("mode") == "list":
            yield ref


def rewire_references(workflow, name_to_id, local_names):
    """Rewrite cross-workflow references to match current ids, resolved by name.

    Returns (changes, pending) where changes is a list of (ref_name, old_id, new_id)
    actually rewritten, and pending is a list of ref_names that reference a workflow
    which only exists locally (not live yet -- e.g. pending creation this run).
    Names that resolve to neither is a dangling reference and is returned in a third
    list, unresolved.
    """
    changes, pending, unresolved = [], [], []
    for ref in find_workflow_refs(workflow.get("nodes", [])):
        name = ref.get("cachedResultName")
        if name is None:
            continue
        if name in name_to_id:
            correct_id = name_to_id[name]
            if ref.get("value") != correct_id:
                changes.append((name, ref.get("value"), correct_id))
                ref["value"] = correct_id
                ref["cachedResultUrl"] = f"/workflow/{correct_id}"
        elif name in local_names:
            pending.append(name)
        else:
            unresolved.append(name)
    return changes, pending, unresolved


def main():
    base_url = os.environ["N8N_BASE_URL"]
    api_key = os.environ["N8N_API_KEY"]
    dry_run = os.environ.get("DRY_RUN", "true").lower() == "true"
    allow_create = os.environ.get("ALLOW_CREATE", "false").lower() == "true"
    only_file = os.environ.get("ONLY_FILE", "").strip()

    print(
        f"{'🔍 Dry run' if dry_run else '🚀 Deploying'} against {base_url}"
        f"{' (creation enabled)' if allow_create else ''}\n"
    )

    files = sorted(f for f in os.listdir(WORKFLOWS_DIR) if f.endswith(".json"))
    if only_file:
        files = [f for f in files if f == only_file]
        if not files:
            print(f"❌ No matching workflow file: {only_file}")
            sys.exit(1)

    workflows = {}
    for filename in files:
        path = os.path.join(WORKFLOWS_DIR, filename)
        workflows[filename] = (path, load_workflow(path))
    local_names = {wf.get("name") for _, wf in workflows.values()}

    try:
        name_to_id = list_live_workflows(base_url, api_key)
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)

    failures = 0
    skipped = set()
    resolved_id = {}
    to_save = []

    # Pass 1: resolve identity by name -- match against what's live, or create if missing
    for filename, (path, workflow) in workflows.items():
        name = workflow.get("name", filename)
        live_id = name_to_id.get(name)

        if live_id is not None:
            resolved_id[filename] = live_id
            if workflow.get("id") != live_id:
                workflow["id"] = live_id
                to_save.append(filename)
            continue

        if not allow_create:
            print(
                f"⏭️  SKIP {filename}: no live workflow named '{name}' and creation is "
                f"disabled (set ALLOW_CREATE=true to create it)"
            )
            skipped.add(filename)
            failures += 1
            continue

        if dry_run:
            print(f"🔍 {filename} -> name='{name}': would CREATE (no live workflow with this name yet)")
            continue

        payload = {k: workflow[k] for k in CREATE_FIELDS if k in workflow}
        status, result = api_request(base_url, api_key, "POST", "/workflows", payload)
        if status not in (200, 201):
            print(f"❌ FAIL {filename}: could not create '{name}' (HTTP {status}): {result}")
            skipped.add(filename)
            failures += 1
            continue

        new_id = result["id"]
        print(f"✨ CREATED {filename} -> name='{name}' assigned id={new_id}")
        resolved_id[filename] = new_id
        name_to_id[name] = new_id
        workflow["id"] = new_id
        to_save.append(filename)

    # Pass 2: rewire cross-workflow references now that names resolve to real ids
    for filename, (path, workflow) in workflows.items():
        if filename in skipped:
            continue
        changes, pending, unresolved = rewire_references(workflow, name_to_id, local_names)
        for name, old_id, new_id in changes:
            marker = "would REWIRE" if dry_run else "🔧 REWIRED"
            print(f"{marker} {filename}: reference to '{name}' {old_id} -> {new_id}")
        for name in pending:
            print(f"⏳ {filename}: reference to '{name}' can't be resolved yet (pending creation this run)")
        for name in unresolved:
            print(f"⚠️  {filename}: reference to '{name}' doesn't match any local or live workflow -- dangling reference")
            failures += 1
        if changes and filename not in to_save:
            to_save.append(filename)

    # Pass 3: push content for every workflow with a resolved (real) id
    for filename, (path, workflow) in workflows.items():
        if filename in skipped:
            continue
        wf_id = resolved_id.get(filename)
        if wf_id is None:
            continue  # dry-run pending-create placeholder; nothing live to diff against yet
        name = workflow.get("name", filename)

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

        payload = {k: workflow[k] for k in UPDATE_FIELDS if k in workflow}
        status, result = api_request(base_url, api_key, "PUT", f"/workflows/{wf_id}", payload)
        if status == 200:
            print(f"✅ {filename} -> id={wf_id} name='{name}' updated")
        else:
            print(f"❌ FAIL {filename} -> id={wf_id}: HTTP {status}: {result}")
            failures += 1

    if not dry_run and to_save:
        print("\n📝 Local files updated with new ids / rewired references -- review and commit these yourself:")
        for filename in to_save:
            path, workflow = workflows[filename]
            save_workflow(path, workflow)
            print(f"   - {filename}")

    if failures:
        print(f"\n🏁 {failures} workflow(s) failed")
        sys.exit(1)
    print("\n🏁 All workflows processed successfully")


if __name__ == "__main__":
    main()
