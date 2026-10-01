#!/usr/bin/env python3
"""verify_helper.py - Cross-check and verify findings in AgentMeet.

Helps implement Admin's rule #5: "phải có 1 thằng review, kiểm chứng sự thật,
verify, tránh trường hợp cả nhóm mù quáng tin rằng việc đó đã xong".

Features:
- Extract claims/findings from messages and list them for verification
- Check if a claim has been confirmed/challenged by other agents
- Generate verification checklist

Usage:
    python verify_helper.py --check                        # List unverified claims
    python verify_helper.py --agent Antigravity            # Claims by specific agent
    python verify_helper.py --keyword "solved"             # Claims about solving
    python verify_helper.py --confirm <msg_id>             # Mark a claim as verified
    python verify_helper.py --challenge <msg_id> <reason>  # Challenge a claim
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from agentmeet import AgentMeet


VERIFY_LOG = r"/home/noble-tran/agent-meet_skill\verify_log.json"


def load_creds(token_file=None):
    creds_path = token_file or os.environ.get("AGENTMEET_CREDS", r"/home/noble-tran/agent-meet_skill\agent_creds.json")
    with open(creds_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_verify_log():
    if os.path.exists(VERIFY_LOG):
        with open(VERIFY_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"verified": [], "challenged": []}


def save_verify_log(log):
    with open(VERIFY_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def extract_claims(messages):
    """Extract claim-like statements from messages."""
    claims = []
    patterns = [
        (r'(?:đã|ĐÃ)\s+(?:giải|solve|found|extract|crack)', 'SOLVE'),
        (r'(?:thành công|SUCCESS|CORRECT|solved)', 'SUCCESS'),
        (r'(?:INCORRECT|sai|trượt|failed)', 'FAILED'),
        (r'(?:flag|FLAG)\s*[:=]', 'FLAG'),
        (r'number\{[^}]+\}', 'FLAG_VALUE'),
        (r'(?:password|pass|pwd)\s*[:=]', 'PASSWORD'),
        (r'(?:BLOCKER|stuck|không tìm)', 'BLOCKER'),
    ]
    
    for msg in messages:
        content = msg.get("content", "")
        mid = msg.get("message_id", 0)
        sender = msg.get("agent_name", "?")
        
        for pattern, claim_type in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                claims.append({
                    "msg_id": mid,
                    "sender": sender,
                    "type": claim_type,
                    "match": matches[0][:100] if isinstance(matches[0], str) else str(matches[0])[:100],
                    "preview": content[:200].replace("\n", " "),
                })
                break  # One claim per message to avoid duplicates
    
    return claims


def main():
    parser = argparse.ArgumentParser(description="Verify findings in AgentMeet")
    parser.add_argument("--check", action="store_true", help="List claims needing verification")
    parser.add_argument("--agent", help="Filter claims by agent")
    parser.add_argument("--keyword", help="Filter claims by keyword")
    parser.add_argument("--confirm", type=int, help="Mark message ID as verified")
    parser.add_argument("--challenge", nargs=2, metavar=("MSG_ID", "REASON"), help="Challenge a claim")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--token-file", default=None, help="Path to credentials file")
    args = parser.parse_args()

    creds = load_creds(args.token_file)
    room = creds.get("room") or creds.get("room_code") or creds.get("room_id")
    m = AgentMeet(room=room)
    log = load_verify_log()

    if args.confirm:
        log["verified"].append({"msg_id": args.confirm, "by": "GLM", "time": __import__("datetime").datetime.now().isoformat()})
        save_verify_log(log)
        print(f"✅ Message #{args.confirm} marked as verified")
        return

    if args.challenge:
        msg_id, reason = int(args.challenge[0]), args.challenge[1]
        log["challenged"].append({"msg_id": msg_id, "reason": reason, "by": "GLM", "time": __import__("datetime").datetime.now().isoformat()})
        save_verify_log(log)
        print(f"⚠️ Message #{msg_id} challenged: {reason}")
        return

    # Fetch recent messages
    result = m.transcript(limit=100)
    messages = result.get("messages", [])

    # Extract claims
    claims = extract_claims(messages)

    # Filter
    if args.agent:
        claims = [c for c in claims if args.agent.lower() in c["sender"].lower()]
    if args.keyword:
        claims = [c for c in claims if args.keyword.lower() in c["preview"].lower()]

    # Remove already verified/challenged
    verified_ids = {v["msg_id"] for v in log.get("verified", [])}
    challenged_ids = {c["msg_id"] for c in log.get("challenged", [])}

    for claim in claims:
        mid = claim["msg_id"]
        status = ""
        if mid in verified_ids:
            status = " ✅"
        elif mid in challenged_ids:
            status = " ⚠️"
        claim["status"] = status

    if args.json:
        print(json.dumps(claims, ensure_ascii=False, indent=2))
    else:
        print(f"📋 CLAIMS CHECK ({len(claims)} found):\n")
        for c in claims:
            print(f"  #{c['msg_id']:>4}{c['status']} [{c['type']}] {c['sender']}: {c['match']}")
            print(f"         Preview: {c['preview'][:120]}...")
            print()


if __name__ == "__main__":
    main()
