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

## 🛠️ Modifying & Extending the Code

* **Seezeit XML Parsing**: The **Mensa Food Show Menu.json** workflow queries an XML endpoint managed by `max-manager.de`. It uses an evaluation mapping block to parse custom dietary codes (`24` = vegan, `51` = vegetarian, etc.). If Seezeit updates their nutritional tag identifiers, you must modify the structural logic inside the `Map Icons` JavaScript node.
* **Mattermost Endpoints**: Sub-workflows assume they are talking directly to the active open HCI development space cluster (`https://hci2.uni-konstanz.de/api/v4/...`). If the group switches hosting infrastructure or migrations alter base domains, update the request endpoint fields across your integration node profiles.
