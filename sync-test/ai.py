#!/usr/bin/env python3

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------
# Cisco OpenAI Circuit API Call
# ---------------------------------------------------------
def call_circuit_api(access_token: str, prompt: str) -> dict:
    url = "https://chat-ai.cisco.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2024-02-15-preview"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "api-key": access_token,
    }
    
    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior release engineer performing deep risk analysis "
                    "for Git branch backports."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "user": json.dumps({"appkey": os.getenv("CISCO_OPENAI_APP_KEY")}),
        "temperature": 0.2,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------
# Deep Branch Analyzer (USED BY sync.py)
# ---------------------------------------------------------
def deep_branch_analyzer(payload: dict) -> dict:
    """
    Input: structured commit + file diff payload
    Output: STRICT JSON risk assessment
    """

    access_token = os.getenv("ACCESS_TOKEN")
    if not access_token:
        raise RuntimeError("ACCESS_TOKEN not found in environment")

    prompt = f"""
You are analyzing a Git backport from one branch to another.

Input JSON describes:
- Commits being backported
- Files impacted
- Change size and scope

Your task:
1. Identify potential BACKPORT RISK
2. Classify overall risk as LOW, MEDIUM, or HIGH
3. Decide whether auto-promotion is SAFE or NOT_SAFE
4. Explain WHY in concise bullet points

Risk guidance:
- Config/docs/tests only → LOW
- Limited code + clear fix → MEDIUM
- Core logic, infra, auth, DB, workflows → HIGH

STRICT OUTPUT RULES:
- Return ONLY valid JSON
- No markdown
- No extra text

Output format EXACTLY:

{{
  "risk_level": "LOW | MEDIUM | HIGH",
  "promotion_safe": "YES | NO",
  "key_risks": [
    "<short bullet>",
    "<short bullet>"
  ],
  "summary": "<one paragraph executive summary>"
}}

Input JSON:
{json.dumps(payload, indent=2)}
"""

    response = call_circuit_api(access_token, prompt)
    content = response["choices"][0]["message"]["content"].strip()

    # Enforce JSON safety
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        raise ValueError(f"AI returned non-JSON response:\n{content}")

