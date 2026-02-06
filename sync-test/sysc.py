#!/usr/bin/env python3

import os
import json
import requests
from dotenv import load_dotenv
import ai

# ---------------------------------------------------------
# Load environment
# ---------------------------------------------------------
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER   = os.getenv("REPO_OWNER")
REPO_NAME    = os.getenv("REPO_NAME")
BASE_BRANCH  = os.getenv("BASE_BRANCH", "develop")
HEAD_BRANCH  = os.getenv("HEAD_BRANCH", "release")

PR_APPROVER_USERNAME = os.getenv("PR_APPROVER_USERNAME")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

LAST_SHA_READ = "sha_last_read"

if not all([GITHUB_TOKEN, REPO_OWNER, REPO_NAME]):
    raise SystemExit("❌ Missing required environment variables")

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

BASE_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"


# ---------------------------------------------------------
# STEP 1: Check if PR already exists
# ---------------------------------------------------------
def pr_already_exists():
    url = f"{BASE_URL}/pulls?state=open&head={REPO_OWNER}:{HEAD_BRANCH}&base={BASE_BRANCH}"
    resp = requests.get(url, headers=HEADERS, timeout=15)

    if resp.status_code != 200:
        print("⚠️ Failed to check existing PRs")
        return False

    return len(resp.json()) > 0


# ---------------------------------------------------------
# STEP 2: Compare branches
# ---------------------------------------------------------
def compare_branches():
    print(f"🔍 Comparing branches: {BASE_BRANCH} ← {HEAD_BRANCH}")

    url = f"{BASE_URL}/compare/{BASE_BRANCH}...{HEAD_BRANCH}"
    resp = requests.get(url, headers=HEADERS, timeout=20)

    if resp.status_code != 200:
        raise SystemExit(f"❌ Compare API failed: {resp.text}")

    data = resp.json()
    commits = data.get("commits", [])
    files   = data.get("files", [])

    if not commits:
        print("✅ No missing commits found.")
        exit(0)

    print(f"✅ Found {len(commits)} missing commits")
    return commits, files


# ---------------------------------------------------------
# STEP 3: Offline summary
# ---------------------------------------------------------
def analyze_commits(commits, files):
    body = []
    body.append("## 🔍 Missing Fix Analysis\n")
    body.append(f"**Source:** `{HEAD_BRANCH}`")
    body.append(f"**Target:** `{BASE_BRANCH}`")
    body.append(f"**Commits:** {len(commits)}\n")

    body.append("### 📌 Commit Summary")
    for c in commits:
        msg = c["commit"]["message"].split("\n")[0]
        sha = c["sha"][:7]
        author = c["commit"]["author"]["name"]
        body.append(f"- `{sha}` – {msg} _(by {author})_")

    body.append("\n### 🗂 Files Impacted")
    for f in files:
        body.append(
            f"- `{f['filename']}` (+{f.get('additions', 0)} / -{f.get('deletions', 0)})"
        )

    body.append("\n---\n_Auto-generated backport analysis._")
    return "\n".join(body)


# ---------------------------------------------------------
# STEP 4: Create PR
# ---------------------------------------------------------
def create_pull_request(pr_body):
    title = f"sync {HEAD_BRANCH} → {BASE_BRANCH}"

    if DRY_RUN:
        print("🧪 DRY-RUN MODE")
        print("PR Title:", title)
        print("PR Body:\n", pr_body)
        exit(0)

    payload = {
        "title": title,
        "head": HEAD_BRANCH,
        "base": BASE_BRANCH,
        "body": pr_body,
        "maintainer_can_modify": True
    }

    resp = requests.post(
        f"{BASE_URL}/pulls",
        headers=HEADERS,
        json=payload,
        timeout=20
    )

    if resp.status_code not in (200, 201):
        raise SystemExit(f"❌ PR creation failed: {resp.text}")

    pr = resp.json()
    print("✅ PR created:", pr["html_url"])
    return pr["number"]


# ---------------------------------------------------------
# STEP 5: Labels & reviewer
# ---------------------------------------------------------
def add_labels(pr_number):
    try:
        requests.post(
            f"{BASE_URL}/issues/{pr_number}/labels",
            headers=HEADERS,
            json={"labels": ["auto-backport", "needs-review"]},
            timeout=10
        )
    except Exception:
        pass


def add_reviewer(pr_number):
    if not PR_APPROVER_USERNAME:
        print("Skipping reviewer request: PR_APPROVER_USERNAME not set.")
        return

    try:
        requests.post(
            f"{BASE_URL}/pulls/{pr_number}/requested_reviewers",
            headers=HEADERS,
            json={"reviewers": [PR_APPROVER_USERNAME]},
            timeout=10
        )
    except Exception as e:
        print(f"⚠️ Reviewer request failed: {e}")


# ---------------------------------------------------------
# STEP 6: Build AI payload
# ---------------------------------------------------------
def build_deep_ai_payload(commits, files):
    return {
        "commit_count": len(commits),
        "commits": [
            {
                "sha": c["sha"][:7],
                "message": c["commit"]["message"],
                "author": c["commit"]["author"]["name"]
            }
            for c in commits
        ],
        "files": [
            {
                "file": f["filename"],
                "status": f.get("status"),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0)
            }
            for f in files
        ]
    }


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    if pr_already_exists():
        print("⚠️ PR already exists. Exiting.")
        return

    commits, files = compare_branches()

    ai_payload = build_deep_ai_payload(commits, files)
    ai_report = None

    try:
        ai_report = ai.deep_branch_analyzer(ai_payload)
        print("🤖 AI Deep Analysis complete")
    except Exception as e:
        print(f"⚠️ AI analysis skipped: {e}")

    body = analyze_commits(commits, files)

    if ai_report:
        body += "\n\n## 🤖 AI Risk Assessment\n"
        body += f"```json\n{json.dumps(ai_report, indent=2)}\n```"

    pr_number = create_pull_request(body)
    add_labels(pr_number)
    add_reviewer(pr_number)


if __name__ == "__main__":
    main()
