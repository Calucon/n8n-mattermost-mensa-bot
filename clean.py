#!/usr/bin/env python3
import os
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def sanitize_workflows(directory: str = "."):
    """
    Recursively scans a directory for n8n JSON workflow files (.json).

    This utility performs two main actions:
    1.  Strips sensitive test data (`pinData`): Removes cached execution payloads which may
        contain live session webhooks, user IDs, and other private credentials.
    2.  Standardizes formatting: Rewrites the JSON with a consistent 2-space indent
    and standardizes JSON formatting for clean Git tracking.
    """
    cleaned_count = 0
    formatted_count = 0

    print(f"🔍 Scanning '{directory}' for n8n workflow files...")

    for root, dirs, files in os.walk(directory):
        # Skip hidden dirs (e.g. .git) and Python cache dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for filename in files:
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(root, filename)

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    workflow = json.loads(f.read())
            except (json.JSONDecodeError, PermissionError, UnicodeDecodeError) as e:
                # Skip files that aren't valid JSON or can't be read
                print(f"⚠️  Skipping non-workflow file: {filepath} ({type(e).__name__})")
                continue
            except FileNotFoundError:
                # Edge case: file was deleted during the scan
                continue

            # Basic validation to check if the JSON is actually an n8n workflow export
            if not (isinstance(workflow, dict) and ("nodes" in workflow or "connections" in workflow)):
                continue

            has_pin_data = "pinData" in workflow and bool(workflow["pinData"])

            # Force clear the pinData structure
            workflow["pinData"] = {}

            # Save the file with standard 2-space indentation
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(workflow, f, indent=2, ensure_ascii=False)
                f.write("\n")  # Add a trailing newline to satisfy standard linting rules

            if has_pin_data:
                print(f"🧹 Cleaned pinned metadata from: {filepath}")
                cleaned_count += 1
            else:
                print(f"✨ Formatted and verified clean: {filepath}")
                formatted_count += 1

    print("\n🏁 Sanitization Summary:")
    print(f"   - Files stripped of credentials/pinData: {cleaned_count}")
    print(f"   - Files formatted for Git compliance:     {formatted_count}")

if __name__ == "__main__":
    # Allow passing a target directory path as an argument (defaults to current directory)
    target_directory = sys.argv[1] if len(sys.argv) > 1 else "."
    sanitize_workflows(target_directory)
