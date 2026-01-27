#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

# ---------------------------------------------------------
# STEP 0: Load environment
# ---------------------------------------------------------
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER   = os.getenv("REPO_OWNER")
REPO_NAME    = os.getenv("REPO_NAME")
BASE_BRANCH  = os.getenv("BASE_BRANCH", "develop")
HEAD_BRANCH  = os.getenv("HEAD_BRANCH", "release123")

ENABLE_AI = os.getenv("ENABLE_AI", "false").lower() == "true"
DRY_RUN   = os.getenv("DRY_RUN", "false").lower() == "true"

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
    resp = requests.get(url, headers=HEADERS)
    return len(resp.json()) > 0

# ---------------------------------------------------------
# STEP 2: Compare branches
# ---------------------------------------------------------
def compare_branches():
    print(f"🔍 Comparing branches: {BASE_BRANCH} ← {HEAD_BRANCH}")
    url = f"{BASE_URL}/compare/{BASE_BRANCH}...{HEAD_BRANCH}"
    resp = requests.get(url, headers=HEADERS)

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
# STEP 3: Offline analysis (always available)
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
            f"- `{f['filename']}` (+{f.get('additions',0)} / -{f.get('deletions',0)})"
        )

    body.append("\n---\n_Auto-generated backport analysis._")
    return "\n".join(body)

# ---------------------------------------------------------
# STEP 4: AI analysis (optional)
# ---------------------------------------------------------
def analyze_with_ai(commits, files):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception:
        print("⚠️ AI disabled or OpenAI SDK missing")
        return None

    commit_text = "\n".join(
        f"- {c['commit']['message'].splitlines()[0]}"
        for c in commits
    )

    file_text = "\n".join(f"- {f['filename']}" for f in files)

    prompt = f"""
You are a release engineer.

Analyze the missing commits between branches.

COMMITS:
{commit_text}

FILES:
{file_text}

Provide:
1. Type of fixes
2. Risk level
3. Reviewer focus areas
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content

# ---------------------------------------------------------
# STEP 5: Create PR
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

    resp = requests.post(f"{BASE_URL}/pulls", headers=HEADERS, json=payload)

    if resp.status_code not in (200, 201):
        raise SystemExit(f"❌ PR creation failed: {resp.text}")

    pr = resp.json()
    print("✅ PR created:", pr["html_url"])
    return pr["number"]

# ---------------------------------------------------------
# STEP 6: Labels & reviewers (non-blocking)
# ---------------------------------------------------------
def add_labels(pr_number):
    try:
        requests.post(
            f"{BASE_URL}/issues/{pr_number}/labels",
            headers=HEADERS,
            json={"labels": ["auto-backport", "needs-review"]}
        )
    except Exception:
        pass

def add_reviewers(pr_number):
    try:
        requests.post(
            f"{BASE_URL}/pulls/{pr_number}/requested_reviewers",
            headers=HEADERS,
            json={"reviewers": ["team-lead", "release-owner"]}
        )
    except Exception:
        pass

# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    if pr_already_exists():
        print("⚠️ PR already exists. Exiting.")
        return

    commits, files = compare_branches()
    body = analyze_commits(commits, files)

    if ENABLE_AI:
        ai_summary = analyze_with_ai(commits, files)
        if ai_summary:
            body += "\n\n## 🤖 AI Review Insights\n" + ai_summary

    pr_number = create_pull_request(body)
    add_labels(pr_number)
    add_reviewers(pr_number)

if __name__ == "__main__":
    main()
