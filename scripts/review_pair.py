#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentMeet - Adversarial Review Pair Matrix Generator (Standard Library Only)
Tự động sinh ma trận phân công Review chéo giữa các Agents:
- Nguyên tắc 1: Không bao giờ tự review code của mình (reviewer != author).
- Nguyên tắc 2: Phân bổ đều tải lượng review giữa các agents.
- Nguyên tắc 3: Hỗ trợ mô hình 2 agents (A <-> B) hoặc xoay vòng 3+ agents (A -> B -> C -> A).
- Tùy chọn broadcast thông báo phân công vào phòng họp qua AgentMeet API.

Ví dụ sử dụng:
  # Chỉ định rõ task và tác giả (task:author):
  python scripts/review_pair.py --agents "Alice,Bob,Charlie" --tasks "PR-01:Alice,PR-02:Bob,PR-03:Charlie"

  # Tự động gán tác giả xoay vòng:
  python scripts/review_pair.py --agents "Gemini,opencode" --tasks "PR-01,PR-02"
"""

from __future__ import annotations

import sys
import os
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# Đưa thư mục gốc package vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentmeet import load_credentials, DEFAULT_BASE_URL

EXIT_OK = 0
EXIT_CONFIG = 3
EXIT_API = 4

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def parse_args():
    parser = argparse.ArgumentParser(
        description="AgentMeet Code Review Pair Assigner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ví dụ định dạng task:
  --tasks "PR-01:Alice,PR-02:Bob"    (Định dạng task_name:author)
  --tasks "PR-01,PR-02"              (Tác giả tự động chia đều theo agents)
"""
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL (default: https://www.agentmeet.net)")
    parser.add_argument("--room", help="Room ID (e.g. 303-e183-fb29)")
    parser.add_argument("--token", help="Agent Token")
    parser.add_argument("--token-file", help="Path to credentials JSON")
    parser.add_argument("--agents", help="Comma-separated list of agents (e.g. 'Alice,Bob,Charlie')")
    parser.add_argument("--tasks", help="Comma-separated list of tasks (e.g. 'PR-01:Alice,PR-02:Bob' hoặc 'PR-01,PR-02')")
    parser.add_argument("--author", help="Author agent for a single task")
    parser.add_argument("--task", help="Single task name or ID")
    parser.add_argument("--broadcast", action="store_true", help="Post review matrix to AgentMeet room")
    return parser.parse_args()

def load_creds(args):
    creds_file = args.token_file or "agent_creds.json"
    if not os.path.exists(creds_file):
        home_creds = os.path.expanduser("~/.agentmeet/creds.json")
        if os.path.exists(home_creds):
            creds_file = home_creds

    room = args.room
    token = args.token
    agent_name = ""
    base_url = args.base_url

    if os.path.exists(creds_file):
        try:
            c = load_credentials(creds_file)
            room = room or c.get("room") or c.get("room_id") or c.get("room_code")
            token = token or c.get("agent_token")
            agent_name = c.get("agent_name", "")
            if args.base_url == DEFAULT_BASE_URL and c.get("base_url"):
                base_url = c.get("base_url")
        except Exception:
            pass

    return base_url, room, token, agent_name

def fetch_room_agents(base_url, room):
    url = f"{base_url.rstrip('/')}/api/v1/{room}/transcript?limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "AgentMeet-ReviewPair/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            agents = data.get("agents", [])
            return [a.get("agent_name") for a in agents if a.get("status") == "active" and a.get("agent_name") != "Admin"]
    except urllib.error.HTTPError as e:
        print(f"[WARN] Không thể lấy danh sách agents từ room (HTTP {e.code}: {e.reason})", file=sys.stderr)
        return []
    except urllib.error.URLError as e:
        print(f"[WARN] Lỗi mạng khi lấy agents: {e.reason}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[WARN] Lỗi xử lý transcript: {e}", file=sys.stderr)
        return []

def build_review_matrix(agents, tasks):
    """
    agents: list of str
    tasks: list of dict {"task": str, "author": str}
    """
    matrix = []
    num_agents = len(agents)
    if num_agents < 2:
        for t in tasks:
            matrix.append({
                "task": t["task"],
                "author": t.get("author", "Unknown"),
                "reviewer": "N/A (Solo Agent)",
                "status": "SELF_REVIEW"
            })
        return matrix

    # Round-robin balanced assignment
    for i, t in enumerate(tasks):
        author = t.get("author")
        candidates = [a for a in agents if a != author]
        reviewer = candidates[i % len(candidates)] if candidates else "N/A"
        matrix.append({
            "task": t["task"],
            "author": author or "Unassigned",
            "reviewer": reviewer,
            "status": "PENDING_REVIEW"
        })
    return matrix

def main():
    args = parse_args()
    base_url, room, token, my_name = load_creds(args)

    # 1. Xác định danh sách agents
    agent_list = []
    if args.agents:
        agent_list = [a.strip() for a in args.agents.split(",") if a.strip()]
    elif room:
        agent_list = fetch_room_agents(base_url, room)

    if not agent_list:
        agent_list = ["Gemini (Antigravity)", "opencode (deepseek-v4.1-flash)"]

    print(f"=== AGENTMEET CODE REVIEW PAIRING ===")
    print(f"Active Reviewers ({len(agent_list)}): {', '.join(agent_list)}\n")

    # 2. Xử lý Single Task hoặc Batch Tasks
    tasks = []
    if args.task:
        tasks.append({"task": args.task, "author": args.author or my_name or agent_list[0]})
    elif args.tasks:
        raw_tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
        for idx, rt in enumerate(raw_tasks):
            if ":" in rt:
                parts = rt.split(":", 1)
                tasks.append({"task": parts[0].strip(), "author": parts[1].strip()})
            else:
                author = agent_list[idx % len(agent_list)]
                tasks.append({"task": rt, "author": author})
    else:
        # Default demo tasks
        tasks = [
            {"task": "PR-01: Safe Proxy Mapping", "author": agent_list[0]},
            {"task": "PR-02: Endpoint Retry & Healthcheck", "author": agent_list[1] if len(agent_list) > 1 else agent_list[0]},
        ]

    matrix = build_review_matrix(agent_list, tasks)

    # In bảng Markdown
    lines = []
    lines.append("| Task / Module | Tác giả (Author) | Người phản biện (Reviewer) | Trạng thái |")
    lines.append("|---|---|---|---|")
    for row in matrix:
        lines.append(f"| `{row['task']}` | **{row['author']}** | **{row['reviewer']}** | `{row['status']}` |")

    report = "\n".join(lines)
    print(report)

    # 3. Broadcast vào room nếu có cờ --broadcast
    if args.broadcast:
        if not (room and token):
            print("[ERROR] Không thể broadcast: thiếu room hoặc agent_token (--token hoặc --token-file).", file=sys.stderr)
            sys.exit(EXIT_CONFIG)

        content = f"### [REVIEW_MATRIX] PHÂN CÔNG REVIEW CHÉO KỸ THUẬT\n\n{report}\n\n*Nguyên tắc: Reviewer phải kiểm tra logic, race condition, data safety trước khi duyệt!*"
        post_url = f"{base_url.rstrip('/')}/api/v1/{room}/message"
        payload = {
            "agent_token": token,
            "agent_name": my_name or "Coordinator",
            "content": content
        }
        try:
            req_data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            post_req = urllib.request.Request(
                post_url,
                data=req_data,
                headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "AgentMeet-ReviewPair/1.0"}
            )
            with urllib.request.urlopen(post_req, timeout=10) as resp:
                if resp.status == 201:
                    print("\n[OK] Đã phát Review Matrix vào phòng họp thành công!")
        except urllib.error.HTTPError as e:
            print(f"\n[ERROR] Lỗi API HTTP {e.code}: {e.reason}", file=sys.stderr)
            sys.exit(EXIT_API)
        except urllib.error.URLError as e:
            print(f"\n[ERROR] Lỗi kết nối mạng: {e.reason}", file=sys.stderr)
            sys.exit(EXIT_API)

if __name__ == "__main__":
    main()
