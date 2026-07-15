# 🤖 HCI Group Mattermost Lunch Bot (Uni Konstanz Mensa)

An automated, multi-workflow n8n system built for the **HCI Group Mattermost instance** (`https://hci2.uni-konstanz.de`). This bot parses the official Seezeit XML meal plan for the **Mensa Gießberg**, formats it into clean markdown tables, and handles customized, interactive user alerts (keyword tracking) via Mattermost interactive dialogs and slash commands.

---

## 🏗️ Architecture Overview

The system uses a decoupled **Parent-Child (Hub and Spoke)** architecture to maximize efficiency and reduce webhook parsing overhead.

* **The Router (`Mensa Food.json`)**: Acts as the central listener. It catches all incoming Slack-compatible webhook payloads from Mattermost (slash commands, button clicks, and dialog submissions) and uses conditional switch blocks to route traffic to specific sub-workflows.
* **The Workers**: Independent modular sub-workflows that execute targeted tasks (e.g., pulling data, editing database rows, formatting message responses) before pushing notifications back to Mattermost.

---

## 🗂️ File Manifest

* **`Mensa Food.json`**: The master entry-point webhook handler and command switch router.
* **`Mensa Food Show Menu.json`**: Pulls the raw Seezeit XML feed, maps diet categories, parses icons, matches user keywords, and builds the primary Slack-compatible channel markdown layout.
* **`Mensa Food List.json`**: Fetches and renders active keyword alerts for a requesting individual with custom action layout strings.
* **`Mensa Food Help.json`**: Formats the markdown syntax formatting assistance layout block.
* **`Mensa Food Notify.json`**: Validates parameters and performs upsert operations for meal subscriptions.
* **`Mensa Food UnNotify.json`**: Manages explicit string row deletions from tracking indexes.
* **`Get Private Channel ID.json`**: Evaluates active bot tracking variables to open a direct DM conversation hook.
* **`Open Add Alert Dialog.json`**: Generates the structural payload for the interactive popup UI context form in Mattermost.
* **`clean.py`**: A helper script to automatically strip testing artifacts (`pinData`) and normalize JSON indentation across workflows.

---

## ⚠️ Vital Maintainer Notice: Stripping `pinData`

> [!IMPORTANT]
> Before pushing changes or modifications to a public git tracking tree, **ensure all test payloads are removed**.

n8n natively bundles testing contexts inside a parameter block called `pinData`. If uncleaned, these files contain live session webhooks, execution IDs, and individual tracking metrics (user_ids, explicit channel tokens, etc.).

To avoid accidentally committing private credentials or execution tracking states, utilize the bundled `clean.py` script.

### Using the Sanitization Script (`clean.py`)

Run the script from the root of the repository to clear `pinData` configurations and format all workflow JSON files with a standard 2-space indentation style:

```bash
python3 clean.py
```

### Automating with a Git Pre-Commit Hook

To guarantee no maintainer ever accidentally leaks session keys or user tokens, set up a local git pre-commit hook. Create or edit `.git/hooks/pre-commit` and populate it with:

```bash
#!/bin/sh
python3 clean.py
git add *.json

```

Make it executable by running:

```bash
chmod +x .git/hooks/pre-commit

```

---

## 🚀 Setup & Deployment Guide

### 1. Database Creation

The system manages states natively using n8n Data Tables. While the master runtime configuration file `Mensa Food.json` contains a validation constructor that automatically initiates structural table logic, maintainers should verify that an internal table titled `Mensa_Food_Notifications` exists with the following columns:

* `user_id` (String)
* `query` (String)
* `diet` (String)

### 2. Mattermost Integration Configuration

On your target Mattermost platform, register a new **Slash Command**:

* **Command Name**: `/lunch`
* **Request URL**: Point this to the production webhook generation target specified inside your live `Mensa Food.json` node context block.
* **Request Method**: `POST`

### 3. Workflow Import Progression Sequence

Because dependency logic builds outward, files should be imported into your target n8n engine in this specific sequence to ensure no validation references are dropped:

1. Import all seven child context scripts (`Mensa Food Show Menu.json`, `Mensa Food List.json`, `Mensa Food Help.json`, `Mensa Food Notify.json`, `Mensa Food UnNotify.json`, `Get Private Channel ID.json`, and `Open Add Alert Dialog.json`).
2. Import the main orchestration script: `Mensa Food.json`.
3. Open the newly imported parent workflow `Mensa Food.json`. Open each individual `Execute Workflow` node block, click the dropdown picker interface, and manually re-select the respective child sub-workflows to bind them to your local installation IDs.

---

## 🔄 Deploying Updates to a Live Instance

Once your workflows are imported (see above) and their IDs are baked into the JSON files, subsequent edits can be pushed straight to your running n8n instance via its REST API instead of re-importing by hand.

### 1. Create a Scoped API Key

In your n8n instance, go to **Settings → API Keys → Create an API Key** and grant:

* `workflow:read` — lets the deploy script fetch the live version of a workflow before updating, to detect whether anything actually changed
* `workflow:update` — lets it push the new `nodes`/`connections`/`settings`
* `workflow:list` — lets it fetch every live workflow's name once per run, to match local files against them by name (see below)
* `workflow:create` — only needed if you plan to use `allow_create` (see below) to let the script create workflows that don't exist live yet

No `workflow:delete`, `credential:*`, or `user:*` scopes are needed. (Older n8n versions without granular API key scopes only offer a single full-access key — the same capabilities are all that's used.)

### 2. Add Repository Secrets

Under **Settings → Secrets and variables → Actions**, add:

* `N8N_BASE_URL` — e.g. `https://n8n.yourdomain.tld`
* `N8N_API_KEY` — the key created above

### 3. Run the Deploy Workflow

The **🚀 Deploy Workflows to n8n** GitHub Action (`.github/workflows/deploy.yml`) is manual-only (`workflow_dispatch`) — nothing is ever pushed automatically on merge. From the **Actions** tab:

1. Run it once with **dry_run: true** (the default) to preview which workflows differ from what's currently live, without changing anything.
2. Review the output, then run it again with **dry_run: false** to actually apply the changes.
3. Optionally set **only_file** to a single filename (e.g. `Mensa Food.json`) to deploy just one workflow instead of all of them.
4. Optionally set **allow_create: true** to let it create workflows that exist locally but not live yet (see below). Off by default — an ordinary update run never creates anything.

### 4. Adding a New Workflow (`allow_create`)

Workflows are matched to their live counterpart **by name**, not by the `id` baked into the file. This is what makes both of the following possible:

* **Creating a new workflow.** Add a new file under `workflows/` with no `id` field (or any `id` — it's ignored for matching). If `allow_create` is off (the default), the script reports it as skipped and fails the run, so a typo'd or renamed workflow can't silently vanish from deploys. With `allow_create: true`, it's created via the API and assigned a real id.
* **Automatic `Execute Workflow` reference wiring.** Every `Execute Workflow` node's `workflowId` field carries the target's name alongside its cached id (`cachedResultName`). Each run resolves every such reference against the current live name → id map and rewrites it if it's stale — so a new sub-workflow's freshly assigned id automatically propagates into whatever parent workflow calls it, with no manual dropdown re-picking in the n8n editor.
* **Dangling reference detection.** If a reference's `cachedResultName` doesn't match *any* local or live workflow, the run reports it explicitly and fails, rather than silently pushing a broken reference.

A create/rewire run **never commits anything itself** — it rewrites the affected `workflows/*.json` files in place (new `id`, corrected `workflowId.value`/`cachedResultUrl`) and prints exactly which files it touched, so the repo doesn't silently drift from what's live. Review the diff and commit it yourself. When run via the GitHub Action, since the runner's checkout is discarded afterward, any changed files are also uploaded as a downloadable **`updated-workflow-jsons`** build artifact on the run's summary page.

Note that in dry-run mode a reference to a workflow that would need creating can't be fully previewed (there's no id to preview yet) — it's reported as "pending creation" instead. Run for real to see the actual resolved wiring.

Locally, the same script can be run directly:

```bash
N8N_BASE_URL="https://n8n.yourdomain.tld" N8N_API_KEY="..." DRY_RUN=true python3 deploy.py
```

n8n keeps its own version history per workflow (visible in the editor), so a bad deploy can be rolled back from there if needed.

---

## 🛠️ Modifying & Extending the Code

* **Seezeit XML Parsing**: The **Mensa Food Show Menu.json** workflow queries an XML endpoint managed by `max-manager.de`. It uses an evaluation mapping block to parse custom dietary codes (`24` = vegan, `51` = vegetarian, etc.). If Seezeit updates their nutritional tag identifiers, you must modify the structural logic inside the `Map Icons` JavaScript node.
* **Mattermost Endpoints**: Sub-workflows assume they are talking directly to the active open HCI development space cluster (`https://hci2.uni-konstanz.de/api/v4/...`). If the group switches hosting infrastructure or migrations alter base domains, update the request endpoint fields across your integration node profiles.
